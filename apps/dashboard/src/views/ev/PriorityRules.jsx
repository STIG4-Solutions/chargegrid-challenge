import { useState } from 'react'
import { power, useApi } from '@chargegrid/sdk'
import { Async } from '../../components/Async.jsx'

/**
 * Regras de prioridade nomeadas.
 *
 * A prioridade decide quem fica sem carregar quando falta potência — a decisão
 * mais consequente do rateio. Até aqui era um inteiro solto no ponto: o
 * operador via "100" e não sabia o que significava nem por que aquele ponto
 * tinha esse valor.
 *
 * A pré-visualização existe porque a regra só se manifesta quando falta
 * potência, e aí já é tarde para descobrir que a janela da frota noturna
 * estava invertida. Aqui dá para perguntar "às 23h, quem tem prioridade?"
 * antes de precisar.
 */
export default function PriorityRules() {
  const regras = useApi(() => power.priorityRules(), [])
  const [hora, setHora] = useState('')
  const previa = useApi(() => power.priorityPreview(hora || undefined), [hora])

  return (
    <div>
      <Async
        loading={regras.loading}
        error={regras.error}
        data={regras.data}
        onRetry={regras.refetch}
      >
        {regras.data && (
          <Lista
            regras={regras.data}
            onMudou={() => {
              regras.refetch()
              previa.refetch()
            }}
          />
        )}
      </Async>

      <Async
        loading={previa.loading}
        error={previa.error}
        data={previa.data}
        onRetry={previa.refetch}
      >
        {previa.data && <Previa d={previa.data} hora={hora} setHora={setHora} />}
      </Async>
    </div>
  )
}

const CRITERIOS = {
  sempre: 'Todos os pontos',
  ponto: 'Pontos específicos',
  conector: 'Tipo de conector'
}

const VAZIA = {
  nome: '',
  prioridade: 100,
  ordem: 100,
  ativo: true,
  criterio_tipo: 'sempre',
  criterio_valor: '',
  janela_inicio: '',
  janela_fim: ''
}

