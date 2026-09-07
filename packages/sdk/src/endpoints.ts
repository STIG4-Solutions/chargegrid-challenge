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
  register: (dados: { email: string; full_name: string; password: string }) =>
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
    api.get<Array<Record<string, number | string | null>>>(`/sessions/${id}/telemetry`, { minutes }),
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
export const app = {
  stations: (params?: { latitude?: number; longitude?: number; radius_km?: number }) =>
    api.get<T.Estacao[]>('/app/stations', params),
  stationChargePoints: (siteId: string) =>
    api.get<T.PontoDaEstacao[]>(`/app/stations/${siteId}/charge-points`),
  /** Resolve o ponto pelo codigo lido no QR colado no carregador. */
  chargePointByCode: (codigo: string) =>
    api.get<T.PontoLido>(`/app/charge-points/by-code/${encodeURIComponent(codigo)}`),
  startSession: (params: { charge_point_id: string; preauth_amount?: number }) =>
    api.post<T.SessaoDetalhada>('/app/sessions', undefined, params),
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
    })
}
