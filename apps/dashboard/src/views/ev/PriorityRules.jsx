import { useId, useState } from 'react'
import { power, useApi } from '@chargegrid/sdk'
import { Async } from '../../components/Async.jsx'
import { Campo } from '../../components/Campo.jsx'

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
      {/*
        `empty={null}` porque a SEÇÃO é dona do próprio vazio, e precisa ser.
        O card não é só a tabela: ele carrega o botão "Nova regra". Deixar o
        `<Async>` trocar o card inteiro pelo aviso genérico tirava da tela a
        única saída do estado vazio — não dava para criar a primeira regra.
        E `Lista` já diz melhor: sem regra, vale a prioridade cadastrada em
        cada ponto, que é informação, não ausência dela.
      */}
      <Async
        loading={regras.loading}
        error={regras.error}
        data={regras.data}
        onRetry={regras.refetch}
        empty={null}
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

/** Exportado para o teste montar com props, sem subir a aba inteira. */
export function Lista({ regras, onMudou }) {
  const [editando, setEditando] = useState(null)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  // `useId` em vez de id fixo: a tela pode montar o formulário mais de uma vez
  // por praça, e id repetido faz o `htmlFor` apontar para o controle errado.
  const idBase = useId()
  const id = (chave) => `${idBase}-${chave}`

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

      {/* `role="alert"` para o leitor de tela anunciar — a mensagem nasce longe
          do controle que a causou, e sem isso passaria despercebida. */}
      {erro && (
        <div className="form-error" role="alert" style={{ marginBottom: 12 }}>
          {erro}
        </div>
      )}

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
          {/*
            Mesmo padrão do formulário de contas: `Campo` cuida do rótulo, da
            associação por `htmlFor` e da faixa única que é dica ou erro. Os
            controles levam `className="input"` — sem ela renderizavam sem
            estilo nenhum, que era o caso aqui.

            As dicas são FIXAS, não placeholders: placeholder some justamente
            quando a pessoa começa a digitar, que é quando a regra ainda importa,
            e leitor de tela costuma anunciá-lo como se fosse valor preenchido.
          */}
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <Campo id={id('nome')} rotulo="Nome" dica="Como esta regra aparece na prévia abaixo.">
              <input
                id={id('nome')}
                className="input"
                required
                maxLength={80}
                value={editando.nome}
                onChange={(e) => setEditando({ ...editando, nome: e.target.value })}
                aria-describedby={`${id('nome')}-dica`}
              />
            </Campo>

            <Campo
              id={id('prioridade')}
              rotulo="Prioridade"
              dica="Maior é servido primeiro quando a potência não dá para todos."
            >
              <input
                id={id('prioridade')}
                className="input"
                type="number"
                min={0}
                max={1000}
                value={editando.prioridade}
                onChange={(e) => setEditando({ ...editando, prioridade: Number(e.target.value) })}
                aria-describedby={`${id('prioridade')}-dica`}
              />
            </Campo>

            <Campo
              id={id('ordem')}
              rotulo="Ordem de avaliação"
              dica="Menor decide antes. A primeira regra que casa é a que vale."
            >
              <input
                id={id('ordem')}
                className="input"
                type="number"
                min={0}
                value={editando.ordem}
                onChange={(e) => setEditando({ ...editando, ordem: Number(e.target.value) })}
                aria-describedby={`${id('ordem')}-dica`}
              />
            </Campo>
          </div>
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <Campo id={id('criterio')} rotulo="Aplica-se a" dica="Quais pontos esta regra alcança.">
              <select
                id={id('criterio')}
                className="input"
                value={editando.criterio_tipo}
                onChange={(e) =>
                  setEditando({ ...editando, criterio_tipo: e.target.value, criterio_valor: '' })
                }
                aria-describedby={`${id('criterio')}-dica`}
              >
                {Object.entries(CRITERIOS).map(([v, r]) => (
                  <option key={v} value={v}>
                    {r}
                  </option>
                ))}
              </select>
            </Campo>

            {/*
              O campo do valor só existe para critério que precisa dele — com
              "Todos os pontos" não há o que listar, e um campo vazio e inerte
              ao lado convidaria a preenchê-lo.
            */}
            {editando.criterio_tipo !== 'sempre' && (
              <div style={{ gridColumn: 'span 2' }}>
                <Campo
                  id={id('valor')}
                  rotulo={editando.criterio_tipo === 'ponto' ? 'Códigos dos pontos' : 'Conectores'}
                  dica={
                    editando.criterio_tipo === 'ponto'
                      ? 'Separe por vírgula, como aparecem na prévia: CP-01, CP-02.'
                      : 'Separe por vírgula: TYPE2, CCS2.'
                  }
                >
                  <input
                    id={id('valor')}
                    className="input"
                    required
                    value={editando.criterio_valor || ''}
                    onChange={(e) => setEditando({ ...editando, criterio_valor: e.target.value })}
                    aria-describedby={`${id('valor')}-dica`}
                  />
                </Campo>
              </div>
            )}
          </div>
          <div className="grid grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <Campo
              id={id('inicio')}
              rotulo="Vale a partir de"
              dica="Vazio nos dois = o dia inteiro."
            >
              <input
                id={id('inicio')}
                className="input"
                type="time"
                value={editando.janela_inicio || ''}
                onChange={(e) => setEditando({ ...editando, janela_inicio: e.target.value })}
                aria-describedby={`${id('inicio')}-dica`}
              />
            </Campo>

            <Campo
              id={id('fim')}
              rotulo="Até"
              dica="22:00 → 06:00 é aceito e cobre a virada da meia-noite."
            >
              <input
                id={id('fim')}
                className="input"
                type="time"
                value={editando.janela_fim || ''}
                onChange={(e) => setEditando({ ...editando, janela_fim: e.target.value })}
                aria-describedby={`${id('fim')}-dica`}
              />
            </Campo>

            <Campo
              id={id('ativo')}
              rotulo="Situação"
              dica={
                editando.ativo
                  ? 'Entra no rateio assim que for salva.'
                  : 'Fica cadastrada sem efeito nenhum.'
              }
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 34 }}>
                <input
                  id={id('ativo')}
                  type="checkbox"
                  checked={editando.ativo}
                  onChange={(e) => setEditando({ ...editando, ativo: e.target.checked })}
                  aria-describedby={`${id('ativo')}-dica`}
                />
                <span style={{ fontSize: 13 }}>{editando.ativo ? 'Ativa' : 'Inativa'}</span>
              </div>
            </Campo>
          </div>
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

