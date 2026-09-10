import { Fragment, useMemo, useState } from 'react'
import { brl, campaigns, num, useAction, useApi } from '@chargegrid/sdk'

import { Async, Empty } from '../../components/Async.jsx'
import {
  alteracoesDaCampanha,
  consumoDoOrcamento,
  ehCashback,
  problemasDaCampanha,
  situacaoDaCampanha
} from './campanha.js'

const SITUACOES = {
  vigente: { rotulo: 'Vigente', classe: 'badge-green' },
  agendada: { rotulo: 'Agendada', classe: 'badge-blue' },
  expirada: { rotulo: 'Prazo vencido', classe: 'badge-yellow' },
  encerrada: { rotulo: 'Encerrada', classe: 'badge-gray' }
}

const BENEFICIOS = [
  { valor: 'cashback_fixo', rotulo: 'Cashback — valor fixo' },
  { valor: 'cashback_pct', rotulo: 'Cashback — percentual' },
  { valor: 'desconto_pct', rotulo: 'Desconto na fatura — percentual' }
]

const METRICAS = [
  { valor: 'sessoes', rotulo: 'Recargas' },
  { valor: 'energia_kwh', rotulo: 'Energia (kWh)' },
  { valor: 'energia_verde_kwh', rotulo: 'Energia solar (kWh)' },
  { valor: 'valor_brl', rotulo: 'Valor gasto (R$)' },
  { valor: 'dias_distintos', rotulo: 'Dias diferentes' },
  { valor: 'sessoes_fora_de_ponta', rotulo: 'Recargas fora de ponta' }
]

const JANELAS = [
  { valor: 'campanha', rotulo: 'Toda a campanha' },
  { valor: 'mensal', rotulo: 'Por mês' },
  { valor: 'semanal', rotulo: 'Por semana' }
]

function Stat({ rotulo, valor, nota, destaque }) {
  return (
    <div className="stat">
      <div className="label">{rotulo}</div>
      <div className="value" style={destaque ? { color: 'var(--sems-red)' } : undefined}>
        {valor}
      </div>
      {nota && <div className="trend muted">{nota}</div>}
    </div>
  )
}

/** Quanto do orçamento já saiu do caixa. */
function BarraDeOrcamento({ campanha }) {
  const pct = consumoDoOrcamento(campanha)
  const semTeto = !(Number(campanha.orcamento_brl) > 0)
  return (
    <div>
      <div className="meter" style={{ marginBottom: 4 }}>
        <div
          className="meter-fill"
          style={{ width: `${pct}%`, background: pct >= 90 ? 'var(--sems-red)' : 'var(--sems-green)' }}
        />
      </div>
      <div className="muted" style={{ fontSize: 12 }}>
        {semTeto ? (
          'sem orçamento definido'
        ) : (
          <>
            {brl(campanha.consumido_brl)} de {brl(campanha.orcamento_brl)} · {num(pct, 0)}%
          </>
        )}
      </div>
    </div>
  )
}

function Desempenho({ campanhaId }) {
  const dados = useApi(() => campaigns.performance(campanhaId), [campanhaId], { pollMs: 60000 })
  return (
    <Async loading={dados.loading} error={dados.error} data={dados.data} onRetry={dados.refetch}>
      {dados.data && (
        <div className="grid grid-4">
          <Stat rotulo="Motoristas alcançados" valor={num(dados.data.motoristas_alcancados, 0)} />
          <Stat rotulo="Missões concluídas" valor={num(dados.data.missoes_concluidas, 0)} />
          <Stat rotulo="Recompensas pagas" valor={num(dados.data.recompensas_creditadas, 0)} />
          <Stat
            rotulo="Consumido"
            valor={brl(dados.data.consumido_brl)}
            nota={`restam ${brl(dados.data.orcamento_disponivel)}`}
            destaque={dados.data.percentual_consumido >= 90}
          />
        </div>
      )}
    </Async>
  )
}

const VAZIA = {
  nome: '',
  descricao: '',
  patrocinador: 'site',
  starts_at: '',
  ends_at: '',
  beneficio_tipo: 'cashback_fixo',
  beneficio_valor: 5,
  teto_por_recompensa: '',
  orcamento_brl: 500,
  missoes: [{ codigo: 'tres-recargas', titulo: 'Recarregue 3 vezes', metrica: 'sessoes', alvo: 3, janela: 'mensal' }]
}

