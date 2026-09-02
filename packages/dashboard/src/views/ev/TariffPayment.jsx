import { useEffect, useRef, useState } from 'react'
import { payments, tariffs as tariffsApi } from '@chargegrid/sdk'
import {
  brl,
  dateTime,
  invoiceStatus,
  meta,
  num,
  paymentKind,
  tariffType
} from '@chargegrid/sdk'
import { useAction, useApi } from '@chargegrid/sdk'
import { Async, Empty, ErrorState, Spinner } from '../../components/Async.jsx'

export default function TariffPayment() {
  const tariffs = useApi(() => tariffsApi.list(), [])
  const methods = useApi(() => payments.listMethods(), [])
  const invoices = useApi(() => payments.listInvoices({ limit: 20 }), [], { pollMs: 20000 })
  const revenue = useApi(() => payments.revenueSummary(30), [], { pollMs: 30000 })

  return (
    <div>
      <Async loading={revenue.loading} error={revenue.error} data={revenue.data} onRetry={revenue.refetch}>
        {revenue.data && <RevenueStats summary={revenue.data} />}
      </Async>

      <TariffTable tariffs={tariffs} />

      <div className="grid grid-2">
        <PaymentMethods methods={methods} />
        <Simulator tariffs={tariffs.data || []} />
      </div>

      <Invoices
        invoices={invoices}
        onPaid={() => {
          invoices.refetch({ silent: true })
          revenue.refetch({ silent: true })
        }}
      />
    </div>
  )
}

function RevenueStats({ summary }) {
  return (
    <div className="grid grid-4" style={{ marginBottom: 16 }}>
      <div className="stat">
        <div className="label">Receita bruta (30 dias)</div>
        <div className="value">{brl(summary.gross)}</div>
        <div className="trend muted">{summary.paid_invoices} faturas pagas</div>
      </div>
      <div className="stat">
        <div className="label">Receita líquida</div>
        <div className="value" style={{ color: 'var(--sems-green)' }}>
          {brl(summary.net)}
        </div>
        <div className="trend muted">{brl(summary.processing_fees)} em taxas de adquirente</div>
      </div>
      <div className="stat">
        <div className="label">Ticket médio</div>
        <div className="value">{brl(summary.average_ticket)}</div>
        <div className="trend muted">{num(summary.energy_kwh, 1)} kWh no período</div>
      </div>
      <div className="stat">
        <div className="label">Pendências</div>
        <div className="value">{summary.open_invoices}</div>
        <div className={'trend ' + (summary.failed_invoices > 0 ? 'red' : 'muted')}>
          {summary.failed_invoices} com falha de pagamento
        </div>
      </div>
    </div>
  )
}

function TariffTable({ tariffs }) {
  const [criando, setCriando] = useState(false)
  const [editandoJanelas, setEditandoJanelas] = useState(null)
  const recarregar = () => tariffs.refetch({ silent: true })
  const emEdicao = (tariffs.data || []).find((t) => t.id === editandoJanelas)

  return (
    <div className="panel" style={{ marginBottom: 16 }}>
      <div className="flex items-center" style={{ justifyContent: 'space-between' }}>
        <div>
          <div className="card-title" style={{ margin: 0 }}>
            Políticas de tarifação
          </div>
          <div className="card-sub" style={{ margin: '4px 0 0' }}>
            Preços por energia (kWh), por tempo e taxa de ociosidade. Alterações são gravadas na
            API e valem para as próximas sessões — faturas já emitidas mantêm o preço da época.
          </div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setCriando((v) => !v)}>
          {criando ? 'Cancelar' : '+ Nova tarifa'}
        </button>
      </div>

      {criando && <NewTariff onCreated={recarregar} onClose={() => setCriando(false)} />}

      <Async loading={tariffs.loading} error={tariffs.error} data={tariffs.data} onRetry={tariffs.refetch}>
        {tariffs.data?.length === 0 ? (
          <Empty label="Nenhuma tarifa cadastrada." />
        ) : (
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Tarifa</th>
                <th>Tipo</th>
                <th>Janelas</th>
                <th>R$/kWh</th>
                <th>R$/min</th>
                <th>Ociosidade R$/min</th>
                <th>Ativa</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(tariffs.data || []).map((tariff) => (
                <TariffRow
                  key={tariff.id}
                  tariff={tariff}
                  onSaved={recarregar}
                  editandoJanelas={editandoJanelas === tariff.id}
                  onEditWindows={() =>
                    setEditandoJanelas((atual) => (atual === tariff.id ? null : tariff.id))
                  }
                />
              ))}
            </tbody>
          </table>
        )}
      </Async>

      {emEdicao && (
        <WindowEditor
          key={emEdicao.id}
          tariff={emEdicao}
          onSaved={recarregar}
          onClose={() => setEditandoJanelas(null)}
        />
      )}
    </div>
  )
}

