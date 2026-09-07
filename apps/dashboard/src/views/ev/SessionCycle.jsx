import { useEffect, useMemo, useState } from 'react'
import { sessions as sessionsApi } from '@chargegrid/sdk'
import {
  brl,
  dateTime,
  duration,
  meta,
  num,
  sessionState,
  stopReason,
  timeOnly
} from '@chargegrid/sdk'
import { useAction, useApi } from '@chargegrid/sdk'
import { Async, Empty, ErrorState, Spinner } from '../../components/Async.jsx'

const filters = [
  { key: 'all', label: 'Todas', state: undefined },
  { key: 'charging', label: 'Em andamento', state: 'charging' },
  { key: 'queued', label: 'Na fila', state: 'queued' },
  { key: 'finished', label: 'Finalizadas', state: 'finished' },
  { key: 'billed', label: 'Faturadas', state: 'billed' },
  { key: 'error', label: 'Com erro', state: 'error' }
]

// Ordem canônica do ciclo; o backend informa o estado, aqui só posicionamos.
const CYCLE = ['Autorização', 'Início', 'Carregando', 'Encerramento', 'Faturamento']

function cycleSteps(session) {
  const reached = {
    authorizing: 1,
    // Na fila o ciclo não avança: a sessão está autorizada e aguardando folga.
    queued: 1,
    starting: 2,
    charging: 3,
    suspended: 3,
    finishing: 4,
    finished: 4,
    billed: 5,
    error: 2
  }[session.state] || 1

  return CYCLE.map((label, i) => ({
    label,
    done: i + 1 < reached,
    active: i + 1 === reached,
    error: session.state === 'error' && i + 1 === reached
  }))
}

