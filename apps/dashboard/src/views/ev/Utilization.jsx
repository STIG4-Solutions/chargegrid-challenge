import { brl, num, power, useApi } from '@chargegrid/sdk'
import { Async } from '../../components/Async.jsx'

/**
 * Ocupação e retorno por ponto.
 *
 * As outras telas olham o site inteiro. Esta compara ponto a ponto, que é onde
 * as decisões de capital acontecem: onde instalar o próximo, qual remover, e
 * qual está ocupado sem faturar.
 *
 * A métrica principal é receita por hora DISPONÍVEL, não por hora corrida. Um
 * ponto que passou a semana em falha não é um ponto ocioso — é um ponto
 * quebrado, e as duas situações pedem ações opostas.
 */
export default function Utilization() {
  const dados = useApi(() => power.utilizationByPoint(30), [], { pollMs: 300000 })

  return (
    <Async
      loading={dados.loading}
      error={dados.error}
      data={dados.data}
      onRetry={dados.refetch}
    >
      {dados.data && <Relatorio d={dados.data} />}
    </Async>
  )
}

const ROTULOS = {
  congestionado: { texto: 'Congestionado', cor: '#d9534f', acao: 'Vive cheio — está recusando cliente. É aqui que o próximo ponto se paga.' },
  bloqueado: { texto: 'Bloqueado', cor: '#d9a441', acao: 'Ocupado sem consumir: usado como vaga. Caso para taxa de ociosidade.' },
  ocioso: { texto: 'Ocioso', cor: '#7a8699', acao: 'Pouca procura. Capital parado — avalie realocar.' },
  saudavel: { texto: 'Saudável', cor: '#3d9970', acao: 'Giro compatível com a capacidade.' },
  indisponivel: { texto: 'Indisponível', cor: '#8a2be2', acao: 'Ficou fora do ar o período todo. É manutenção, não demanda.' }
}

function Stat({ rotulo, valor, nota, destaque }) {
  return (
    <div className="stat">
      <div className="label">{rotulo}</div>
      <div className="value" style={destaque ? { color: 'var(--sems-red)' } : undefined}>{valor}</div>
      <div className="trend muted">{nota}</div>
    </div>
  )
}

/** Barra proporcional: a fatia escura é o tempo ocupado sem consumir. */
function BarraDeOcupacao({ ocupacaoPct, ociosidadePct }) {
  const util = Math.max(0, ocupacaoPct * (1 - ociosidadePct / 100))
  const ocioso = Math.max(0, ocupacaoPct - util)
  return (
    <div
      title={`${num(ocupacaoPct, 1)}% ocupado, dos quais ${num(ociosidadePct, 0)}% sem consumir`}
      style={{
        display: 'flex',
        height: 10,
        borderRadius: 5,
        overflow: 'hidden',
        background: 'var(--barra-fundo, rgba(127,127,127,0.18))',
        minWidth: 90
      }}
    >
      <div style={{ width: `${util}%`, background: '#3d9970' }} />
      <div style={{ width: `${ocioso}%`, background: '#d9a441' }} />
    </div>
  )
}

function Relatorio({ d }) {
  const pontos = d.pontos || []

  if (pontos.length === 0) {
    return (
      <div className="card">
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Ocupação e retorno por ponto</h3>
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Nenhum ponto de recarga cadastrado neste site.
        </p>
      </div>
    )
  }

  const semGiro = pontos.filter((p) => p.sessoes === 0).length

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Ocupação e retorno por ponto</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        {d.janela_completa
          ? `Últimos ${d.dias} dias.`
          : `Site em operação há ${num(d.dias_efetivos, 1)} dia(s) — a janela cobre esse período, não os ${d.dias} pedidos.`}{' '}
        O ranking é por receita a cada hora em que o ponto esteve realmente disponível —
        horas de falha saem do denominador, senão um ponto quebrado apareceria como ponto
        sem procura.
      </p>

      <div className="grid grid-3" style={{ marginBottom: 16 }}>
        <Stat
          rotulo="Receita no período"
          valor={brl(d.receita_total_brl)}
          nota={`${d.sessoes_total} sessões · ${num(d.energia_total_kwh, 0)} kWh`}
        />
        <Stat
          rotulo="Ocupação média"
          valor={`${num(d.ocupacao_media_pct, 1)}%`}
          nota={semGiro > 0 ? `${semGiro} ponto(s) sem nenhuma sessão` : 'todos os pontos giraram'}
        />
        <Stat
          rotulo="Perdido em ociosidade"
          valor={brl(d.receita_perdida_por_ociosidade_brl)}
          nota={`${num(d.horas_ociosas_total, 0)} h de conector plugado sem consumir`}
          destaque={d.receita_perdida_por_ociosidade_brl > 0}
        />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="table" style={{ minWidth: 760 }}>
          <thead>
            <tr>
              <th>Ponto</th>
              <th style={{ minWidth: 120 }}>Ocupação</th>
              <th style={{ textAlign: 'right' }}>Receita</th>
              <th style={{ textAlign: 'right' }}>R$/h disp.</th>
              <th style={{ textAlign: 'right' }}>Sessões</th>
              <th style={{ textAlign: 'right' }}>kWh/sessão</th>
              <th>Situação</th>
            </tr>
          </thead>
          <tbody>
            {pontos.map((p) => {
              const r = ROTULOS[p.classificacao] || ROTULOS.saudavel
              return (
                <tr key={p.charge_point_id}>
                  <td>
                    <strong>{p.code}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {p.name} · {num(p.rated_kw, 0)} kW
                    </div>
                  </td>
                  <td>
                    <BarraDeOcupacao
                      ocupacaoPct={p.ocupacao_pct}
                      ociosidadePct={p.ociosidade_pct}
                    />
                    <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                      {num(p.ocupacao_pct, 1)}%
                      {p.horas_indisponiveis > 0 &&
                        ` · ${num(p.horas_indisponiveis, 0)} h fora do ar`}
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>{brl(p.receita_brl)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <strong>{brl(p.receita_por_hora_brl)}</strong>
                  </td>
                  <td style={{ textAlign: 'right' }}>{p.sessoes}</td>
                  <td style={{ textAlign: 'right' }}>{num(p.energia_por_sessao_kwh, 1)}</td>
                  <td>
                    <span style={{ color: r.cor, fontWeight: 600, fontSize: 13 }}>{r.texto}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16 }}>
        <p className="muted" style={{ fontSize: 12, margin: '0 0 6px' }}>
          O que cada situação recomenda:
        </p>
        <ul className="muted" style={{ fontSize: 12, margin: 0, paddingLeft: 18 }}>
          {[...new Set(pontos.map((p) => p.classificacao))].map((c) => (
            <li key={c} style={{ marginBottom: 2 }}>
              <span style={{ color: (ROTULOS[c] || ROTULOS.saudavel).cor, fontWeight: 600 }}>
                {(ROTULOS[c] || ROTULOS.saudavel).texto}
              </span>{' '}
              — {(ROTULOS[c] || ROTULOS.saudavel).acao}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