function TariffRow({ tariff, onSaved, onEditWindows, editandoJanelas }) {
  const [confirmando, setConfirmando] = useState(false)
  // A API recusa excluir tarifa já aplicada em sessão — o histórico de cobrança
  // perderia a referência. A mensagem dela explica o caminho (desativar).
  const excluir = useAction(() => tariffsApi.remove(tariff.id), {
    onSuccess: () => {
      setConfirmando(false)
      onSaved()
    }
  })
  const [draft, setDraft] = useState(tariff)

  // Acompanha o servidor apenas enquanto esta linha não está sendo editada.
  //
  // `recarregar()` roda depois da alteração de QUALQUER linha e devolve objetos
  // novos para todas, então este efeito disparava aqui também — e uma edição
  // ainda não confirmada era substituída pelo valor do servidor sem aviso. Quem
  // digitava um preço na linha 1 e mexia no interruptor da linha 2 perdia o que
  // tinha escrito.
  // O guarda adia, não descarta.
  //
  // Ignorar a atualização enquanto o campo está focado protegia a edição, mas
  // o efeito não voltava a rodar depois do blur — as demais colunas da linha
  // ficavam com o valor de antes do refresh até a próxima mudança. Guardando o
  // que chegou, o blur reaplica o que foi pulado, preservando só o campo que
  // estava sendo editado.
  // O efeito depende só de `tariff`, de propósito.
  //
  // Ter `editando` nas dependências fazia o efeito rodar de novo no blur — e aí
  // ele desfazia a mesclagem que `encerrarEdicao` tinha acabado de aplicar,
  // devolvendo o valor do servidor por cima do que foi digitado. A mesclagem
  // virava código morto: o campo voltava sozinho enquanto o PATCH corria, e se
  // ele falhasse o valor digitado sumia de vez.
  //
  // O sinalizador é ref e não estado justamente para não entrar em dependência.
  const editandoRef = useRef(null)
  const pendenteRef = useRef(null)

  useEffect(() => {
    if (editandoRef.current) {
      // Guarda para reaplicar no blur, em vez de descartar.
      pendenteRef.current = tariff
      return
    }
    setDraft(tariff)
  }, [tariff])

  // Só preserva campo que foi realmente digitado.
  //
  // Focar sem alterar também marcava o campo como "em edição": se uma alteração
  // concorrente chegasse nesse intervalo, o merge devolvia o valor antigo por
  // cima dela e o commit seguinte a desfazia com um PATCH — revertendo em
  // silêncio o que outra pessoa acabou de salvar.
  const sujoRef = useRef(false)

  const encerrarEdicao = (campo) => {
    editandoRef.current = null
    const chegou = pendenteRef.current
    const digitou = sujoRef.current
    pendenteRef.current = null
    sujoRef.current = false
    if (!chegou) return
    // Sem digitação, o que chegou do servidor vale inteiro.
    setDraft(digitou ? (atual) => ({ ...chegou, [campo]: atual[campo] }) : chegou)
  }

  const save = useAction((payload) => tariffsApi.update(tariff.id, payload), { onSuccess: onSaved })

  // Só grava quando o campo perde o foco: cada tecla digitada não vira um PATCH.
  const commit = (field) => {
    const value = Number(draft[field])
    if (Number.isNaN(value) || value === Number(tariff[field])) return
    save.run({ [field]: value })
  }

  const priceInput = (field) => (
    <input
      className="mini"
      type="number"
      step="0.01"
      min="0"
      value={draft[field]}
      disabled={save.pending}
      onFocus={() => { editandoRef.current = field }}
      onChange={(e) => { sujoRef.current = true; setDraft({ ...draft, [field]: e.target.value }) }}
      onBlur={() => { encerrarEdicao(field); commit(field) }}
      onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
    />
  )

  return (
    <tr>
      <td style={{ fontWeight: 600 }}>
        {tariff.name}
        {save.pending ? <Spinner size={12} /> : null}
        {save.error && <div className="row-error">{save.error.detail}</div>}
      </td>
      <td className="muted">{tariffType[tariff.type] || tariff.type}</td>
      <td className="muted" style={{ fontSize: 12 }}>
        {tariff.windows?.length
          ? tariff.windows
              .map((w) => `${w.label || 'janela'} ${w.starts_at.slice(0, 5)}–${w.ends_at.slice(0, 5)}`)
              .join(' · ')
          : '24h'}
      </td>
      <td>{priceInput('price_per_kwh')}</td>
      <td>{priceInput('price_per_min')}</td>
      <td>{priceInput('idle_fee_per_min')}</td>
      <td>
        <label className="switch">
          <input
            type="checkbox"
            checked={draft.active}
            disabled={save.pending}
            onChange={(e) => {
              setDraft({ ...draft, active: e.target.checked })
              save.run({ active: e.target.checked })
            }}
          />
          <span className="slider" />
        </label>
      </td>
      <td>
        <div className="flex gap-8">
          <button
            className={'btn btn-sm' + (editandoJanelas ? ' btn-primary' : '')}
            onClick={onEditWindows}
          >
            Janelas
          </button>
          {confirmando ? (
            <>
              <button
                className="btn btn-sm btn-primary"
                disabled={excluir.pending}
                onClick={() => excluir.run()}
              >
                {excluir.pending ? <Spinner size={12} /> : null} Confirmar
              </button>
              <button
                className="btn btn-sm"
                disabled={excluir.pending}
                onClick={() => {
                  setConfirmando(false)
                  excluir.clearError()
                }}
              >
                Não
              </button>
            </>
          ) : (
            <button className="btn btn-sm" title="Excluir tarifa" onClick={() => setConfirmando(true)}>
              Excluir
            </button>
          )}
        </div>
        {excluir.error && <div className="row-error">{excluir.error.detail}</div>}
      </td>
    </tr>
  )
}

