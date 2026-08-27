// Formatação e rótulos, compartilhados pelo painel e pelo app.
//
// Intl funciona no navegador e no Hermes (React Native) — nenhum polyfill.

export const brl = (v: unknown): string =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(v) || 0)

export const num = (v: unknown, d = 2): string =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }).format(
    Number(v) || 0
  )

// A API devolve ISO-8601 em UTC; o painel mostra no fuso do navegador.
export function dateTime(iso?: string | null, { withDate = true } = {}): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', {
    ...(withDate ? { day: '2-digit', month: '2-digit', year: 'numeric' } : {}),
    hour: '2-digit',
    minute: '2-digit'
  })
}

export function timeOnly(iso?: string | null): string {
  return dateTime(iso, { withDate: false })
}

export function duration(seconds?: number | null): string {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  return h > 0 ? `${h}h ${m}min` : `${m} min`
}

// Os rótulos abaixo espelham os enums do backend (app/models/enums.py).
export interface Rotulo {
  label: string
  cls: string
}

export const chargePointStatus: Record<string, Rotulo> = {
  available: { label: 'Disponível', cls: 'badge-blue' },
  preparing: { label: 'Preparando', cls: 'badge-yellow' },
  charging: { label: 'Carregando', cls: 'badge-green' },
  suspended: { label: 'Suspenso', cls: 'badge-yellow' },
  finishing: { label: 'Finalizando', cls: 'badge-blue' },
  reserved: { label: 'Reservado', cls: 'badge-blue' },
  faulted: { label: 'Em falha', cls: 'badge-red' },
  offline: { label: 'Offline', cls: 'badge-gray' },
  maintenance: { label: 'Manutenção', cls: 'badge-gray' }
}

export const sessionState: Record<string, Rotulo> = {
  authorizing: { label: 'Autorizando', cls: 'badge-yellow' },
  queued: { label: 'Na fila', cls: 'badge-yellow' },
  starting: { label: 'Iniciando', cls: 'badge-yellow' },
  charging: { label: 'Carregando', cls: 'badge-green' },
  suspended: { label: 'Suspensa', cls: 'badge-yellow' },
  finishing: { label: 'Encerrando', cls: 'badge-blue' },
  finished: { label: 'Finalizada', cls: 'badge-blue' },
  billed: { label: 'Faturada', cls: 'badge-green' },
  error: { label: 'Erro', cls: 'badge-red' }
}

export const invoiceStatus: Record<string, Rotulo> = {
  draft: { label: 'Rascunho', cls: 'badge-gray' },
  open: { label: 'Pendente', cls: 'badge-yellow' },
  paid: { label: 'Pago', cls: 'badge-green' },
  failed: { label: 'Falhou', cls: 'badge-red' },
  refunded: { label: 'Estornado', cls: 'badge-gray' },
  void: { label: 'Cancelada', cls: 'badge-gray' }
}

export const tariffType: Record<string, string> = {
  per_kwh: 'Por energia',
  per_time: 'Por tempo',
  time_of_use: 'Por horário (ponta/fora)',
  flat: 'Valor fixo'
}

export const paymentKind: Record<string, string> = {
  pix: 'Pix',
  credit_card: 'Cartão de crédito',
  rfid_subscription: 'Cartão RFID / assinatura',
  wallet: 'Carteira digital (app)'
}

export const stopReason: Record<string, string> = {
  queue_timeout: 'Saiu da fila por tempo de espera',
  local: 'Encerrada no ponto',
  remote: 'Encerrada remotamente',
  ev_disconnected: 'Veículo desconectado',
  energy_limit: 'Limite de energia atingido',
  time_limit: 'Limite de tempo atingido',
  amount_limit: 'Limite de valor atingido',
  power_shortage: 'Potência insuficiente',
  fault: 'Falha no equipamento',
  deauthorized: 'Autorização revogada'
}

// Fallback: enum novo no backend não pode quebrar a tela.
export const meta = (map: Record<string, Rotulo>, key?: string | null): Rotulo =>
  (key ? map[key] : undefined) ?? { label: key || '—', cls: 'badge-gray' }
