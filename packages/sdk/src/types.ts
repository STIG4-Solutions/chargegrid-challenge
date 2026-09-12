/**
 * Apelidos legíveis para os schemas gerados do OpenAPI.
 *
 * `schema.ts` é gerado (`npm run gen:types -w @chargegrid/sdk`) e não deve ser
 * editado à mão: ele é o contrato da API, não uma cópia dele. Este arquivo só
 * dá nomes curtos ao que os clientes usam.
 */
import type { components } from './schema'

type S = components['schemas']

// Autenticação
export type TokenPairOut = S['TokenPair']
export type Usuario = S['UserOut']
export type PapelUsuario = S['UserRole']

// Potência
export type VisaoPotencia = S['PowerOverview']
export type Orcamento = S['PowerBudgetOut']
export type ConfiguracaoSite = S['SiteSettingsOut']
export type PlanoDeRateio = S['PowerPlanOut']
export type Alocacao = S['AllocationOut']
export type PontoDeRecarga = S['ChargePointOut']
export type StatusPonto = S['ChargePointStatus']

// Sessões
export type Sessao = S['SessionOut']
export type SessaoDetalhada = S['SessionDetail']
export type EventoDaSessao = S['SessionEventOut']
export type EstadoSessao = S['SessionState']
export type KpisDeSessao = S['SessionKpis']
export type MotivoDeParada = S['StopReason']

// Tarifação e pagamento
export type Tarifa = S['TariffOut']
export type JanelaTarifaria = S['TariffWindowOut']
export type TipoTarifa = S['TariffType']
export type Precificacao = S['RatingOut']
export type LinhaDePreco = S['RatedLineOut']
export type MetodoDePagamento = S['PaymentMethodOut']
export type TipoDePagamento = S['PaymentMethodKind']
export type Fatura = S['InvoiceOut']
export type StatusFatura = S['InvoiceStatus']
export type Pagamento = S['PaymentOut']
export type ResumoDeReceita = S['RevenueSummary']

// App do motorista
export type Estacao = S['StationOut']
export type PontoDaEstacao = S['StationPointOut']
export type PontoLido = S['ScannedChargePointOut']
export type Agendamento = S['ReservationOut']
export type StatusAgendamento = S['ReservationStatus']
export type Veiculo = S['VehicleOut']
export type Missao = S['MissaoDoMotoristaOut']
export type Recompensa = S['RecompensaOut']

// Campanhas (painel do operador)
export type Campanha = S['CampanhaOut']
export type CampanhaNova = S['CampanhaIn']
export type DesempenhoDaCampanha = S['DesempenhoOut']
export type FrotaParaCampanha = S['FrotaOut']

/**
 * Um movimento da carteira. Escrito à mão, e não gerado de `schema.ts`: a rota
 * devolve `dict`, sem `response_model`, então o OpenAPI não descreve o corpo.
 *
 * A alternativa seria `Record<string, unknown>`, como em `energyForecast` — e
 * aí a tela leria campo por campo sem o `tsc` conferir nada. Um extrato de
 * dinheiro merece o tipo.
 */
export interface MovimentoDaCarteira {
  id: string
  data: string
  /** Negativo é saída. O sinal é a direção; `origem` é o motivo. */
  valor: number
  saldo_apos: number
  origem: 'topup' | 'cashback' | 'estorno' | 'ajuste' | 'pagamento'
  /** `origem` já traduzida para quem recebeu o dinheiro. */
  rotulo: string
  invoice_id: string | null
}

export interface ExtratoDaCarteira {
  /** Soma de TODOS os movimentos, não só dos que vieram nesta página. */
  saldo: number
  movimentos: MovimentoDaCarteira[]
}

/** Página genérica devolvida pelas listagens. */
export interface Pagina<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