/** Exportado para o teste montar com props, sem subir a aba inteira. */
export function Previa({ d, hora, setHora }) {
  const idBase = useId()
  const idHora = `${idBase}-hora`

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Quem tem prioridade agora</h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        Simule outro horário para conferir a regra antes de precisar dela. Fuso do site:{' '}
        {d.timezone}. {d.regras_ativas} regra(s) ativa(s).
      </p>

      {/*
        Mesmo `Campo` do formulário acima. O botão de voltar vai no `acao`, ao
        lado do rótulo, e não dentro do `<label>`: botão dentro de label faz o
        clique nele cair também no campo de horário, abrindo o seletor de hora
        justamente quando a pessoa quis fechá-lo.

        A tabela abaixo é o resultado, então o campo cabe numa coluna estreita —
        esticá-lo pela largura do cartão sugeriria que ele filtra a tabela
        inteira, quando o que ele faz é mover o relógio da simulação.
      */}
      <div style={{ maxWidth: 260, marginBottom: 12 }}>
        <Campo
          id={idHora}
          rotulo="Horário simulado"
          dica={hora ? `Mostrando as regras como às ${hora}.` : 'Vazio = agora.'}
          acao={
            hora ? (
              <button className="btn btn-sm" onClick={() => setHora('')}>
                Voltar para agora
              </button>
            ) : null
          }
        >
          <input
            id={idHora}
            className="input"
            type="time"
            value={hora}
            onChange={(e) => setHora(e.target.value)}
            aria-describedby={`${idHora}-dica`}
          />
        </Campo>
      </div>

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