function Lista({ regras, onMudou }) {
  const [editando, setEditando] = useState(null)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  async function salvar(e) {
    e.preventDefault()
    setErro('')
    setSalvando(true)
    // A janela é opcional, mas precisa dos dois lados ou de nenhum — a API
    // recusa meia janela, e mandar "" viraria um horário inválido.
    const corpo = {
      ...editando,
      criterio_valor: editando.criterio_tipo === 'sempre' ? null : editando.criterio_valor || null,
      janela_inicio: editando.janela_inicio || null,
      janela_fim: editando.janela_fim || null
    }
    try {
      if (editando.id) await power.updatePriorityRule(editando.id, corpo)
      else await power.createPriorityRule(corpo)
      setEditando(null)
      onMudou()
    } catch (err) {
      setErro(err?.message || 'não foi possível salvar')
    } finally {
      setSalvando(false)
    }
  }

  async function remover(id) {
    setErro('')
    try {
      await power.deletePriorityRule(id)
      onMudou()
    } catch (err) {
      setErro(err?.message || 'não foi possível remover')
    }
  }

  return (
    <div className="card">
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12
        }}
      >
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Regras de prioridade</h3>
          <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
            Quando a potência não dá para todos, as faixas maiores são servidas primeiro. A primeira
            regra que casa decide — por isso a ordem importa.
          </p>
        </div>
        {!editando && (
          <button className="btn" onClick={() => setEditando({ ...VAZIA })}>
            Nova regra
          </button>
        )}
      </div>

      {erro && <p style={{ color: 'var(--sems-red)', fontSize: 13, margin: '0 0 12px' }}>{erro}</p>}

      {editando && (
        <form
          onSubmit={salvar}
          style={{
            marginBottom: 16,
            padding: 12,
            border: '1px solid var(--borda, rgba(127,127,127,0.25))',
            borderRadius: 6
          }}
        >
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <label style={{ fontSize: 13 }}>
              Nome
              <input
                required
                maxLength={80}
                value={editando.nome}
                onChange={(e) => setEditando({ ...editando, nome: e.target.value })}
                placeholder="Frota da noite"
                style={{ width: '100%' }}
              />
            </label>
            <label style={{ fontSize: 13 }}>
              Prioridade
              <input
                type="number"
                min={0}
                max={1000}
                value={editando.prioridade}
                onChange={(e) => setEditando({ ...editando, prioridade: Number(e.target.value) })}
                style={{ width: '100%' }}
              />
              <span className="muted" style={{ fontSize: 11 }}>
                maior = servido primeiro
              </span>
            </label>
            <label style={{ fontSize: 13 }}>
              Ordem
              <input
                type="number"
                min={0}
                value={editando.ordem}
                onChange={(e) => setEditando({ ...editando, ordem: Number(e.target.value) })}
                style={{ width: '100%' }}
              />
              <span className="muted" style={{ fontSize: 11 }}>
                menor decide antes
              </span>
            </label>
          </div>
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <label style={{ fontSize: 13 }}>
              Aplica-se a
              <select
                value={editando.criterio_tipo}
                onChange={(e) =>
                  setEditando({ ...editando, criterio_tipo: e.target.value, criterio_valor: '' })
                }
                style={{ width: '100%' }}
              >
                {Object.entries(CRITERIOS).map(([v, r]) => (
                  <option key={v} value={v}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            {editando.criterio_tipo !== 'sempre' && (
              <label style={{ fontSize: 13, gridColumn: 'span 2' }}>
                {editando.criterio_tipo === 'ponto' ? 'Códigos dos pontos' : 'Conectores'}
                <input
                  required
                  value={editando.criterio_valor || ''}
                  onChange={(e) => setEditando({ ...editando, criterio_valor: e.target.value })}
                  placeholder={editando.criterio_tipo === 'ponto' ? 'CP-01, CP-02' : 'TYPE2, CCS2'}
                  style={{ width: '100%' }}
                />
                <span className="muted" style={{ fontSize: 11 }}>
                  separe por vírgula
                </span>
              </label>
            )}
          </div>
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <label style={{ fontSize: 13 }}>
              Vale a partir de
              <input
                type="time"
                value={editando.janela_inicio || ''}
                onChange={(e) => setEditando({ ...editando, janela_inicio: e.target.value })}
                style={{ width: '100%' }}
              />
            </label>
            <label style={{ fontSize: 13 }}>
              Até
              <input
                type="time"
                value={editando.janela_fim || ''}
                onChange={(e) => setEditando({ ...editando, janela_fim: e.target.value })}
                style={{ width: '100%' }}
              />
            </label>
            <label style={{ fontSize: 13, alignSelf: 'end' }}>
              <input
                type="checkbox"
                checked={editando.ativo}
                onChange={(e) => setEditando({ ...editando, ativo: e.target.checked })}
              />{' '}
              Ativa
            </label>
          </div>
          <p className="muted" style={{ fontSize: 11, margin: '0 0 12px' }}>
            Deixe os dois horários vazios para valer o dia inteiro. Janela que cruza a meia-noite
            (22:00 → 06:00) é aceita e cobre a virada.
          </p>
          <button className="btn" type="submit" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar'}
          </button>{' '}
          <button className="btn" type="button" onClick={() => setEditando(null)}>
            Cancelar
          </button>
        </form>
      )}

      {regras.length === 0 ? (
        <p className="muted" style={{ fontSize: 13 }}>
          Nenhuma regra. A prioridade de cada ponto é o valor cadastrado nele.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ minWidth: 720 }}>
            <thead>
              <tr>
                <th>Ordem</th>
                <th>Nome</th>
                <th>Aplica-se a</th>
                <th>Quando</th>
                <th style={{ textAlign: 'right' }}>Prioridade</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {regras.map((r) => (
                <tr key={r.id} style={r.ativo ? undefined : { opacity: 0.5 }}>
                  <td>{r.ordem}</td>
                  <td>
                    <strong>{r.nome}</strong>
                    {!r.ativo && <span className="muted"> (inativa)</span>}
                  </td>
                  <td>
                    {CRITERIOS[r.criterio_tipo] || r.criterio_tipo}
                    {r.criterio_valor && (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {r.criterio_valor}
                      </div>
                    )}
                  </td>
                  <td>
                    {r.janela_inicio ? `${r.janela_inicio} → ${r.janela_fim}` : 'dia inteiro'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <strong>{r.prioridade}</strong>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button
                      className="btn"
                      onClick={() =>
                        setEditando({
                          ...r,
                          criterio_valor: r.criterio_valor || '',
                          janela_inicio: r.janela_inicio || '',
                          janela_fim: r.janela_fim || ''
                        })
                      }
                    >
                      Editar
                    </button>{' '}
                    <button className="btn" onClick={() => remover(r.id)}>
                      Remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Previa({ d, hora, setHora }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Quem tem prioridade agora</h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        Simule outro horário para conferir a regra antes de precisar dela. Fuso do site:{' '}
        {d.timezone}. {d.regras_ativas} regra(s) ativa(s).
      </p>

      <label style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
        Horário <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />{' '}
        {hora && (
          <button className="btn" onClick={() => setHora('')}>
            Voltar para agora
          </button>
        )}
      </label>

      <div style={{ overflowX: 'auto' }}>
        <table className="table" style={{ minWidth: 560 }}>
          <thead>
            <tr>
              <th>Ponto</th>
              <th>Regra que decide</th>
              <th style={{ textAlign: 'right' }}>Cadastrada</th>
              <th style={{ textAlign: 'right' }}>Efetiva</th>
            </tr>
          </thead>
          <tbody>
            {(d.pontos || []).map((p) => {
              const mudou = p.regra && p.prioridade_efetiva !== p.prioridade_base
              return (
                <tr key={p.code}>
                  <td>
                    <strong>{p.code}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {p.name}
                    </div>
                  </td>
                  <td>
                    {p.regra || <span className="muted">nenhuma — vale o valor do ponto</span>}
                  </td>
                  <td style={{ textAlign: 'right' }} className="muted">
                    {p.prioridade_base}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <strong style={mudou ? { color: 'var(--sems-red)' } : undefined}>
                      {p.prioridade_efetiva}
                    </strong>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