function Formulario({ aoCriar, aoFechar }) {
  const [rascunho, setRascunho] = useState(VAZIA)
  const criar = useAction(campaigns.create, { onSuccess: aoCriar })

  const problemas = useMemo(() => problemasDaCampanha(rascunho), [rascunho])
  const campo = (nome) => (evento) =>
    setRascunho((atual) => ({ ...atual, [nome]: evento.target.value }))

  const trocaBeneficio = (evento) => {
    const tipo = evento.target.value
    setRascunho((atual) => ({
      ...atual,
      beneficio_tipo: tipo,
      // Desconto age na fatura, na hora: as missões deixam de fazer sentido e
      // some com elas em vez de deixar o operador descobrir no erro do salvar.
      missoes: ehCashback(tipo) ? (atual.missoes.length ? atual.missoes : VAZIA.missoes) : []
    }))
  }

  const mexeNaMissao = (indice, chave) => (evento) =>
    setRascunho((atual) => ({
      ...atual,
      missoes: atual.missoes.map((m, i) => (i === indice ? { ...m, [chave]: evento.target.value } : m))
    }))

  const enviar = () => {
    if (problemas.length) return
    criar.run({
      ...rascunho,
      beneficio_valor: Number(rascunho.beneficio_valor),
      orcamento_brl: Number(rascunho.orcamento_brl),
      teto_por_recompensa: rascunho.teto_por_recompensa ? Number(rascunho.teto_por_recompensa) : null,
      starts_at: new Date(rascunho.starts_at).toISOString(),
      ends_at: new Date(rascunho.ends_at).toISOString(),
      missoes: rascunho.missoes.map((m) => ({ ...m, alvo: Number(m.alvo), ordem: 0, repetivel: false }))
    })
  }

  return (
    <div className="card">
      <div className="card-title">Nova campanha</div>
      <div className="card-sub">
        Quem paga é esta praça. Campanha de rede é criada pela administração da GoodWe.
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <div className="form-row">
          <label>Nome</label>
          <input className="input" value={rascunho.nome} onChange={campo('nome')} placeholder="Setembro Verde" />
        </div>
        <div className="form-row">
          <label>Benefício</label>
          <select className="input" value={rascunho.beneficio_tipo} onChange={trocaBeneficio}>
            {BENEFICIOS.map((b) => (
              <option key={b.valor} value={b.valor}>
                {b.rotulo}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label>Início</label>
          <input className="input" type="date" value={rascunho.starts_at} onChange={campo('starts_at')} />
        </div>
        <div className="form-row">
          <label>Término</label>
          <input className="input" type="date" value={rascunho.ends_at} onChange={campo('ends_at')} />
        </div>
        <div className="form-row">
          <label>{rascunho.beneficio_tipo.endsWith('_pct') ? 'Percentual (%)' : 'Valor por recompensa (R$)'}</label>
          <input
            className="input"
            type="number"
            value={rascunho.beneficio_valor}
            onChange={campo('beneficio_valor')}
          />
        </div>
        <div className="form-row">
          <label>Orçamento total (R$)</label>
          <input className="input" type="number" value={rascunho.orcamento_brl} onChange={campo('orcamento_brl')} />
        </div>
      </div>

      {ehCashback(rascunho.beneficio_tipo) && (
        <>
          <div className="card-title" style={{ marginTop: 20, fontSize: 14 }}>
            Missões
          </div>
          <div className="card-sub">É o que o motorista precisa cumprir para receber o cashback.</div>
          {rascunho.missoes.map((missao, indice) => (
            <div className="grid grid-4" key={indice} style={{ marginTop: 12 }}>
              <div className="form-row">
                <label>Título</label>
                <input className="input" value={missao.titulo} onChange={mexeNaMissao(indice, 'titulo')} />
              </div>
              <div className="form-row">
                <label>Medir</label>
                <select className="input" value={missao.metrica} onChange={mexeNaMissao(indice, 'metrica')}>
                  {METRICAS.map((m) => (
                    <option key={m.valor} value={m.valor}>
                      {m.rotulo}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-row">
                <label>Alvo</label>
                <input className="input" type="number" value={missao.alvo} onChange={mexeNaMissao(indice, 'alvo')} />
              </div>
              <div className="form-row">
                <label>Janela</label>
                <select className="input" value={missao.janela} onChange={mexeNaMissao(indice, 'janela')}>
                  {JANELAS.map((j) => (
                    <option key={j.valor} value={j.valor}>
                      {j.rotulo}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </>
      )}

      {problemas.length > 0 && (
        <div className="async-error compact" style={{ marginTop: 16 }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {problemas.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {criar.error && (
        <div className="async-error compact" style={{ marginTop: 12 }}>
          {criar.error.detail}
        </div>
      )}

      <div className="flex gap-12" style={{ marginTop: 16 }}>
        <button className="btn btn-primary" onClick={enviar} disabled={problemas.length > 0 || criar.pending}>
          {criar.pending ? 'Salvando…' : 'Criar campanha'}
        </button>
        <button className="btn" onClick={aoFechar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

function Lista({ dados, aoMudar }) {
  const [aberta, setAberta] = useState(null)
  const encerrar = useAction(campaigns.close, { onSuccess: aoMudar })

  if (!dados.length) {
    return <Empty>Nenhuma campanha ainda. Crie a primeira para dar um motivo de volta ao motorista.</Empty>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table" style={{ minWidth: 860 }}>
        <thead>
          <tr>
            <th>Campanha</th>
            <th>Quem paga</th>
            <th>Benefício</th>
            <th>Período</th>
            <th style={{ width: 200 }}>Orçamento</th>
            <th>Situação</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {dados.map((c) => {
            const situacao = SITUACOES[situacaoDaCampanha(c)]
            const daRede = c.site_id === null
            return (
              // A chave fica no Fragment, e nao nos <tr> de dentro: um fragmento
              // curto (<>) nao aceita key, e sem ela o React reconcilia a lista
              // pela posicao - encerrar uma campanha do meio faria a linha
              // expandida saltar para outra.
              <Fragment key={c.id}>
                <tr
                  className="clickable"
                  onClick={() => setAberta(aberta === c.id ? null : c.id)}
                >
                  <td>
                    <strong>{c.nome}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {c.missoes.length ? `${c.missoes.length} missão(ões)` : 'desconto direto na fatura'}
                    </div>
                  </td>
                  <td>{daRede ? 'Rede GoodWe' : 'Esta praça'}</td>
                  <td>
                    {c.beneficio_tipo.endsWith('_pct')
                      ? `${num(c.beneficio_valor, 1)}%`
                      : brl(c.beneficio_valor)}
                    <div className="muted" style={{ fontSize: 12 }}>
                      {c.beneficio_tipo.startsWith('cashback') ? 'na carteira' : 'na fatura'}
                    </div>
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>
                    {new Date(c.starts_at).toLocaleDateString('pt-BR')} →{' '}
                    {new Date(c.ends_at).toLocaleDateString('pt-BR')}
                  </td>
                  <td>
                    <BarraDeOrcamento campanha={c} />
                  </td>
                  <td>
                    <span className={`badge ${situacao.classe}`}>{situacao.rotulo}</span>
                  </td>
                  <td className="text-right">
                    {!daRede && c.ativa && (
                      <button
                        className="btn btn-sm"
                        disabled={encerrar.pending}
                        onClick={(e) => {
                          e.stopPropagation()
                          encerrar.run(c.id)
                        }}
                      >
                        Encerrar
                      </button>
                    )}
                  </td>
                </tr>
                {aberta === c.id && (
                  <tr>
                    <td colSpan={7} style={{ background: 'var(--sems-card-2)' }}>
                      <Desempenho campanhaId={c.id} />
                      {c.missoes.length > 0 && (
                        <div className="kv" style={{ marginTop: 12 }}>
                          {c.missoes.map((m) => (
                            <div key={m.id}>
                              <span className="muted">{m.titulo}</span>
                              <span>
                                {num(m.alvo, 0)} · {METRICAS.find((x) => x.valor === m.metrica)?.rotulo ?? m.metrica}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
      {encerrar.error && <div className="async-error compact">{encerrar.error.detail}</div>}
    </div>
  )
}

export default function Campaigns() {
  const [criando, setCriando] = useState(false)
  const lista = useApi(() => campaigns.list(), [], { pollMs: 120000 })

  const recarregar = () => {
    setCriando(false)
    lista.refetch({ silent: true })
  }

  return (
    <>
      <div className="panel">
        <div className="flex items-center gap-16" style={{ justifyContent: 'space-between' }}>
          <div>
            <div className="card-title">Campanhas</div>
            <div className="card-sub">
              Desconto sai da margem desta praça e aparece na fatura na hora. Cashback é bancado pela
              rede, depende de missão cumprida e vira crédito na carteira — dinheiro que só volta aqui.
            </div>
          </div>
          {!criando && (
            <button className="btn btn-primary" onClick={() => setCriando(true)}>
              Nova campanha
            </button>
          )}
        </div>
      </div>

      {criando && (
        <div className="panel">
          <Formulario aoCriar={recarregar} aoFechar={() => setCriando(false)} />
        </div>
      )}

      <div className="panel">
        <Async loading={lista.loading} error={lista.error} data={lista.data} onRetry={lista.refetch}>
          {lista.data && <Lista dados={lista.data} aoMudar={recarregar} />}
        </Async>
      </div>
    </>
  )
}