export default function SessionCycle() {
  const [filter, setFilter] = useState('all')
  const [selectedId, setSelectedId] = useState(null)

  const active = filters.find((f) => f.key === filter)
  const list = useApi(
    () => sessionsApi.list({ state: active.state, limit: 100 }),
    [filter],
    { pollMs: 10000 }
  )
  const kpis = useApi(() => sessionsApi.kpis(), [], { pollMs: 10000 })

  const items = useMemo(() => list.data?.items || [], [list.data])

  // Mantém uma sessão selecionada quando a lista muda de filtro ou recarrega.
  useEffect(() => {
    if (items.length === 0) {
      setSelectedId(null)
      return
    }
    if (!items.some((s) => s.id === selectedId)) setSelectedId(items[0].id)
  }, [items, selectedId])

  return (
    <div>
      <Async loading={kpis.loading} error={kpis.error} data={kpis.data} onRetry={kpis.refetch}>
        {kpis.data && (
          <div className="grid grid-4" style={{ marginBottom: 16 }}>
            <div className="stat">
              <div className="label">Sessões em andamento</div>
              <div className="value" style={{ color: 'var(--sems-green)' }}>
                {kpis.data.active}
              </div>
              {kpis.data.queued > 0 && (
                <div className="trend" style={{ color: 'var(--sems-yellow)' }}>
                  {kpis.data.queued} na fila aguardando potência
                </div>
              )}
            </div>
            <div className="stat">
              <div className="label">Sessões hoje</div>
              <div className="value">{kpis.data.today}</div>
            </div>
            <div className="stat">
              <div className="label">Energia entregue (hoje)</div>
              <div className="value">
                {num(kpis.data.energy_kwh, 1)}
                <small>kWh</small>
              </div>
              <div className="trend muted">
                {num(kpis.data.green_energy_kwh, 1)} kWh de origem solar/bateria
              </div>
            </div>
            <div className="stat">
              <div className="label">Receita confirmada</div>
              <div className="value">{brl(kpis.data.confirmed_revenue)}</div>
              <div className="trend muted">{brl(kpis.data.pending_revenue)} a receber</div>
            </div>
          </div>
        )}
      </Async>

      <div className="split">
        <div className="panel">
          <div className="tabs" style={{ marginTop: 0 }}>
            {filters.map((f) => (
              <div
                key={f.key}
                className={'tab' + (filter === f.key ? ' active' : '')}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </div>
            ))}
          </div>

          <Async loading={list.loading} error={list.error} data={list.data} onRetry={list.refetch}>
            {items.length === 0 ? (
              <Empty label="Nenhuma sessão neste filtro." />
            ) : (
              <table className="table" style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th>Sessão</th>
                    <th>Estado</th>
                    <th>Energia</th>
                    <th>Duração</th>
                    <th>Custo estimado</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => {
                    const state = meta(sessionState, s.state)
                    return (
                      <tr
                        key={s.id}
                        className={'clickable' + (s.id === selectedId ? ' sel' : '')}
                        onClick={() => setSelectedId(s.id)}
                      >
                        <td>
                          <div style={{ fontWeight: 600 }}>{s.code}</div>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {dateTime(s.started_at || s.authorized_at)}
                          </div>
                        </td>
                        <td>
                          <span className={'badge ' + state.cls}>{state.label}</span>
                        </td>
                        <td>{num(s.energy_kwh, 1)} kWh</td>
                        <td>{duration(s.duration_s)}</td>
                        <td>{brl(s.estimated_cost)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </Async>
        </div>

        {/* `key` força uma instância nova a cada sessão escolhida. Sem ela o
            componente era reaproveitado e `useApi` só escreve em caso de sucesso,
            então os dados da sessão anterior ficavam na tela durante a busca da
            nova — com os botões calculados do dado velho e agindo sobre o id novo.
            Clicar em "Encerrar" nessa janela chamava stop() numa sessão já
            encerrada. */}
        {selectedId && <SessionDetail key={selectedId} sessionId={selectedId} onChanged={() => {
          list.refetch({ silent: true })
          kpis.refetch({ silent: true })
        }} />}
      </div>
    </div>
  )
}

function SessionDetail({ sessionId, onChanged }) {
  const detail = useApi(() => sessionsApi.get(sessionId), [sessionId], { pollMs: 8000 })
  // A prévia rateia o custo por janela tarifária — o valor real que está correndo.
  const preview = useApi(() => sessionsApi.preview(sessionId), [sessionId], { pollMs: 15000 })

  const reload = () => {
    detail.refetch({ silent: true })
    preview.refetch({ silent: true })
    onChanged()
  }

  const stop = useAction(() => sessionsApi.stop(sessionId), { onSuccess: reload })
  const bill = useAction(() => sessionsApi.bill(sessionId), { onSuccess: reload })

  const session = detail.data
  const canStop =
    session && ['authorizing', 'queued', 'starting', 'charging', 'suspended'].includes(session.state)
  const canBill = session && session.state === 'finished'

  return (
    <div className="panel">
      <Async loading={detail.loading} error={detail.error} data={session} onRetry={detail.refetch}>
        {session && (
          <>
            <div className="flex items-center" style={{ justifyContent: 'space-between' }}>
              <div className="card-title" style={{ margin: 0 }}>
                {session.code}
              </div>
              <span className={'badge ' + meta(sessionState, session.state).cls}>
                {meta(sessionState, session.state).label}
              </span>
            </div>
            <div className="card-sub">
              Autorização via {session.auth_method}
              {session.stop_reason ? ` · ${stopReason[session.stop_reason] || session.stop_reason}` : ''}
            </div>

            <div className="cycle">
              {cycleSteps(session).map((step, i) => (
                <div
                  key={step.label}
                  className={
                    'step' +
                    (step.done ? ' done' : '') +
                    (step.active ? ' active' : '') +
                    (step.error ? ' error' : '')
                  }
                >
                  <span className="mark">{step.error ? '✕' : step.done ? '✓' : i + 1}</span>
                  <span className="lbl">{step.label}</span>
                </div>
              ))}
            </div>

            {session.state === 'queued' && (
              <div className="queue-banner">
                <div>
                  <strong>
                    {session.queue_position
                      ? `${session.queue_position}º na fila do site`
                      : 'Na fila do site'}
                  </strong>
                  <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                    Entra sozinha assim que o rateio liberar potência. Esperando desde{' '}
                    {dateTime(session.queued_at, { withDate: false })}.
                  </div>
                </div>
              </div>
            )}

            {session.error_message && (
              <div className="row-error" style={{ marginTop: 12 }}>
                {session.error_message}
              </div>
            )}

            <hr className="hr" />

            <div className="kv">
              <div>
                <span className="muted">Início</span>
                <b>{dateTime(session.started_at)}</b>
              </div>
              <div>
                <span className="muted">Fim</span>
                <b>{dateTime(session.ended_at)}</b>
              </div>
              <div>
                <span className="muted">Duração</span>
                <b>{duration(session.duration_s)}</b>
              </div>
              <div>
                <span className="muted">Energia</span>
                <b>{num(session.energy_kwh, 2)} kWh</b>
              </div>
              <div>
                <span className="muted">Energia verde</span>
                <b>{num(session.green_energy_kwh, 2)} kWh</b>
              </div>
              <div>
                <span className="muted">Pico de potência</span>
                <b>{num(session.peak_power_kw, 1)} kW</b>
              </div>
              <div>
                <span className="muted">Ociosidade</span>
                <b>{session.idle_minutes} min</b>
              </div>
              <div>
                <span className="muted">Custo estimado</span>
                <b>{brl(session.estimated_cost)}</b>
              </div>
            </div>

            <SessionChart sessionId={sessionId} />
            <CostBreakdown preview={preview} />
            <Timeline events={session.events} />

            <div style={{ marginTop: 18 }} className="flex gap-8">
              <button
                className="btn btn-primary btn-sm"
                disabled={!canStop || stop.pending}
                onClick={() => stop.run()}
              >
                {stop.pending ? <Spinner size={12} /> : null}{' '}
                {session.state === 'queued' ? 'Sair da fila' : 'Encerrar sessão'}
              </button>
              <button className="btn btn-sm" disabled={!canBill || bill.pending} onClick={() => bill.run()}>
                {bill.pending ? <Spinner size={12} /> : null} Faturar
              </button>
            </div>
            <ErrorState error={stop.error || bill.error} compact />
          </>
        )}
      </Async>
    </div>
  )
}

function CostBreakdown({ preview }) {
  const lines = preview.data?.lines || []
  if (preview.loading && !preview.data) return null
  if (lines.length === 0) return null

  return (
    <>
      <hr className="hr" />
      <div className="card-title" style={{ fontSize: 14 }}>
        Composição do custo
      </div>
      <table className="table compact">
        <tbody>
          {/* `kind` + descrição identifica a linha melhor que a posição: o
              motor insere "mínimo" e "ociosidade" no meio conforme a sessão
              avança, e o índice então aponta para outra coisa. */}
          {lines.map((line) => (
            <tr key={`${line.kind}-${line.description}`}>
              <td>{line.description}</td>
              <td className="muted text-right">
                {num(line.quantity, 2)} {line.unit} × {brl(line.unit_price)}
              </td>
              <td className="text-right">{brl(line.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="total">
        <span className="muted">Total corrente</span>
        <span className="amount">{brl(preview.data.total)}</span>
      </div>
    </>
  )
}

function Timeline({ events }) {
  if (!events?.length) return null
  return (
    <>
      <hr className="hr" />
      <div className="card-title" style={{ fontSize: 14 }}>
        Linha do tempo
      </div>
      <ul className="timeline">
        {/* Os eventos chegam em ordem e só crescem, então o índice funcionaria
            hoje. O instante + tipo continua funcionando se algum dia deixarem
            de crescer só pelo fim. */}
        {events.map((event) => (
          <li key={`${event.occurred_at}-${event.event_type}`}>
            <span className="muted">{dateTime(event.occurred_at)}</span>
            <span>
              {event.message ||
                (event.to_state ? `${event.from_state || '—'} → ${event.to_state}` : event.event_type)}
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}

// Geometria do gráfico. viewBox fixo + largura 100%: escala sozinho, e o traço
// fica em 2px reais graças ao vector-effect.
const G = { w: 760, h: 190, top: 14, right: 14, bottom: 26, left: 44 }
const PLOT_W = G.w - G.left - G.right
const PLOT_H = G.h - G.top - G.bottom

function escalaY(valor, maximo) {
  return G.top + PLOT_H - (Math.max(0, valor) / maximo) * PLOT_H
}

// Escala do eixo em passos redondos. Dividir o pico por quatro produzia rótulos
// como 7,5 e 11,25 — números que ninguém lê como escala. Aqui o passo e o número
// de divisões são escolhidos juntos, e vence a combinação mais justa ao dado.
const PASSOS = [0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100]

function escalaDoEixo(maiorValor) {
  const alvo = Math.max(maiorValor, 1) * 1.1
  let melhor = null
  for (const divisoes of [4, 5]) {
    for (const passo of PASSOS) {
      const teto = passo * divisoes
      if (teto >= alvo && (melhor === null || teto < melhor.maximo)) {
        melhor = { maximo: teto, passo, divisoes }
      }
    }
  }
  return melhor || { maximo: Math.ceil(alvo / 100) * 100, passo: 100, divisoes: 4 }
}

function SessionChart({ sessionId }) {
  const serie = useApi(() => sessionsApi.telemetry(sessionId, 240), [sessionId], { pollMs: 12000 })
  const [ativo, setAtivo] = useState(null)

  const amostras = serie.data || []
  if (serie.loading && !serie.data) return null
  if (amostras.length < 2) {
    return (
      <>
        <hr className="hr" />
        <div className="card-title" style={{ fontSize: 14 }}>Potência entregue</div>
        <Empty label="Ainda sem amostras suficientes para o gráfico." />
      </>
    )
  }

  // O teto vem da própria telemetria e muda ao longo da sessão — é o controle de
  // demanda agindo. Traçado em degraus, ele mostra isso; uma linha fixa esconderia.
  const limites = amostras.map((a) => Number(a.limit_kw) || 0)
  const limiteAtual = limites[limites.length - 1]
  const picoSerie = Math.max(...amostras.map((a) => Number(a.power_kw) || 0))
  const eixo = escalaDoEixo(Math.max(picoSerie, ...limites))
  const maximo = eixo.maximo

  const px = (i) => G.left + (i / (amostras.length - 1)) * PLOT_W
  const pontos = amostras.map((a, i) => [px(i), escalaY(Number(a.power_kw) || 0, maximo)])
  const linha = pontos.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `${linha} L${pontos[pontos.length - 1][0].toFixed(1)},${G.top + PLOT_H} L${pontos[0][0].toFixed(1)},${G.top + PLOT_H} Z`

  // Uma linha por passo, então todo rótulo cai num número redondo.
  const marcas = Array.from({ length: eixo.divisoes + 1 }, (_, i) => i * eixo.passo)
  const casas = Number.isInteger(eixo.passo) ? 0 : 1
  const fim = pontos[pontos.length - 1]

  const degrau = limites.reduce((caminho, kw, i) => {
    const x = px(i)
    const y = escalaY(kw, maximo)
    if (i === 0) return `M${x.toFixed(1)},${y.toFixed(1)}`
    const anterior = escalaY(limites[i - 1], maximo)
    return `${caminho} L${x.toFixed(1)},${anterior.toFixed(1)} L${x.toFixed(1)},${y.toFixed(1)}`
  }, '')
  const yLimiteFim = escalaY(limiteAtual, maximo)

  function mover(evento) {
    const caixa = evento.currentTarget.getBoundingClientRect()
    const fracao = (evento.clientX - caixa.left) / caixa.width
    const i = Math.round(fracao * (amostras.length - 1))
    setAtivo(i >= 0 && i < amostras.length ? i : null)
  }

  return (
    <>
      <hr className="hr" />
      <div className="flex items-center" style={{ justifyContent: 'space-between' }}>
        <div className="card-title" style={{ fontSize: 14, margin: 0 }}>Potência entregue</div>
        <span className="muted" style={{ fontSize: 11 }}>
          pico {num(picoSerie, 1)} kW · {amostras.length} amostras
        </span>
      </div>

      <div className="chart" onMouseLeave={() => setAtivo(null)}>
        <svg viewBox={`0 0 ${G.w} ${G.h}`} role="img"
             aria-label={`Potência da sessão ao longo do tempo, pico de ${num(picoSerie, 1)} kW`}>
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-fill-top)" />
              <stop offset="100%" stopColor="var(--chart-fill-bottom)" />
            </linearGradient>
          </defs>
          {marcas.map((valor) => {
            const y = escalaY(valor, maximo)
            return (
              <g key={valor}>
                <line className="c-grid" x1={G.left} x2={G.w - G.right} y1={y} y2={y} />
                <text className="c-axis" x={G.left - 8} y={y + 3.5} textAnchor="end">
                  {num(valor, casas)}
                </text>
              </g>
            )
          })}

          <path className="c-area" d={area} />
          <path className="c-line" d={linha} vectorEffect="non-scaling-stroke" />

          {limiteAtual > 0 && (
            <>
              <path className="c-limit" d={degrau} vectorEffect="non-scaling-stroke" />
              <text className="c-limit-label" x={G.w - G.right} y={yLimiteFim - 7} textAnchor="end">
                teto {num(limiteAtual, 1)} kW
              </text>
            </>
          )}

          <circle className="c-end-ring" cx={fim[0]} cy={fim[1]} r="5.5" />
          <circle className="c-end" cx={fim[0]} cy={fim[1]} r="3.5" />

          {ativo !== null && (
            <>
              <line className="c-cross" x1={pontos[ativo][0]} x2={pontos[ativo][0]}
                    y1={G.top} y2={G.top + PLOT_H} vectorEffect="non-scaling-stroke" />
              <circle className="c-end-ring" cx={pontos[ativo][0]} cy={pontos[ativo][1]} r="5.5" />
              <circle className="c-end" cx={pontos[ativo][0]} cy={pontos[ativo][1]} r="3.5" />
            </>
          )}

          <text className="c-axis" x={G.left} y={G.h - 8}>{timeOnly(amostras[0].recorded_at)}</text>
          <text className="c-axis" x={G.w - G.right} y={G.h - 8} textAnchor="end">
            {timeOnly(amostras[amostras.length - 1].recorded_at)}
          </text>

          <rect x={G.left} y={G.top} width={PLOT_W} height={PLOT_H} fill="transparent"
                onMouseMove={mover} />
        </svg>

        {ativo !== null && (
          <div className="c-tip" style={{ left: `${(pontos[ativo][0] / G.w) * 100}%` }}>
            <strong>{num(amostras[ativo].power_kw, 1)} kW</strong>
            <span>teto {num(amostras[ativo].limit_kw, 1)} kW</span>
            <span>{num(amostras[ativo].energy_kwh, 2)} kWh acumulados</span>
            <span className="muted">{timeOnly(amostras[ativo].recorded_at)}</span>
          </div>
        )}
      </div>
    </>
  )
}
