import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  chargePointStatus,
  dateTime,
  meta,
  num,
  power,
  sessions as sessionsApi,
  useAction,
  useApi,
  useSiteStream
} from '@chargegrid/sdk'
import { Async, ErrorState, Spinner } from '../../components/Async.jsx'
import { idadeEmPalavras, problemaNaResolucao, rotuloDaCategoria } from './manutencao.js'
import { alteracoesDoOrcamento, mudouPorBaixo } from './orcamento.js'

// Espelha ACTIVE_SESSION_STATES do backend: são os estados que ocupam o ponto.
// Sem 'queued' aqui, um ponto com alguém na fila mostrava "Iniciar" e o clique
// voltava 409 — o botão prometia algo que a API recusaria.
const ACTIVE_STATES = ['authorizing', 'queued', 'starting', 'charging', 'suspended', 'finishing']
const LOCKED_STATUSES = ['offline', 'faulted', 'maintenance']

export default function PowerManagement() {
  // O poller do backend varre a cada 5s; sem WebSocket, 10s de fallback bastam.
  const overview = useApi(() => power.overview(), [], { pollMs: 10000 })
  const recent = useApi(() => sessionsApi.list({ limit: 50 }), [], { pollMs: 15000 })
  const manutencao = useApi(() => power.maintenanceAttention(30), [], { pollMs: 120000 })
  const reportes = useApi(() => power.maintenanceReports(true, 100), [], { pollMs: 60000 })
  const resolver = useAction((id, resolucao) => power.resolveReport(id, resolucao), {
    onSuccess: () => {
      void reportes.refetch({ silent: true })
      // A contagem de `abertos` por categoria muda junto: sem isto, o card de
      // cima continuaria dizendo "3 abertos" com a fila já em 2.
      void manutencao.refetch({ silent: true })
    }
  })
  const stream = useSiteStream()

  // O evento do WebSocket chega antes do próximo poll: aplica na hora.
  useEffect(() => {
    if (!stream.telemetry) return
    overview.setData((current) => {
      if (!current) return current
      const live = new Map(stream.telemetry.charge_points.map((cp) => [cp.id, cp]))
      const chargePoints = current.charge_points.map((cp) => {
        const update = live.get(cp.id)
        if (!update) return cp
        return {
          ...cp,
          status: update.status,
          current_kw: update.current_kw,
          limit_kw: update.limit_kw,
          active_faults: update.faults
        }
      })
      const currentKw = chargePoints.reduce((sum, cp) => sum + Number(cp.current_kw || 0), 0)
      const available = stream.telemetry.budget.available_kw

      // Recalcula a potência alocada com a mesma regra do backend: só os pontos
      // que podem puxar energia. Carregá-la adiante sem refazer a conta deixava
      // o cartão com a soma anterior enquanto os limites por ponto, logo abaixo,
      // já mostravam os novos — e o alerta vermelho de "excede a
      // disponibilidade" ficava aceso até 10s num site que já estava dentro.
      const alocada = chargePoints
        .filter((cp) => podeReceberPotencia(cp))
        .reduce((sum, cp) => sum + Number(cp.limit_kw || 0), 0)

      return {
        ...current,
        budget: stream.telemetry.budget,
        charge_points: chargePoints,
        current_kw: Number(currentKw.toFixed(2)),
        allocated_kw: Number(alocada.toFixed(2)),
        over_budget: alocada > available,
        usage_percent: available > 0 ? Math.min(100, (currentKw / available) * 100) : 0,
        active_count: chargePoints.filter((cp) => cp.status === 'charging').length
      }
    })

    // A lista de sessões alimenta o botão de ação de cada linha, e o WebSocket
    // não a toca. Sem isto, o status da linha ficava "Carregando" enquanto o
    // botão ainda dizia "Iniciar" — e o clique tomava 409 do servidor, que é
    // exatamente o conflito que o painel deveria evitar.
    recent.refetch({ silent: true })
  }, [stream.telemetry]) // eslint-disable-line react-hooks/exhaustive-deps

  // Recarrega as duas fontes. `silent` no overview mantinha o botão sem
  // spinner e clicável durante a requisição, porque useApi só marca loading no
  // caminho não-silencioso; o Async já preserva o conteúdo enquanto há dados,
  // então o não-silencioso não pisca a tela.
  const reload = () => {
    overview.refetch()
    recent.refetch({ silent: true })
  }
  const rebalance = useAction(() => power.rebalance(false), { onSuccess: reload })

  const activeByPoint = useMemo(() => {
    const map = new Map()
    for (const session of recent.data?.items || []) {
      if (ACTIVE_STATES.includes(session.state)) map.set(session.charge_point_id, session)
    }
    return map
  }, [recent.data])

  const data = overview.data
  const budget = data?.budget

  return (
    <div>
      <div className="stream-bar">
        <StreamBadge status={stream.status} />
        <button className="btn btn-sm" onClick={reload} disabled={overview.loading}>
          {overview.loading ? <Spinner /> : null} Atualizar
        </button>
      </div>

      <Async
        loading={overview.loading}
        error={overview.error}
        data={data}
        onRetry={overview.refetch}
      >
        {data && (
          <>
            <PowerStats data={data} budget={budget} />
            <BudgetEditor settings={data.settings} onSaved={reload} />
            <BalancePanel data={data} budget={budget} rebalance={rebalance} />
            <ChargePointTable
              chargePoints={data.charge_points}
              activeByPoint={activeByPoint}
              onChanged={reload}
            />
          </>
        )}
      </Async>

      <Async
        loading={manutencao.loading}
        error={manutencao.error}
        data={manutencao.data}
        onRetry={manutencao.refetch}
      >
        {manutencao.data && <Manutencao d={manutencao.data} />}
      </Async>

      {/*
        Sem `<Async>` de propósito: uma fila que não carregou não pode esconder
        o resto da aba. Falhando, o card não aparece — e o erro de uma ação
        aparece dentro dele, onde quem clicou está olhando.
      */}
      {reportes.data && (
        <FilaDeReportes
          reportes={reportes.data}
          aoResolver={(id, texto) => resolver.run(id, texto)}
          pendente={resolver.pending}
          erro={resolver.error}
        />
      )}
    </div>
  )
}