function PaymentMethods({ methods }) {
  return (
    <div className="panel">
      <div className="card-title">Métodos de pagamento</div>
      <div className="card-sub">
        Formas aceitas nos pontos e a taxa do adquirente, descontada da receita líquida.
      </div>
      <Async loading={methods.loading} error={methods.error} data={methods.data} onRetry={methods.refetch}>
        {(methods.data || []).map((method) => (
          <MethodRow key={method.id} method={method} onSaved={() => methods.refetch({ silent: true })} />
        ))}
      </Async>
    </div>
  )
}

function MethodRow({ method, onSaved }) {
  const toggle = useAction(
    (enabled) =>
      payments.upsertMethod({
        kind: method.kind,
        label: method.label,
        enabled,
        fee_percent: method.fee_percent,
        fee_fixed: method.fee_fixed,
        provider: method.provider
      }),
    { onSuccess: onSaved }
  )

  return (
    <div className="pm">
      <div>
        <div style={{ fontWeight: 500 }}>{paymentKind[method.kind] || method.label}</div>
        <div className="muted" style={{ fontSize: 12 }}>
          Taxa: {num(method.fee_percent, 2)}%
          {Number(method.fee_fixed) > 0 ? ` + ${brl(method.fee_fixed)}` : ''} · provedor{' '}
          {method.provider}
        </div>
        {toggle.error && <div className="row-error">{toggle.error.detail}</div>}
      </div>
      <label className="switch">
        <input
          type="checkbox"
          checked={method.enabled}
          disabled={toggle.pending}
          onChange={(e) => toggle.run(e.target.checked)}
        />
        <span className="slider" />
      </label>
    </div>
  )
}

