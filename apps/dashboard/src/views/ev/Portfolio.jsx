import { brl, num, power, useApi } from '@chargegrid/sdk'
import { Async } from '../../components/Async.jsx'

/**
 * Visão de rede: as praças lado a lado.
 *
 * Todo o resto do painel opera dentro de um site — é assim que o operador
 * trabalha e é assim que o isolamento se sustenta. Esta tela responde a
 * pergunta que nenhuma tela de site responde: qual praça segura a operação, e
 * para onde vai o próximo ponto.
 *
 * O ranking é por receita por ponto, não por total. Uma praça de dez pontos
 * fatura mais que uma de dois quase por definição; ordenar pelo total faria a
 * tela sempre recomendar investir onde já se investiu.
 */
export default function Portfolio() {
  const rede = useApi(() => power.portfolio(30), [], { pollMs: 300000 })

  return (
    <Async loading={rede.loading} error={rede.error} data={rede.data} onRetry={rede.refetch}>
      {rede.data && <Rede d={rede.data} />}
    </Async>
  )
}

function Stat({ rotulo, valor, nota, destaque }) {
  return (
    <div className="stat">
      <div className="label">{rotulo}</div>
      <div className="value" style={destaque ? { color: 'var(--sems-red)' } : undefined}>
        {valor}
      </div>
      <div className="trend muted">{nota}</div>
    </div>
  )
}

function Rede({ d }) {
  const sites = d.sites || []
  const t = d.totais || {}

  if (sites.length === 0) {
    return (
      <div className="card">
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Visão de rede</h3>
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Nenhuma praça cadastrada.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Visão de rede</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        Últimos {d.dias} dias, {t.sites} praça(s). A ordem é por receita <strong>por ponto</strong>:
        comparar totais premiaria a praça maior por ser maior.
      </p>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat
          rotulo="Receita da rede"
          valor={brl(t.receita_brl)}
          nota={`${num(t.energia_kwh, 0)} kWh entregues`}
        />
        <Stat rotulo="Pontos" valor={t.pontos} nota={`${t.sessoes_ativas} sessão(ões) agora`} />
        <Stat
          rotulo="Disponibilidade"
          valor={`${num(t.disponibilidade_pct, 1)}%`}
          nota={`${t.pontos_em_falha} ponto(s) fora do ar`}
          destaque={t.disponibilidade_pct < 90}
        />
        <Stat
          rotulo="Falhas abertas"
          valor={t.falhas_abertas}
          nota={t.falhas_abertas > 0 ? 'episódios ainda não resolvidos' : 'nenhuma pendente'}
          destaque={t.falhas_abertas > 0}
        />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="table" style={{ minWidth: 820 }}>
          <thead>
            <tr>
              <th>Praça</th>
              <th style={{ textAlign: 'right' }}>Pontos</th>
              <th style={{ textAlign: 'right' }}>Agora</th>
              <th style={{ textAlign: 'right' }}>Receita</th>
              <th style={{ textAlign: 'right' }}>R$/ponto</th>
              <th style={{ textAlign: 'right' }}>Energia</th>
              <th style={{ textAlign: 'right' }}>Disponível</th>
            </tr>
          </thead>
          <tbody>
            {sites.map((s) => (
              <tr key={s.site_id}>
                <td>
                  <strong>{s.nome}</strong>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {[s.cidade, s.estado].filter(Boolean).join('/') || s.timezone}
                    {s.grid_limit_kw > 0 && ` · ${num(s.grid_limit_kw, 0)} kW contratados`}
                  </div>
                </td>
                <td style={{ textAlign: 'right' }}>
                  {s.pontos}
                  {s.pontos_em_falha > 0 && (
                    <div style={{ color: 'var(--sems-red)', fontSize: 12 }}>
                      {s.pontos_em_falha} fora
                    </div>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>{s.sessoes_ativas}</td>
                <td style={{ textAlign: 'right' }}>{brl(s.receita_brl)}</td>
                <td style={{ textAlign: 'right' }}>
                  <strong>{brl(s.receita_por_ponto_brl)}</strong>
                </td>
                <td style={{ textAlign: 'right' }}>{num(s.energia_kwh, 0)} kWh</td>
                <td style={{ textAlign: 'right' }}>
                  <span
                    style={
                      s.disponibilidade_pct < 90
                        ? { color: 'var(--sems-red)', fontWeight: 600 }
                        : undefined
                    }
                  >
                    {num(s.disponibilidade_pct, 0)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted" style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}>
        Use o seletor de praça no topo para abrir qualquer uma delas nas demais telas.
      </p>
    </div>
  )
}