function PowerStats({ data, budget }) {
  return (
    <div className="grid grid-4" style={{ marginBottom: 16 }}>
      <div className="stat">
        <div className="label">Potência disponível no site</div>
        <div className="value">
          {num(budget.available_kw, 1)}
          <small>kW</small>
        </div>
        <div className="trend muted">
          Rede {num(budget.grid_limit_kw, 0)} + Solar {num(budget.pv_kw, 1)} + Bateria{' '}
          {num(budget.battery_kw, 1)} − Reserva {num(budget.reserved_kw, 0)}
          {budget.booked_kw > 0 ? ` − Agendado ${num(budget.booked_kw, 1)}` : ''}
        </div>
        <MeterFreshness budget={budget} />
      </div>
      <div className="stat">
        <div className="label">Consumo atual</div>
        <div className="value">
          {num(data.current_kw, 1)}
          <small>kW</small>
        </div>
        <div
          className="trend"
          style={{ color: data.usage_percent > 90 ? 'var(--sems-red)' : 'var(--sems-green)' }}
        >
          {num(data.usage_percent, 0)}% da capacidade
        </div>
      </div>
      <div className="stat">
        <div className="label">Potência alocada (limites)</div>
        <div className="value" style={{ color: data.over_budget ? 'var(--sems-red)' : 'inherit' }}>
          {num(data.allocated_kw, 1)}
          <small>kW</small>
        </div>
        <div className={'trend ' + (data.over_budget ? 'red' : 'muted')}>
          {data.over_budget ? '⚠ Excede a disponibilidade' : 'Dentro do limite'}
        </div>
      </div>
      <div className="stat">
        <div className="label">Pontos ativos</div>
        <div className="value">
          {data.active_count}
          <small>/ {data.total_count}</small>
        </div>
        <div className="trend muted">carregando agora</div>
      </div>
    </div>
  )
}