function Simulator({ tariffs }) {
  const [form, setForm] = useState({ tariff_id: '', energy_kwh: 20, minutes: 45, idle_minutes: 0 })
  const [result, setResult] = useState(null)

  // Assim que as tarifas chegam, seleciona a primeira para o campo não ficar vazio.
  useEffect(() => {
    if (!form.tariff_id && tariffs.length > 0) setForm((f) => ({ ...f, tariff_id: tariffs[0].id }))
  }, [tariffs, form.tariff_id])

  // Descarta resposta fora de ordem.
  //
  // `useAction` não tem a guarda de request-id que o `useApi` tem, e o timer
  // só era limpo — a requisição já em voo seguia. Digitar 20 e depois 200:
  // se a de 20 kWh voltasse depois, o painel exibia o total de 20 sob os
  // campos de 200, apresentado como "calculado pelo motor de tarifação da API".
  const pedidoRef = useRef(0)

  // Resultado e erro passam pela mesma guarda de ordem.
  //
  // Só o sucesso estava protegido; `useAction` grava `error` em qualquer
  // rejeição, e a tela troca o resultado inteiro por <ErrorState> quando ele
  // existe. Uma requisição antiga que falhasse depois de uma nova ter dado
  // certo apagava o valor bom e mostrava um erro sem relação com a tela.
  //
  // A ação não rejeita: devolve o desfecho junto do id, e quem chegou atrasado
  // é descartado inteiro — sucesso ou falha.
  const [erroCorrente, setErroCorrente] = useState(null)

  const simulate = useAction(
    (id) =>
      tariffsApi
        .simulate(form)
        .then((r) => ({ id, r, erro: null }))
        .catch((erro) => ({ id, r: null, erro })),
    {
      onSuccess: ({ id, r, erro }) => {
        if (id !== pedidoRef.current) return
        setErroCorrente(erro)
        if (r) setResult(r)
      }
    }
  )

  // O cálculo roda no servidor, com as mesmas regras que faturam de verdade —
  // o simulador não pode divergir da cobrança real.
  // O atraso de 300ms evita uma requisição por tecla digitada nos campos numéricos.
  useEffect(() => {
    if (!form.tariff_id) return undefined
    const timer = setTimeout(() => simulate.run(++pedidoRef.current), 300)
    return () => clearTimeout(timer)
  }, [form.tariff_id, form.energy_kwh, form.minutes, form.idle_minutes]) // eslint-disable-line react-hooks/exhaustive-deps

  const number = (field) => (
    <input
      className="input"
      type="number"
      min="0"
      value={form[field]}
      onChange={(e) => setForm({ ...form, [field]: Number(e.target.value) })}
    />
  )

  return (
    <div className="panel">
      <div className="card-title">Simulador de custo</div>
      <div className="card-sub">
        Estimativa calculada pelo motor de tarifação da API, incluindo janela horária vigente.
      </div>

      <div className="form-row">
        <label>Tarifa</label>
        <select
          className="input"
          value={form.tariff_id}
          onChange={(e) => setForm({ ...form, tariff_id: e.target.value })}
        >
          {tariffs.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-3">
        <div className="form-row">
          <label>Energia (kWh)</label>
          {number('energy_kwh')}
        </div>
        <div className="form-row">
          <label>Tempo (min)</label>
          {number('minutes')}
        </div>
        <div className="form-row">
          <label>Ocioso (min)</label>
          {number('idle_minutes')}
        </div>
      </div>

      <hr className="hr" />

      {erroCorrente ? (
        <ErrorState error={erroCorrente} compact />
      ) : (
        <>
          <div className="total">
            <span className="muted">Total estimado {simulate.pending ? <Spinner size={12} /> : null}</span>
            <span className="amount">{brl(result?.total)}</span>
          </div>
          {result?.lines?.length > 0 && (
            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {result.lines.map((line) => `${line.description}: ${brl(line.amount)}`).join(' · ')}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Invoices({ invoices, onPaid }) {
  const items = invoices.data?.items || []

  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <div className="card-title">Faturas recentes</div>
      <div className="card-sub">
        Cobranças geradas automaticamente ao encerrar uma sessão de recarga.
      </div>
      <Async loading={invoices.loading} error={invoices.error} data={invoices.data} onRetry={invoices.refetch}>
        {items.length === 0 ? (
          <Empty label="Nenhuma fatura emitida ainda. Encerre uma sessão para gerar a primeira." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Fatura</th>
                <th>Itens</th>
                <th>Valor</th>
                <th>Líquido</th>
                <th>Status</th>
                <th>Emissão</th>
                <th>Cobrança</th>
              </tr>
            </thead>
            <tbody>
              {items.map((invoice) => (
                <InvoiceRow key={invoice.id} invoice={invoice} onPaid={onPaid} />
              ))}
            </tbody>
          </table>
        )}
      </Async>
    </div>
  )
}

function InvoiceRow({ invoice, onPaid }) {
  const status = meta(invoiceStatus, invoice.status)
  const [method, setMethod] = useState('pix')

  // Uma chave por TENTATIVA, não por fatura.
  //
  // A chave existe para o duplo clique: as duas chamadas levam a mesma e o
  // backend devolve o mesmo pagamento em vez de cobrar duas vezes. Mas ela era
  // `inv-<id>-<método>` — constante. Como o botão reaparece depois de uma
  // recusa (canCharge inclui 'failed'), a segunda tentativa reencontrava a
  // chave e o backend devolvia o pagamento FALHO anterior sem sequer falar com
  // o provedor: o clique não fazia nada e não explicava por quê.
  //
  // Agora a chave nasce na primeira tentativa e só é descartada quando aquela
  // tentativa termina sem sucesso — então o duplo clique continua protegido e
  // a retentativa é uma cobrança de verdade.
  const chaveRef = useRef(null)

  const charge = useAction(
    () => {
      chaveRef.current ??= `inv-${invoice.id}-${method}-${Date.now().toString(36)}`
      return payments.charge(invoice.id, method, chaveRef.current)
    },
    {
      onSuccess: (pagamento) => {
        // Recusa volta como 201 com status 'failed', não como erro HTTP.
        if (pagamento?.status !== 'captured' && pagamento?.status !== 'authorized') {
          chaveRef.current = null
        }
        onPaid()
      },
      onError: () => {
        chaveRef.current = null
      }
    }
  )

  // Trocar de método é outra tentativa, não a mesma.
  useEffect(() => {
    chaveRef.current = null
  }, [method])

  const payment = invoice.payments?.[0]
  const canCharge = invoice.status === 'open' || invoice.status === 'failed'

  return (
    <tr>
      <td style={{ fontWeight: 600 }}>
        {invoice.code}
        {charge.error && <div className="row-error">{charge.error.detail}</div>}
        {payment?.qr_code && (
          <div className="muted pix-code" title={payment.qr_code}>
            Pix copia-e-cola gerado
          </div>
        )}
      </td>
      <td className="muted" style={{ fontSize: 12 }}>
        {(invoice.lines || []).map((line) => line.description).join(' · ') || '—'}
      </td>
      <td>{brl(invoice.total)}</td>
      <td className="muted">{brl(invoice.net_amount)}</td>
      <td>
        <span className={'badge ' + status.cls}>{status.label}</span>
      </td>
      <td className="muted">{invoice.issued_on}</td>
      <td>
        {canCharge ? (
          <div className="flex gap-8 items-center">
            <select
              className="input mini-select"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              disabled={charge.pending}
            >
              <option value="pix">Pix</option>
              <option value="credit_card">Cartão</option>
              <option value="wallet">Carteira</option>
            </select>
            <button className="btn btn-sm btn-primary" onClick={() => charge.run()} disabled={charge.pending}>
              {charge.pending ? <Spinner size={12} /> : null} Cobrar
            </button>
          </div>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>
            {invoice.paid_at ? dateTime(invoice.paid_at) : '—'}
          </span>
        )}
      </td>
    </tr>
  )
}

// bit0 = segunda ... bit6 = domingo, igual à máscara do backend.
const DIAS = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D']
const NOMES_DIAS = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']
const TODOS_OS_DIAS = 0b1111111

function janelaVazia() {
  return {
    label: 'Nova janela',
    day_mask: TODOS_OS_DIAS,
    starts_at: '18:00',
    ends_at: '21:00',
    price_per_kwh: 0,
    price_per_min: 0,
    idle_fee_per_min: 0
  }
}

function WindowEditor({ tariff, onSaved, onClose }) {
  const [janelas, setJanelas] = useState(() =>
    (tariff.windows || []).map((w) => ({
      label: w.label || '',
      day_mask: w.day_mask,
      starts_at: (w.starts_at || '00:00').slice(0, 5),
      ends_at: (w.ends_at || '00:00').slice(0, 5),
      price_per_kwh: Number(w.price_per_kwh),
      price_per_min: Number(w.price_per_min),
      idle_fee_per_min: Number(w.idle_fee_per_min)
    }))
  )

  const salvar = useAction(
    () =>
      tariffsApi.replaceWindows(
        tariff.id,
        janelas.map((j) => ({ ...j, starts_at: `${j.starts_at}:00`, ends_at: `${j.ends_at}:00` }))
      ),
    { onSuccess: () => { onSaved(); onClose() } }
  )

  const editar = (i, campo, valor) =>
    setJanelas((atual) => atual.map((j, k) => (k === i ? { ...j, [campo]: valor } : j)))
  const alternarDia = (i, bit) =>
    editar(i, 'day_mask', janelas[i].day_mask ^ (1 << bit))

  // Um instante sem janela cai no preço base da tarifa em silêncio — vale avisar.
  const semCobertura = janelas.length > 0 && janelas.every((j) => j.day_mask === 0)

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div className="card-title" style={{ fontSize: 15 }}>Janelas de {tariff.name}</div>
      <div className="card-sub">
        A primeira janela que casar com o horário vence. Se nenhuma casar, vale o preço base da
        tarifa — cheque se a cobertura fecha a semana inteira, inclusive o fim de semana.
      </div>

      <div className="window-row window-head" style={{ marginTop: 12 }}>
        <span>Rótulo</span><span>Início</span><span>Fim</span>
        <span>R$/kWh</span><span>R$/min</span><span>Ocioso</span><span>Dias</span>
      </div>

      {janelas.map((j, i) => (
        <div className="window-row" key={i}>
          <input className="input" value={j.label} placeholder="Ponta"
                 onChange={(e) => editar(i, 'label', e.target.value)} />
          <input className="input" type="time" value={j.starts_at}
                 onChange={(e) => editar(i, 'starts_at', e.target.value)} />
          <input className="input" type="time" value={j.ends_at}
                 onChange={(e) => editar(i, 'ends_at', e.target.value)} />
          <input className="input" type="number" step="0.01" min="0" value={j.price_per_kwh}
                 onChange={(e) => editar(i, 'price_per_kwh', Number(e.target.value))} />
          <input className="input" type="number" step="0.01" min="0" value={j.price_per_min}
                 onChange={(e) => editar(i, 'price_per_min', Number(e.target.value))} />
          <input className="input" type="number" step="0.01" min="0" value={j.idle_fee_per_min}
                 onChange={(e) => editar(i, 'idle_fee_per_min', Number(e.target.value))} />
          <div className="flex gap-8 items-center">
            <div className="day-picker">
              {DIAS.map((letra, bit) => (
                <button key={bit} type="button" title={NOMES_DIAS[bit]}
                        className={(j.day_mask >> bit) & 1 ? 'on' : ''}
                        onClick={() => alternarDia(i, bit)}>
                  {letra}
                </button>
              ))}
            </div>
            <button className="btn btn-sm" title="Remover janela"
                    onClick={() => setJanelas((a) => a.filter((_, k) => k !== i))}>
              ✕
            </button>
          </div>
        </div>
      ))}

      {janelas.length === 0 && (
        <Empty label="Sem janelas: a tarifa cobra o preço base o tempo todo." />
      )}
      {semCobertura && (
        <div className="row-error" style={{ maxWidth: 'none' }}>
          Nenhuma janela tem dia marcado — todas as sessões cairão no preço base.
        </div>
      )}
      <ErrorState error={salvar.error} compact />

      <div className="flex gap-8" style={{ marginTop: 14 }}>
        <button className="btn btn-primary btn-sm" disabled={salvar.pending}
                onClick={() => salvar.run()}>
          {salvar.pending ? <Spinner size={12} /> : null} Salvar janelas
        </button>
        <button className="btn btn-sm" disabled={salvar.pending}
                onClick={() => setJanelas((a) => [...a, janelaVazia()])}>
          + Adicionar janela
        </button>
        <button className="btn btn-sm" disabled={salvar.pending} onClick={onClose}>
          Fechar
        </button>
      </div>
    </div>
  )
}

// O motor de tarifação cobra pelos componentes de preço, não pelo tipo — o tipo
// é rótulo. Por isso trocar o tipo aqui zera os componentes que não pertencem a
// ele: sem isso uma tarifa "Por tempo" saía com R$/kWh preenchido e cobrava os
// dois, entregando ao operador um modelo diferente do que ele escolheu.
const TIPOS_TARIFA = [
  {
    valor: 'per_kwh',
    rotulo: 'Por energia (R$/kWh)',
    precos: { price_per_kwh: 1.4, price_per_min: 0, session_fee: 0 }
  },
  {
    valor: 'time_of_use',
    rotulo: 'Por horário (ponta / fora de ponta)',
    precos: { price_per_kwh: 1.4, price_per_min: 0, session_fee: 0 }
  },
  {
    valor: 'per_time',
    rotulo: 'Por tempo (R$/min)',
    precos: { price_per_kwh: 0, price_per_min: 0.35, session_fee: 0 }
  },
  {
    valor: 'flat',
    rotulo: 'Valor fixo por sessão',
    precos: { price_per_kwh: 0, price_per_min: 0, session_fee: 10 }
  }
]

const AJUDA_TIPO = {
  per_kwh: 'Cobra só a energia entregue.',
  time_of_use: 'Cobra a energia pelo preço da janela horária vigente. Configure as janelas depois de criar.',
  per_time: 'Cobra só o tempo conectado, independente da energia.',
  flat: 'Cobra um valor fixo por sessão, independente de energia e tempo.'
}

function NewTariff({ onCreated, onClose }) {
  const [form, setForm] = useState({
    name: '',
    type: 'per_kwh',
    active: false,
    price_per_kwh: 1.4,
    price_per_min: 0,
    idle_fee_per_min: 0.1,
    session_fee: 0,
    min_charge: 5,
    free_minutes: 5
  })

  const criar = useAction(() => tariffsApi.create(form), {
    onSuccess: () => {
      onCreated()
      onClose()
    }
  })

  const campo = (nome, rotulo, step = '0.01') => (
    <div className="form-row" key={nome}>
      <label htmlFor={`nt-${nome}`}>{rotulo}</label>
      <input
        id={`nt-${nome}`}
        className="input"
        type="number"
        min="0"
        step={step}
        value={form[nome]}
        disabled={criar.pending}
        onChange={(e) => setForm({ ...form, [nome]: Number(e.target.value) })}
      />
    </div>
  )

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div className="card-title" style={{ fontSize: 15 }}>Nova tarifa</div>
      <div className="card-sub">
        Nasce inativa: ligue na tabela quando estiver pronta. As janelas horárias são configuradas
        depois, no botão Janelas da própria linha.
      </div>

      <div className="grid grid-2" style={{ marginTop: 12 }}>
        <div className="form-row">
          <label htmlFor="nt-name">Nome</label>
          <input
            id="nt-name"
            className="input"
            value={form.name}
            disabled={criar.pending}
            placeholder="Tarifa Visitante"
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </div>
        <div className="form-row">
          <label htmlFor="nt-type">Tipo</label>
          <select
            id="nt-type"
            className="input"
            value={form.type}
            disabled={criar.pending}
            onChange={(e) => {
              const tipo = TIPOS_TARIFA.find((t) => t.valor === e.target.value)
              setForm({ ...form, type: tipo.valor, ...tipo.precos })
            }}
          >
            {TIPOS_TARIFA.map((t) => (
              <option key={t.valor} value={t.valor}>{t.rotulo}</option>
            ))}
          </select>
          <span className="muted" style={{ fontSize: 11 }}>{AJUDA_TIPO[form.type]}</span>
        </div>
      </div>

      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        O que a fatura cobra são os valores abaixo, não o tipo. Deixe em zero o que não deve ser
        cobrado.
      </div>

      <div className="grid grid-3">
        {campo('price_per_kwh', 'Preço por kWh')}
        {campo('price_per_min', 'Preço por minuto')}
        {campo('idle_fee_per_min', 'Ociosidade por minuto')}
        {campo('session_fee', 'Taxa de conexão')}
        {campo('min_charge', 'Valor mínimo')}
        {campo('free_minutes', 'Minutos livres', '1')}
      </div>

      <ErrorState error={criar.error} compact />

      <div className="flex gap-8" style={{ marginTop: 14 }}>
        <button
          className="btn btn-primary btn-sm"
          disabled={criar.pending || form.name.trim().length < 2}
          onClick={() => criar.run()}
        >
          {criar.pending ? <Spinner size={12} /> : null} Criar tarifa
        </button>
        <button className="btn btn-sm" disabled={criar.pending} onClick={onClose}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
