import { num } from '@chargegrid/sdk'

/**
 * Bandeira do site: a folga de potência traduzida em preço.
 *
 * Vem de `GET /power/overview` e é trocada ao vivo pelo evento `power_plan` do
 * WebSocket. `null` é a precificação dinâmica desligada (ou o primeiro ciclo
 * ainda não rodou): aí o componente não aparece.
 */

const CLASSE = { verde: 'badge-green', amarela: 'badge-yellow', vermelha: 'badge-red' }

function hora(iso, fuso) {
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: fuso
  }).format(new Date(iso))
}

export function BandeiraDoSite({
  bandeira,
  isAdmin = false,
  demoDisponivel = false,
  picoAte = null,
  fuso = 'America/Sao_Paulo',
  onSimular,
  simulando = false
}) {
  const podeSimular = isAdmin && demoDisponivel
  // Sem bandeira (flag desligada ou antes do primeiro ciclo) o card so' existe
  // para o admin disparar o pico: e' o plano B da demo, que mostra a potencia
  // caindo mesmo sem preco dinamico.
  if (!bandeira && !podeSimular) return null
  const velha = bandeira?.desatualizada

  return (
    <div
      className="card"
      role="status"
      style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}
    >
      {bandeira && (
        <>
          <span className={`badge ${velha ? 'badge-gray' : CLASSE[bandeira.cor] || 'badge-gray'}`}>
            {velha ? 'Bandeira desatualizada' : `Bandeira ${bandeira.cor}`}
          </span>
          {!velha && (
            <>
              <strong>x{num(bandeira.multiplicador, 2)}</strong>
              <span>{num(bandeira.folga_pct, 1)}% de folga</span>
            </>
          )}
          <span style={{ color: 'var(--text-muted, #666)' }}>
            {velha
              ? 'O rebalanceador parou de atualizar. Recargas iniciadas agora pagam o preço sem bandeira.'
              : bandeira.motivo}
          </span>
        </>
      )}
      {podeSimular && (
        <span style={{ marginLeft: 'auto' }}>
          {picoAte ? (
            <span>Pico simulado até {hora(picoAte, fuso)}</span>
          ) : (
            <button className="btn btn-sm" onClick={onSimular} disabled={simulando}>
              Simular pico no prédio
            </button>
          )}
        </span>
      )}
    </div>
  )
}

/** O overview com a bandeira que o evento `power_plan` acabou de trazer. */
export function comBandeiraDoPlano(overview, plano) {
  if (!overview || !plano?.bandeira) return overview
  return { ...overview, bandeira: plano.bandeira }
}