function BalancePanel({ data, budget, rebalance }) {
  const [previa, setPrevia] = useState(null)
  // Calcula sem tocar no hardware: o operador vê o efeito antes de aplicar.
  const prever = useAction(() => power.plan(), { onSuccess: setPrevia })

  // Depois de redistribuir, a prévia vira retrato do passado. Fechá-la é mais
  // honesto que deixar números velhos na tela parecendo o estado atual.
  useEffect(() => {
    if (rebalance.pending) setPrevia(null)
  }, [rebalance.pending])

  return (
    <div className="panel" style={{ marginBottom: 16 }}>
      <div
        className="flex items-center"
        style={{ justifyContent: 'space-between', marginBottom: 10 }}
      >
        <div className="card-title" style={{ margin: 0 }}>
          Balanceamento de carga do site
        </div>
        <div className="flex items-center gap-12">
          <span className="muted" style={{ fontSize: 13 }}>
            Rateio automático a cada 15s no servidor
          </span>
          <button
            className="btn btn-sm"
            onClick={() => (previa ? setPrevia(null) : prever.run())}
            disabled={prever.pending}
          >
            {prever.pending ? <Spinner /> : null} {previa ? 'Ocultar prévia' : 'Prever rateio'}
          </button>
          <button
            className="btn btn-sm"
            onClick={() => rebalance.run()}
            disabled={rebalance.pending}
          >
            {rebalance.pending ? <Spinner /> : null} Redistribuir agora
          </button>
        </div>
      </div>
      <div className="meter">
        <div
          className="meter-fill"
          style={{
            width: Math.min(100, data.usage_percent) + '%',
            background:
              data.usage_percent > 90 ? 'var(--sems-red)' : 'linear-gradient(90deg,#34c759,#ffcc00)'
          }}
        />
      </div>
      <div className="flex" style={{ justifyContent: 'space-between', marginTop: 6 }}>
        <span className="muted" style={{ fontSize: 12 }}>
          0 kW
        </span>
        <span className="muted" style={{ fontSize: 12 }}>
          Capacidade: {num(budget.available_kw, 1)} kW
        </span>
      </div>
      <ErrorState error={rebalance.error || prever.error} compact />
      {previa && <PlanPreview plano={previa} />}
    </div>
  )
}

