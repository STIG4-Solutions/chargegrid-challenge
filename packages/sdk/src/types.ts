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

/** Página genérica devolvida pelas listagens. */
export interface Pagina<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
