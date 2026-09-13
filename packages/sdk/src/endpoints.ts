/**
 * Um lugar só para as chamadas da API — nenhuma tela monta URL na mão.
 *
 * Separado por escopo: `painel` são as rotas do operador, `app` as do motorista.
 * O empacotador remove o que cada cliente não importa.
 */
import { api, request } from './http'
import type * as T from './types'

/**
 * Chave que identifica uma tentativa de escrita, para o servidor reconhecer o
 * retry como a mesma operacao.
 *
 * Sem `crypto.randomUUID`: ele nao e' global no Hermes, e o app quebraria em
 * producao por causa de uma chave. Aqui nao e' preciso ser imprevisivel - so
 * unica dentro da sessao -, entao relogio mais contador mais ruido bastam.
 */
let sequencia = 0
function chaveDeIdempotencia(): string {
  sequencia += 1
  return `${Date.now().toString(36)}-${sequencia.toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

// ---- autenticação (os dois clientes) ----------------------------------------
export const auth = {
  login: (email: string, senha: string) =>
    request<T.TokenPairOut>('/auth/login', {
      method: 'POST',
      body: { email, password: senha },
      auth: false
    }),
  /**
   * Cadastro publico do app do motorista. Sem token, e sempre motorista.
   *
   * O tipo vem do contrato (`RegistroPublicoIn`), e nao escrito a mao: e' o que
   * garante que `role` e `site_id` nao tenham como ser enviados daqui nem por
   * engano - o servidor tambem os recusa, mas errar isso no cliente daria um
   * 422 no lugar de um erro de compilacao.
   *
   * Devolve o usuario, e NAO um par de tokens: quem cadastra ainda precisa
   * fazer login em seguida.
   */
  register: (dados: T.RegistroPublico) =>
    request<T.Usuario>('/auth/register', { method: 'POST', body: dados, auth: false }),
  me: () => api.get<T.Usuario>('/auth/me')
}

// ---- painel comercial -------------------------------------------------------
export const power = {
  overview: () => api.get<T.VisaoPotencia>('/power/overview'),
  budget: () => api.get<T.Orcamento>('/power/budget'),
  updateBudget: (dados: Record<string, unknown>) => api.patch<T.Orcamento>('/power/budget', dados),
  plan: () => api.get<T.PlanoDeRateio>('/power/plan'),
  /** Projeta a demanda das proximas horas contra o contrato. */
  demandForecast: (horas = 6) =>
    api.get<Record<string, unknown>>('/power/demand/forecast', { horas }),
  /** Qual demanda contratar, dado o consumo real medido. */
  contractSimulator: (dias = 30, passoKw = 5) =>
    api.get<Record<string, unknown>>('/power/demand/contract-simulator', {
      dias,
      passo_kw: passoKw
    }),
  /** Pontos que vem falhando com frequencia. */
  maintenanceAttention: (dias = 30) =>
    api.get<Record<string, unknown>>('/power/maintenance/attention', { dias }),
  /**
   * A fila de problemas reportados por quem esteve no ponto.
   *
   * `maintenanceAttention` agrupa e diz QUANTOS estao abertos; esta diz QUAIS.
   */
  maintenanceReports: (abertos = true, limit = 100) =>
    api.get<T.ReporteDoPonto[]>('/power/maintenance/reports', { abertos, limit }),
  /** Fecha um reporte. A descricao do que foi feito e' obrigatoria. */
  resolveReport: (id: string, resolucao: string) =>
    api.post<{ id: string; resolvido: boolean; resolvido_em: string; resolucao: string }>(
      `/power/maintenance/reports/${id}/resolve`,
      { resolucao }
    ),
  /** Sites que o usuario pode escolher no seletor (operador ve so o proprio). */
  visibleSites: () => api.get<Record<string, unknown>[]>('/power/sites'),
  /** As pracas lado a lado. So admin. */
  portfolio: (dias = 30) => api.get<Record<string, unknown>>('/power/sites/portfolio', { dias }),
  /** Regras de prioridade nomeadas do site. */
  /**
   * Quanto o site deve VENDER no proximo mes, em kWh e em reais.
   *
   * Calculada fora da API, por um job que roda uma vez por mes. Sem previsao a
   * resposta vem com `disponivel: false` e um motivo - nao e' erro.
   */
  energyForecast: () => api.get<Record<string, unknown>>('/power/demand/energy-forecast'),
  priorityRules: () => api.get<Record<string, unknown>[]>('/power/priority-rules'),
  createPriorityRule: (dados: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/power/priority-rules', dados),
  updatePriorityRule: (id: string, dados: Record<string, unknown>) =>
    api.put<Record<string, unknown>>(`/power/priority-rules/${id}`, dados),
  deletePriorityRule: (id: string) => api.del<void>(`/power/priority-rules/${id}`),
  /** Qual regra pegaria cada ponto, no horario informado (HH:MM local). */
  priorityPreview: (hora?: string) =>
    api.get<Record<string, unknown>>('/power/priority-rules/preview', hora ? { hora } : {}),
  /** Ocupacao, receita e ociosidade de cada ponto. */
  utilizationByPoint: (dias = 30) =>
    api.get<Record<string, unknown>>('/power/utilization/by-point', { dias }),
  /** Quanto o rateio poupou de ultrapassagem no periodo. */
  avoidedCost: (dias = 30) =>
    api.get<Record<string, unknown>>('/power/demand/avoided-cost', { dias }),
  rebalance: (dryRun = false) =>
    api.post<Record<string, unknown>>('/power/rebalance', undefined, { dry_run: dryRun }),
  setLimit: (id: string, limitKw: number) =>
    api.post<T.PontoDeRecarga>(`/power/charge-points/${id}/limit`, { limit_kw: limitKw }),
  throttle: (id: string, enabled: boolean) =>
    api.post<T.PontoDeRecarga>(`/power/charge-points/${id}/throttle`, undefined, { enabled }),
  pushMeterReading: (dados: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/power/meter-readings', dados)
}

export const sessions = {
  list: (params?: Record<string, string | number | undefined>) =>
    api.get<T.Pagina<T.Sessao>>('/sessions', params),
  kpis: () => api.get<T.KpisDeSessao>('/sessions/kpis'),
  get: (id: string) => api.get<T.SessaoDetalhada>(`/sessions/${id}`),
  start: (dados: { charge_point_id: string; [k: string]: unknown }) =>
    api.post<T.SessaoDetalhada>('/sessions', dados),
  stop: (id: string, dados: Record<string, unknown> = { reason: 'remote', auto_bill: true }) =>
    api.post<T.SessaoDetalhada>(`/sessions/${id}/stop`, dados),
  preview: (id: string) => api.get<T.Precificacao>(`/sessions/${id}/preview`),
  telemetry: (id: string, minutes = 120) =>
    api.get<Array<Record<string, number | string | null>>>(`/sessions/${id}/telemetry`, {
      minutes
    }),
  bill: (id: string) => api.post<Record<string, unknown>>(`/sessions/${id}/bill`)
}

export const tariffs = {
  list: () => api.get<T.Tarifa[]>('/tariffs'),
  create: (dados: Record<string, unknown>) => api.post<T.Tarifa>('/tariffs', dados),
  update: (id: string, dados: Record<string, unknown>) =>
    api.patch<T.Tarifa>(`/tariffs/${id}`, dados),
  replaceWindows: (id: string, janelas: Array<Record<string, unknown>>) =>
    api.put<T.Tarifa>(`/tariffs/${id}/windows`, janelas),
  remove: (id: string) => api.del<void>(`/tariffs/${id}`),
  simulate: (dados: Record<string, unknown>) => api.post<T.Precificacao>('/tariffs/simulate', dados)
}

export const payments = {
  listMethods: () => api.get<T.MetodoDePagamento[]>('/payment-methods'),
  upsertMethod: (dados: Record<string, unknown>) =>
    api.put<T.MetodoDePagamento>('/payment-methods', dados),
  listInvoices: (params?: Record<string, string | number | undefined>) =>
    api.get<T.Pagina<T.Fatura>>('/invoices', params),
  charge: (id: string, metodo: T.TipoDePagamento, idempotencyKey?: string) =>
    api.post<T.Pagamento>(`/invoices/${id}/charge`, {
      method: metodo,
      idempotency_key: idempotencyKey
    }),
  revenueSummary: (days = 30) => api.get<T.ResumoDeReceita>('/revenue/summary', { days })
}

// ---- app do motorista -------------------------------------------------------
// --------------------------------------------------------------- campanhas
//
// Gestao pelo operador. O `site_id` NAO viaja no corpo: o servidor o tira do
// escopo do token, e mandar um daqui so' criaria a impressao de que a tela
// escolhe quem paga.
/**
 * O que so' admin pode: devolver dinheiro, corrigir saldo e ler a trilha.
 *
 * Bloco proprio porque o criterio e' o mesmo nas tres - mexer no dinheiro de
 * terceiro, ou ler quem mexeu. O servidor recusa as tres para operador; a tela
 * as esconde pelo mesmo motivo.
 */
export const admin = {
  /** Estorna a fatura. Carteira volta na hora; PSP, pelo provedor. */
  refundInvoice: (invoiceId: string) => api.post<T.Pagamento>(`/invoices/${invoiceId}/refund`, {}),
  /** Correcao manual de saldo. O motivo e' obrigatorio, e vai para o extrato. */
  adjustWallet: (userId: string, valor: number, motivo: string) =>
    api.post<T.ExtratoDaCarteira>(`/wallets/${userId}/adjust`, {
      valor: valor.toFixed(2),
      motivo
    }),
  /** Quem fez o que, com dinheiro e com permissao. */
  auditTrail: (limit = 100, action?: string, entity?: string) =>
    api.get<T.LinhaDeAuditoria[]>('/audit', { limit, action, entity }),

  // ---- contas de operacao ----------------------------------------------
  //
  // Motorista NAO aparece aqui: ele se cadastra sozinho pelo app, e sao
  // milhares. Esta e' a lista de quem opera a rede.

  /** Operadores e admins, com a praca de cada um. Traz os desligados. */
  users: (inativas = true) => api.get<T.ContaDeOperacao[]>('/users', { inativas }),
  /** Cria operador (exige `site_id`) ou admin. So admin da rede. */
  createUser: (dados: T.ContaNova) => api.post<T.ContaDeOperacao>('/users', dados),
  /**
   * Liga ou desliga o acesso. Nao ha apagar: as FKs de auditoria e faturamento
   * sao SET NULL, entao apagar a conta apaga o vinculo do rastro dela.
   */
  setUserActive: (userId: string, ativa: boolean) =>
    api.patch<T.ContaDeOperacao>(`/users/${userId}`, { is_active: ativa })
}

export const campaigns = {
  /** Campanhas desta praca, mais as de rede que agem sobre ela. */
  list: () => api.get<T.Campanha[]>('/campaigns'),
  /**
   * Frotas as quais uma campanha pode ser dirigida - so' id e nome.
   *
   * Sob `/campaigns` porque e' o que ela serve: preencher o seletor do
   * formulario. Uma `/fleets` de proposito geral prometeria administracao de
   * frota, que este painel nao faz.
   */
  fleets: () => api.get<T.FrotaParaCampanha[]>('/campaigns/fleets'),
  /** Cria a campanha junto com as missoes, numa transacao so'. */
  create: (corpo: T.CampanhaNova) => api.post<T.Campanha>('/campaigns', corpo),
  /** Edicao parcial: so' os campos tocados viajam. */
  update: (id: string, mudancas: Partial<T.CampanhaNova>) =>
    api.patch<T.Campanha>(`/campaigns/${id}`, mudancas),
  /** Se o dinheiro comprou comportamento ou so' saiu do caixa. */
  performance: (id: string) => api.get<T.DesempenhoDaCampanha>(`/campaigns/${id}/desempenho`),
  /** Encerra. Nao apaga: o progresso de quem estava no meio dela sobrevive. */
  close: (id: string) => api.del<void>(`/campaigns/${id}`)
}

// ------------------------------------------------- contrato da plataforma
//
// Dinheiro na direcao oposta ao resto do sistema: aqui o estabelecimento paga a
// rede, e nao o motorista paga o estabelecimento.
export const platform = {
  /** O que a GoodWe vende ao estabelecimento. */
  plans: () => api.get<Record<string, unknown>[]>('/platform/plans'),
  /** Contrato desta praca, com as ultimas cobrancas. */
  contract: () => api.get<Record<string, unknown>>('/platform/contract'),
  /** Contrata. O site vem do escopo do token, nunca do corpo. */
  subscribe: (codigo: string, multaPercentual?: number) =>
    api.post<Record<string, unknown>>('/platform/contract', {
      codigo,
      multa_percentual: multaPercentual
    }),
  /** Pede a rescisao. Dentro do prazo minimo, emite a multa junto. */
  terminate: () => api.post<Record<string, unknown>>('/platform/contract/terminate', {}),
  /** Baixa MANUAL da cobranca. So' admin: nao ha liquidacao automatica. */
  settle: (cobrancaId: string) =>
    api.post<Record<string, unknown>>(`/platform/invoices/${cobrancaId}/settle`, {})
}

export const app = {
  /** Catalogo de planos de recarga. Escopo de rede, nao de praca. */
  plans: () => api.get<Record<string, unknown>[]>('/app/plans'),
  /** Plano do proprio motorista, com franquia restante e proxima cobranca. */
  subscription: () => api.get<Record<string, unknown>>('/app/subscription'),
  /** Assina e cobra a primeira mensalidade da carteira. 402 = sem saldo. */
  subscribe: (codigo: string) => api.post<Record<string, unknown>>('/app/subscription', { codigo }),
  /** Cancela a renovacao. O mes ja pago continua valendo ate o fim. */
  unsubscribe: () => api.del<void>('/app/subscription'),
  /** Missoes vigentes com o progresso de quem esta pedindo. */
  missions: () => api.get<T.Missao[]>('/app/missions'),
  /** Historico de recompensas do proprio motorista. */
  rewards: () => api.get<T.Recompensa[]>('/app/rewards'),
  stations: (params?: { latitude?: number; longitude?: number; radius_km?: number }) =>
    api.get<T.Estacao[]>('/app/stations', params),
  stationChargePoints: (siteId: string) =>
    api.get<T.PontoDaEstacao[]>(`/app/stations/${siteId}/charge-points`),
  /** Resolve o ponto pelo codigo lido no QR colado no carregador. */
  chargePointByCode: (codigo: string) =>
    api.get<T.PontoLido>(`/app/charge-points/by-code/${encodeURIComponent(codigo)}`),
  /**
   * Inicia a recarga. Os tres limites sao tetos opcionais que o servidor
   * aplica sozinho: a ingestao de telemetria encerra a sessao no primeiro
   * que for atingido.
   */
  startSession: (params: {
    charge_point_id: string
    preauth_amount?: number
    limit_kwh?: number
    limit_minutes?: number
    limit_amount?: number
  }) => api.post<T.SessaoDetalhada>('/app/sessions', undefined, params),
  /** Reporta um problema visto no ponto — o motorista ve antes do sensor. */
  reportProblem: (
    chargePointId: string,
    dados: { categoria: string; descricao?: string; session_id?: string }
  ) => api.post<Record<string, unknown>>(`/app/charge-points/${chargePointId}/reports`, dados),
  /**
   * Os reportes que ESTE motorista fez neste ponto, com o desfecho.
   *
   * E' o que fecha o ciclo de quem reportou: sem isto ele manda o problema e
   * nunca fica sabendo se alguem olhou.
   */
  myReports: (chargePointId: string) =>
    api.get<T.MeuReporte[]>(`/app/charge-points/${chargePointId}/reports`),
  /** Relatorio mensal da frota, por centro de custo. So gestor. */
  fleetReport: (mes: string) => api.get<Record<string, unknown>>('/app/fleet/report', { mes }),
  /** Carros da frota e seus centros de custo. So gestor. */
  fleetVehicles: () => api.get<T.VeiculoDaFrota[]>('/app/fleet/vehicles'),
  /** Define (ou limpa, com null) a area do carro. Vazio ou so espaco limpa. */
  setCostCenter: (vehicleId: string, centro: string | null) =>
    api.put<T.VeiculoDaFrota>(`/app/fleet/vehicles/${vehicleId}/cost-center`, {
      centro_de_custo: centro
    }),
  /** Registra (ou reaponta) o aparelho que recebe notificacao push. */
  registerPushDevice: (token: string, platform: 'android' | 'ios' = 'android') =>
    api.post<void>('/app/push-devices', { token, platform }),
  /** Remove o aparelho ao sair da conta. */
  unregisterPushDevice: (token: string) =>
    api.del<void>(`/app/push-devices/${encodeURIComponent(token)}`),
  /** Dados do recibo de uma fatura do proprio motorista. */
  receipt: (invoiceId: string) =>
    api.get<Record<string, unknown>>(`/app/invoices/${invoiceId}/receipt`),
  /** O documento em HTML, pronto para virar PDF no aparelho. */
  receiptHtml: (invoiceId: string) => api.getText(`/app/invoices/${invoiceId}/receipt.html`),
  /** Quando compensa comecar: compara agora com o melhor horario a frente. */
  whenToStart: (chargePointId: string, kwh = 30, horas = 12) =>
    api.get<Record<string, unknown>>(`/app/charge-points/${chargePointId}/when-to-start`, {
      kwh,
      horas
    }),
  mySessions: (limit = 20) => api.get<T.Sessao[]>('/app/sessions', { limit }),
  activeSession: () => api.get<T.SessaoDetalhada | null>('/app/sessions/active'),
  sessionPreview: (id: string) => api.get<T.Precificacao>(`/app/sessions/${id}/preview`),
  stopSession: (id: string) => api.post<T.SessaoDetalhada>(`/app/sessions/${id}/stop`),
  createReservation: (dados: Record<string, unknown>) =>
    api.post<T.Agendamento>('/app/reservations', dados),
  myReservations: () => api.get<T.Agendamento[]>('/app/reservations'),
  cancelReservation: (id: string) => api.del<T.Agendamento>(`/app/reservations/${id}`),
  myVehicles: () => api.get<T.Veiculo[]>('/app/vehicles'),
  addVehicle: (dados: Record<string, unknown>) => api.post<T.Veiculo>('/app/vehicles', dados),
  updateVehicle: (id: string, dados: Record<string, unknown>) =>
    api.patch<T.Veiculo>(`/app/vehicles/${id}`, dados),
  removeVehicle: (id: string) => api.del<void>(`/app/vehicles/${id}`),
  myInvoices: (limit = 20) => api.get<T.Fatura[]>('/app/invoices', { limit }),
  /**
   * Credito na carteira pre-paga.
   *
   * A chave de idempotencia nasce aqui, uma por chamada, e nao na tela: se ela
   * viesse do componente, um re-render podia gerar outra e o retry deixaria de
   * ser reconhecido como o mesmo credito. O servidor tem UNIQUE nela.
   */
  topUpWallet: (amount: number, idempotencyKey = chaveDeIdempotencia()) =>
    api.post<{ wallet_balance: number }>('/app/wallet/topup', {
      amount: amount.toFixed(2),
      idempotency_key: idempotencyKey
    }),
  /**
   * O extrato da carteira: credito e debito, do mais novo ao mais antigo.
   *
   * Sempre o do proprio motorista - o dono vem do token, e nao ha parametro que
   * permita pedir o de outra pessoa.
   */
  walletStatement: (limit = 50) => api.get<T.ExtratoDaCarteira>('/app/wallet/statement', { limit })
}