function PlanPreview({ plano }) {
  return (
    <div className="plan-preview">
      <div
        className="flex items-center"
        style={{ justifyContent: 'space-between', marginBottom: 8 }}
      >
        <span style={{ fontWeight: 600, fontSize: 13 }}>Prévia do rateio</span>
        <span className="muted" style={{ fontSize: 12 }}>
          {num(plano.total_granted_kw, 1)} kW de {num(plano.budget.available_kw, 1)} kW disponíveis
        </span>
      </div>
      <table className="table compact">
        <thead>
          <tr>
            <th>Ponto</th>
            <th>Prioridade</th>
            <th className="text-right">Concederia</th>
            <th>Situação</th>
          </tr>
        </thead>
        <tbody>
          {plano.allocations.map((a) => (
            <tr key={a.charge_point_id}>
              <td style={{ fontWeight: 500 }}>{a.code}</td>
              <td className="muted">{a.priority}</td>
              <td className="text-right">{num(a.granted_kw, 1)} kW</td>
              <td className="muted" style={{ fontSize: 12 }}>
                {a.suspended ? `⚠ ${a.reason || 'suspenso'}` : a.reason || 'atendido no teto'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        Cálculo sem escrita no hardware. O rateio automático aplica isso no próximo ciclo.
      </div>
    </div>
  )
}

function StreamBadge({ status }) {
  const map = {
    online: { label: 'Tempo real', cls: 'badge-green' },
    connecting: { label: 'Conectando…', cls: 'badge-yellow' },
    reconnecting: { label: 'Reconectando…', cls: 'badge-yellow' },
    offline: { label: 'Sem tempo real', cls: 'badge-gray' },
    error: { label: 'Sem tempo real', cls: 'badge-gray' },
    idle: { label: 'Tempo real desligado', cls: 'badge-gray' }
  }
  const item = map[status] || map.idle
  return <span className={'badge ' + item.cls}>{item.label}</span>
}

function ChargePointTable({ chargePoints, activeByPoint, onChanged }) {
  return (
    <div className="panel">
      <div className="card-title">Pontos de recarga</div>
      <div className="card-sub">
        O limite é escrito no registrador 10029 e vira o teto do ponto: o rateio automático
        distribui a potência disponível, mas nunca sobe acima do valor definido aqui.
        <strong> Cortar</strong> usa o registrador 10000 para derrubar o ponto à potência mínima sem
        encerrar a sessão em curso.
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Ponto</th>
            <th>Conector</th>
            <th>Status</th>
            <th>Consumo atual</th>
            <th style={{ minWidth: 240 }}>Limite de potência</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>
          {chargePoints.map((cp) => (
            <ChargePointRow
              key={cp.id}
              chargePoint={cp}
              session={activeByPoint.get(cp.id)}
              onChanged={onChanged}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChargePointRow({ chargePoint, session, onChanged }) {
  const cp = chargePoint
  const locked = LOCKED_STATUSES.includes(cp.status)
  const status = meta(chargePointStatus, cp.status)

  // O slider é local e só vira requisição ao soltar: um POST por pixel arrastado
  // encheria a fila do Modbus e travaria o eletroposto.
  const [limit, setLimit] = useState(Number(cp.limit_kw))
  const dirty = useRef(false)

  useEffect(() => {
    if (!dirty.current) setLimit(Number(cp.limit_kw))
  }, [cp.limit_kw])

  const applyLimit = useAction(() => power.setLimit(cp.id, limit), {
    onSuccess: () => {
      dirty.current = false
      onChanged()
    },
    onError: () => {
      dirty.current = false
      setLimit(Number(cp.limit_kw)) // rejeitado pelo hardware: volta ao valor real
    }
  })

  const toggle = useAction(
    async () => {
      if (session) return sessionsApi.stop(session.id)
      return sessionsApi.start({ charge_point_id: cp.id, auth_method: 'operator' })
    },
    { onSuccess: onChanged }
  )

  // Reflete a intenção gravada, não o status observado: o ponto pode estar
  // suspenso pelo orçamento sem ter sido cortado pelo operador.
  const cortado = cp.operator_throttled
  // Reg 10000: força o ponto à potência mínima sem derrubar a sessão em curso.
  const cortar = useAction(() => power.throttle(cp.id, !cortado), { onSuccess: onChanged })

  const commit = () => {
    if (!dirty.current || applyLimit.pending) return
    if (Math.abs(limit - Number(cp.limit_kw)) < 0.05) {
      dirty.current = false
      return
    }
    applyLimit.run()
  }

  const busy = applyLimit.pending || toggle.pending || cortar.pending
  const error = applyLimit.error || toggle.error || cortar.error

  return (
    <tr>
      <td>
        <div style={{ fontWeight: 600 }}>{cp.name}</div>
        <div className="muted" style={{ fontSize: 12 }}>
          {cp.code} · nominal {num(cp.rated_kw, 0)} kW · mín {num(cp.min_kw, 1)} kW
        </div>
        {session?.state === 'queued' && (
          <div className="queue-hint">Um motorista aguarda na fila deste ponto</div>
        )}
        {cp.active_faults?.length > 0 && (
          <div className="fault-list" title={cp.active_faults.join('; ')}>
            ⚠ {cp.active_faults[0]}
            {cp.active_faults.length > 1 ? ` (+${cp.active_faults.length - 1})` : ''}
          </div>
        )}
        {error && <div className="row-error">{error.detail || error.message}</div>}
      </td>
      <td>{cp.connector}</td>
      <td>
        <span className={'badge ' + status.cls}>{status.label}</span>
      </td>
      <td>{num(cp.current_kw, 1)} kW</td>
      <td>
        <div className="slider-row">
          <input
            type="range"
            min={0}
            max={Number(cp.rated_kw)}
            step="0.5"
            value={limit}
            onChange={(e) => {
              dirty.current = true
              setLimit(Number(e.target.value))
            }}
            onPointerUp={commit}
            onKeyUp={commit}
            onBlur={commit}
            disabled={locked || busy || cortado}
            className="range"
            title={cortado ? 'Ponto cortado pelo operador — libere para ajustar o teto' : undefined}
          />
          <span className="kw">
            {num(limit, 1)} kW {applyLimit.pending ? <Spinner size={12} /> : null}
          </span>
        </div>
      </td>
      <td>
        <div className="flex gap-8">
          <button className="btn btn-sm" disabled={locked || busy} onClick={() => toggle.run()}>
            {toggle.pending ? <Spinner size={12} /> : null}{' '}
            {!session ? 'Iniciar' : session.state === 'queued' ? 'Cancelar' : 'Parar'}
          </button>
          <button
            className={'btn btn-sm' + (cortado ? ' btn-primary' : '')}
            disabled={locked || busy}
            onClick={() => cortar.run()}
            title={
              cortado
                ? 'Liberar o ponto do corte de demanda (reg 10000)'
                : 'Cortar para a potência mínima sem encerrar a sessão (reg 10000)'
            }
          >
            {cortar.pending ? <Spinner size={12} /> : null} {cortado ? 'Liberar' : 'Cortar'}
          </button>
        </div>
      </td>
    </tr>
  )
}

function MeterFreshness({ budget }) {
  // Sem leitura recente do medidor, solar e bateria saem do orçamento e só a
  // rede sustenta os pontos. O operador precisa saber que é isso — e não que
  // o sol acabou — quando vê Solar 0,0.
  if (!budget.reading_stale) {
    return (
      <div className="trend muted" style={{ fontSize: 11 }}>
        Medidor lido {dateTime(budget.reading_at, { withDate: false })}
      </div>
    )
  }
  return (
    <div className="meter-stale" title="Aguardando o coletor do site enviar novas leituras">
      ⚠ Leitura do medidor desatualizada
      {budget.reading_at ? ` (${dateTime(budget.reading_at)})` : ''} — solar e bateria fora do
      orçamento
    </div>
  )
}

// `obrigatorio` espelha o NOT NULL da coluna. Um campo limpo vira null no
// rascunho, e mandar null para uma coluna NOT NULL estourava um 500 sem
// mensagem — o operador que apagasse o valor só para redigitar levava um erro
// de servidor. Só `main_breaker_current_a` aceita nulo de verdade.
// Espelha ChargePoint.is_dispatchable do backend. Se um dos lados mudar, o
// cartão de potência alocada passa a discordar da tabela logo abaixo dele.
export function podeReceberPotencia(cp) {
  if (cp.operator_throttled) return false
  return cp.enabled && (cp.status === 'charging' || cp.status === 'suspended')
}

// `obrigatorio` espelha o NOT NULL da coluna. Um campo limpo vira null no
// rascunho, e mandar null para uma coluna NOT NULL estourava um 500 sem
// mensagem — o operador que apagasse o valor só para redigitar levava um erro
// de servidor. Só `main_breaker_current_a` aceita nulo de verdade.
const CAMPOS_ORCAMENTO = [
  {
    campo: 'grid_limit_kw',
    rotulo: 'Limite da rede (kW)',
    dica: 'Capacidade contratada no ponto de entrega',
    step: 1,
    obrigatorio: true
  },
  {
    campo: 'reserved_kw',
    rotulo: 'Reserva predial (kW)',
    dica: 'Potência protegida para as cargas não-EV',
    step: 1,
    obrigatorio: true
  },
  {
    campo: 'main_breaker_current_a',
    rotulo: 'Disjuntor de entrada (A)',
    dica: 'Espelha o registrador 10026 do carregador',
    step: 1
  },
  {
    campo: 'battery_min_soc',
    rotulo: 'SOC mínimo da bateria (%)',
    dica: 'Abaixo disso a bateria não alimenta a recarga',
    step: 1,
    obrigatorio: true
  }
]

// Rótulo legível de cada chave, para o aviso de edição concorrente não dizer
// "allow_pv_kw" a quem opera o estabelecimento.
const ROTULO_ORCAMENTO = {
  ...Object.fromEntries(CAMPOS_ORCAMENTO.map((c) => [c.campo, c.rotulo])),
  allow_pv_kw: 'contar solar',
  allow_battery_kw: 'contar bateria'
}

// Campos booleanos do orçamento; entram no diff junto com os numéricos.
const CHAVES_ORCAMENTO = [
  ...CAMPOS_ORCAMENTO.map((c) => c.campo),
  'allow_pv_kw',
  'allow_battery_kw'
]

function BudgetEditor({ settings, onSaved }) {
  const [aberto, setAberto] = useState(false)
  const [rascunho, setRascunho] = useState(settings)

  // O que o operador VIU quando abriu o painel. É contra isto que o diff é
  // calculado — não contra `settings`, que continua chegando do polling.
  const baseRef = useRef(settings)

  // Enquanto o painel está fechado, acompanha o servidor; aberto, preserva a edição.
  useEffect(() => {
    if (!aberto) {
      setRascunho(settings)
      baseRef.current = settings
    }
  }, [settings, aberto])

  // Só o que este operador mexeu vai no PATCH. As regras vivem em
  // `orcamento.js` porque são a parte testável — ver o arquivo para o porquê.
  const alteracoes = alteracoesDoOrcamento(rascunho, baseRef.current, CHAVES_ORCAMENTO)
  const mudouAtras = mudouPorBaixo(settings, baseRef.current, CHAVES_ORCAMENTO, alteracoes)

  const salvar = useAction((payload) => power.updateBudget(payload), {
    onSuccess: () => {
      setAberto(false)
      onSaved()
    }
  })

  const faltando = CAMPOS_ORCAMENTO.filter(
    ({ campo, obrigatorio }) =>
      obrigatorio && (rascunho[campo] === null || rascunho[campo] === undefined)
  )

  const alterado = Object.keys(alteracoes).length > 0

  if (!aberto) {
    return (
      <div className="budget-bar">
        <span className="muted" style={{ fontSize: 13 }}>
          Rede {num(settings.grid_limit_kw, 0)} kW · reserva {num(settings.reserved_kw, 0)} kW ·
          solar {settings.allow_pv_kw ? 'no orçamento' : 'fora'} · bateria{' '}
          {settings.allow_battery_kw ? `acima de ${num(settings.battery_min_soc, 0)}%` : 'fora'}
        </span>
        <button className="btn btn-sm" onClick={() => setAberto(true)}>
          Ajustar orçamento
        </button>
      </div>
    )
  }

  return (
    <div className="panel" style={{ marginBottom: 16 }}>
      <div className="card-title">Orçamento do site</div>
      <div className="card-sub">
        Define o teto que o rateio automático distribui. Salvar recalcula e reaplica os limites nos
        pontos imediatamente.
      </div>

      <div className="grid grid-4" style={{ marginTop: 14 }}>
        {CAMPOS_ORCAMENTO.map(({ campo, rotulo, dica, step }) => (
          <div className="form-row" key={campo}>
            <label htmlFor={campo}>{rotulo}</label>
            <input
              id={campo}
              className="input"
              type="number"
              min="0"
              step={step}
              value={rascunho[campo] ?? ''}
              disabled={salvar.pending}
              onChange={(e) =>
                setRascunho({
                  ...rascunho,
                  [campo]: e.target.value === '' ? null : Number(e.target.value)
                })
              }
            />
            <span className="muted" style={{ fontSize: 11 }}>
              {dica}
            </span>
          </div>
        ))}
      </div>

      <div className="flex gap-16 items-center" style={{ marginTop: 14, flexWrap: 'wrap' }}>
        <label className="flex items-center gap-8" style={{ fontSize: 13 }}>
          <input
            type="checkbox"
            checked={rascunho.allow_pv_kw}
            disabled={salvar.pending}
            onChange={(e) => setRascunho({ ...rascunho, allow_pv_kw: e.target.checked })}
          />
          Contar geração solar no orçamento
        </label>
        <label className="flex items-center gap-8" style={{ fontSize: 13 }}>
          <input
            type="checkbox"
            checked={rascunho.allow_battery_kw}
            disabled={salvar.pending}
            onChange={(e) => setRascunho({ ...rascunho, allow_battery_kw: e.target.checked })}
          />
          Contar descarga da bateria
        </label>
      </div>

      <ErrorState error={salvar.error} compact />

      {faltando.length > 0 && (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          Preencha {faltando.map((c) => c.rotulo).join(', ')} para salvar.
        </p>
      )}

      {mudouAtras.length > 0 && (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          Outra pessoa alterou{' '}
          {mudouAtras.map((campo) => ROTULO_ORCAMENTO[campo] ?? campo).join(', ')} enquanto este
          painel estava aberto. Esses valores <strong>não</strong> serão sobrescritos — só o que
          você mudou é enviado. Feche e reabra para ver os atuais.
        </p>
      )}

      <div className="flex gap-8" style={{ marginTop: 16 }}>
        <button
          className="btn btn-primary btn-sm"
          disabled={salvar.pending || !alterado || faltando.length > 0}
          onClick={() => salvar.run(alteracoes)}
        >
          {salvar.pending ? <Spinner size={12} /> : null} Salvar e reaplicar
        </button>
        <button className="btn btn-sm" disabled={salvar.pending} onClick={() => setAberto(false)}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

/**
 * Manutenção pela recorrência, não pelo estado.
 *
 * A tabela acima mostra o que está ruim agora. Esta mostra o que vem falhando:
 * um conector que abre "falha da trava" três vezes na semana ainda funciona, e
 * não vai continuar funcionando. No instante em que se olha o painel de estado,
 * ele está normal — por isso o problema só aparece quando para.
 */
/**
 * A fila de problemas reportados por quem esteve no ponto.
 *
 * `Manutencao`, acima, agrupa por categoria e diz QUANTOS estão abertos — e
 * dizia isso desde sempre sem que nada pudesse fechá-los. Esta lista diz QUAIS,
 * e é dela que sai o trabalho de quem vai até o ponto.
 *
 * Exportada para o teste montá-la com props, sem subir a aba inteira.
 */
export function FilaDeReportes({ reportes, aoResolver, pendente, erro }) {
  const [aberto, setAberto] = useState(null)
  const [texto, setTexto] = useState('')

  const fila = reportes ?? []
  if (!fila.length) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Problemas reportados</h3>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Nenhum reporte em aberto. O que as pessoas relatam aparece aqui antes de o sensor perceber
          — cabo cortado e vaga ocupada não têm registrador.
        </p>
      </div>
    )
  }

  const problema = problemaNaResolucao(texto)

  const fechar = (id) => {
    if (problema) return
    aoResolver(id, texto.trim())
    setAberto(null)
    setTexto('')
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>
        Problemas reportados <span className="badge badge-red">{fila.length}</span>
      </h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        O que as pessoas relatam, e o sensor não vê. Fechar exige dizer o que foi feito: o próximo
        que reportar o mesmo problema precisa saber que alguém já olhou.
      </p>

      {erro && <ErrorState error={erro} compact />}

      <div style={{ overflowX: 'auto' }}>
        <table className="table" style={{ minWidth: 720 }}>
          <thead>
            <tr>
              <th>Ponto</th>
              <th>Problema</th>
              <th>Quem reportou</th>
              <th>Aberto</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {fila.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td>{r.ponto}</td>
                  <td>
                    {rotuloDaCategoria(r.categoria)}
                    {r.descricao && (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {r.descricao}
                      </div>
                    )}
                  </td>
                  <td className="muted">{r.reportado_por ?? '—'}</td>
                  <td className="muted">{idadeEmPalavras(r.reportado_em)}</td>
                  <td className="text-right">
                    <button
                      className="btn btn-sm"
                      onClick={() => {
                        setAberto(aberto === r.id ? null : r.id)
                        setTexto('')
                      }}
                    >
                      {aberto === r.id ? 'Cancelar' : 'Resolver'}
                    </button>
                  </td>
                </tr>
                {aberto === r.id && (
                  <tr>
                    <td colSpan={5}>
                      <div className="form-row">
                        <label htmlFor={`resolucao-${r.id}`}>O que foi feito</label>
                        <input
                          id={`resolucao-${r.id}`}
                          className="input"
                          value={texto}
                          onChange={(e) => setTexto(e.target.value)}
                          placeholder="Cabo trocado na manutenção de terça"
                        />
                        {/*
                          O aviso aparece enquanto se digita, e o botão fica
                          desabilitado: descobrir o piso de tamanho no 422 do
                          servidor é a mesma informação chegando tarde.
                        */}
                        {problema && (
                          <div className="muted" style={{ fontSize: 12 }}>
                            {problema}
                          </div>
                        )}
                      </div>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={Boolean(problema) || pendente}
                        onClick={() => fechar(r.id)}
                      >
                        {pendente ? 'Fechando…' : 'Fechar reporte'}
                      </button>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Manutencao({ d }) {
  if (d.sem_ocorrencias) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Manutenção preditiva</h3>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Nenhum ponto registrou falha recorrente nos últimos {d.dias} dias.
        </p>
      </div>
    )
  }

  const cor = {
    alta: 'var(--sems-red)',
    media: 'var(--sems-yellow, #ffcc00)',
    baixa: 'var(--sems-text-dim)'
  }
  const rotulo = { alta: 'Alta', media: 'Média', baixa: 'Baixa' }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Manutenção preditiva</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        {d.total_episodios} episódios em {d.dias} dias, agrupados por ponto. Vêm dos 65 bits de
        diagnóstico do carregador — a mesma fonte do estado atual, mas ao longo do tempo.
      </p>

      <table className="table">
        <thead>
          <tr>
            <th>Ponto</th>
            <th>Prioridade</th>
            <th>Episódios</th>
            <th>Sintomas</th>
          </tr>
        </thead>
        <tbody>
          {d.pontos.map((p) => (
            <tr key={p.charge_point_id}>
              <td>
                <div style={{ fontWeight: 600 }}>{p.code}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {p.name}
                </div>
              </td>
              <td>
                <span style={{ color: cor[p.prioridade], fontWeight: 600 }}>
                  {rotulo[p.prioridade]}
                </span>
                {p.tem_falha_aberta && (
                  <div className="muted" style={{ fontSize: 12 }}>
                    em curso agora
                  </div>
                )}
              </td>
              <td>{p.episodios}</td>
              <td>
                {p.sintomas.map((s) => (
                  <div key={s.label} style={{ marginBottom: 4 }}>
                    <span style={{ color: s.terminal ? 'var(--sems-red)' : 'inherit' }}>
                      {s.label}
                    </span>
                    <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>
                      {s.episodios}× · último em {dateTime(s.ultima_vez)}
                    </span>
                  </div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="muted" style={{ margin: '12px 0 0', fontSize: 12 }}>
        Prioridade alta significa que a falha já encerrou uma recarga. Média é alarme recorrente —
        ainda não parou nada, e é onde a manutenção preventiva custa menos.
      </p>
    </div>
  )
}
