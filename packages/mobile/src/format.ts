/** Formatacoes que so' o app usa. O resto vem do SDK. */
export function dataCurta(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

export function dataHora(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} · ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
}

/** "hoje", "amanhã" ou a data — o que o motorista realmente quer ler. */
export function quando(iso?: string | null): string {
  if (!iso) return '—'
  const alvo = new Date(iso)
  const hoje = new Date()
  const dias = Math.round(
    (new Date(alvo.getFullYear(), alvo.getMonth(), alvo.getDate()).getTime() -
      new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()).getTime()) /
      86_400_000
  )
  const hora = alvo.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  if (dias === 0) return `hoje às ${hora}`
  if (dias === 1) return `amanhã às ${hora}`
  if (dias === -1) return `ontem às ${hora}`
  return `${alvo.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} às ${hora}`
}

export const statusAgendamento: Record<string, { label: string; cor: 'verde' | 'ambar' | 'fraco' }> = {
  confirmed: { label: 'Confirmado', cor: 'verde' },
  consumed: { label: 'Utilizado', cor: 'fraco' },
  cancelled: { label: 'Cancelado', cor: 'fraco' },
  expired: { label: 'Expirado', cor: 'ambar' }
}

export const statusFatura: Record<string, { label: string; cor: 'verde' | 'ambar' | 'vermelho' | 'fraco' }> = {
  draft: { label: 'Rascunho', cor: 'fraco' },
  open: { label: 'Em aberto', cor: 'ambar' },
  paid: { label: 'Paga', cor: 'verde' },
  failed: { label: 'Falhou', cor: 'vermelho' },
  refunded: { label: 'Estornada', cor: 'fraco' },
  void: { label: 'Cancelada', cor: 'fraco' }
}
