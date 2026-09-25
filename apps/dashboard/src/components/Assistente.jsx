import { useEffect, useReducer, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { assistant, getConfig, useApi } from '@chargegrid/sdk'
import { Spinner } from './Async.jsx'
import {
  blocosMarkdown,
  estadoInicial,
  problemaNaPergunta,
  reduzir,
  sugestoesDaAba
} from '../views/ev/assistente.js'

/**
 * Assistente de operação: um botão fixo no canto, em qualquer tela do painel.
 *
 * Só aparece se a API disser que está habilitado. Desligado — ou para uma
 * conta de motorista, que toma 403 — ele não se mostra: um botão que abre um
 * painel que só responde erro é pior que botão nenhum.
 */
export default function Assistente() {
  const status = useApi(() => assistant.status(), [])
  if (!status.data?.habilitado) return null
  return <PainelDoAssistente limite={status.data.limite_de_caracteres} />
}

function IconeConversa() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
      <path
        d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4A2.5 2.5 0 0 1 3 13.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M8 8.5h8M8 11.5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function PainelDoAssistente({ limite, abertoDeInicio = false }) {
  const [aberto, setAberto] = useState(abertoDeInicio)
  const [estado, despachar] = useReducer(reduzir, undefined, estadoInicial)
  const [pergunta, setPergunta] = useState('')
  const controle = useRef(null)
  // Praça em que a conversa nasceu. A API recusa (409) continuar a conversa em
  // outra praça; conferir aqui antes evita a ida e volta.
  const pracaDaConversa = useRef(null)
  const retomou = useRef(false)
  const fim = useRef(null)
  const { pathname } = useLocation()

  // Ao abrir pela primeira vez, retoma a última conversa desta praça.
  useEffect(() => {
    if (!aberto || retomou.current) return
    retomou.current = true
    ;(async () => {
      try {
        const [ultima] = await assistant.conversas()
        if (!ultima) return
        const detalhe = await assistant.conversa(ultima.id)
        pracaDaConversa.current = getConfig().siteId ?? null
        despachar({ tipo: 'carregar', id: detalhe.id, mensagens: detalhe.mensagens })
      } catch {
        // Sem histórico, começa do zero - não é motivo para travar o painel.
      }
    })()
  }, [aberto])

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: 'end' })
  }, [estado.mensagens])

  // Fechar a página no meio da resposta encerra o fluxo.
  useEffect(() => () => controle.current?.abort(), [])

  async function enviar(texto) {
    if (estado.enviando || problemaNaPergunta(texto, limite)) return
    const pracaAtual = getConfig().siteId ?? null
    let conversaId = estado.conversaId
    if (conversaId && pracaDaConversa.current !== pracaAtual) {
      despachar({ tipo: 'nova', aviso: 'A praça mudou. Esta é uma conversa nova.' })
      conversaId = null
    }

    despachar({ tipo: 'enviar', texto: texto.trim() })
    setPergunta('')
    const parar = new AbortController()
    controle.current = parar
    try {
      if (!conversaId) {
        const nova = await assistant.criarConversa()
        conversaId = nova.id
        pracaDaConversa.current = pracaAtual
        despachar({ tipo: 'conversa', id: nova.id })
      }
      for await (const evento of assistant.enviar(conversaId, texto.trim(), {
        aba: pathname,
        signal: parar.signal
      })) {
        despachar(evento)
      }
    } catch (err) {
      if (parar.signal.aborted) despachar({ tipo: 'parado' })
      else
        despachar({
          tipo: 'falhou',
          status: err?.status,
          mensagem: err?.detail || 'Não foi possível falar com o assistente.'
        })
    } finally {
      if (controle.current === parar) controle.current = null
    }
  }

  function novaConversa() {
    controle.current?.abort()
    pracaDaConversa.current = null
    despachar({ tipo: 'nova' })
  }

  const problema = problemaNaPergunta(pergunta, limite)
  const vazio = estado.mensagens.length === 0

  return (
    <>
      <button
        type="button"
        className="assistente-botao"
        aria-label={aberto ? 'Fechar assistente' : 'Abrir assistente'}
        aria-expanded={aberto}
        onClick={() => setAberto((a) => !a)}
      >
        <IconeConversa />
      </button>

      {aberto && (
        <section className="assistente-painel" aria-label="Assistente de operação">
          <header className="assistente-topo">
            <div>
              <strong>Assistente</strong>
              <span className="muted">Consulta os dados desta praça</span>
            </div>
            <button type="button" className="btn btn-sm" onClick={novaConversa}>
              Nova conversa
            </button>
            <button
              type="button"
              className="btn btn-sm btn-icon"
              aria-label="Fechar"
              onClick={() => setAberto(false)}
            >
              ×
            </button>
          </header>

          <div className="assistente-mensagens" aria-live="polite">
            {estado.aviso && <p className="assistente-aviso">{estado.aviso}</p>}
            {vazio ? (
              <div className="assistente-sugestoes">
                <p className="muted">
                  Pergunte sobre potência, sessões, receita, ocupação, manutenção, campanhas ou o
                  contrato. Cada número vem das mesmas consultas das abas do painel.
                </p>
                {sugestoesDaAba(pathname).map((s) => (
                  <button key={s} type="button" className="btn btn-sm" onClick={() => enviar(s)}>
                    {s}
                  </button>
                ))}
              </div>
            ) : (
              estado.mensagens.map((m) => <Mensagem key={m.id} mensagem={m} />)
            )}
            <div ref={fim} />
          </div>

          <form
            className="assistente-entrada"
            onSubmit={(e) => {
              e.preventDefault()
              enviar(pergunta)
            }}
          >
            <textarea
              aria-label="Pergunta ao assistente"
              placeholder="Pergunte sobre a operação da praça…"
              rows={2}
              value={pergunta}
              onChange={(e) => setPergunta(e.target.value)}
              onKeyDown={(e) => {
                // Enter envia; Shift+Enter quebra a linha.
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  enviar(pergunta)
                }
              }}
            />
            <div className="assistente-rodape">
              <span className={pergunta.length > limite ? 'red' : 'muted'}>
                {pergunta.length}/{limite}
              </span>
              {estado.enviando ? (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => controle.current?.abort()}
                >
                  Parar
                </button>
              ) : (
                <button type="submit" className="btn btn-primary btn-sm" disabled={!!problema}>
                  Enviar
                </button>
              )}
            </div>
            <p className="assistente-nota muted">
              Respostas geradas por IA a partir dos dados do painel. Confira na aba citada.
            </p>
          </form>
        </section>
      )}
    </>
  )
}

// Estado da resposta -> classe de destaque. As que saem normais nao tem entrada.
const DESTAQUE = {
  bloqueada: 'assistente-bloqueada',
  erro: 'assistente-erro',
  interrompida: 'assistente-interrompida'
}

export function Mensagem({ mensagem }) {
  const { papel, texto, estado, consulta } = mensagem
  if (papel === 'user') return <div className="assistente-msg usuario">{texto}</div>
  const destaque = DESTAQUE[estado] ?? ''
  return (
    <div className={`assistente-msg resposta ${destaque}`}>
      {texto ? <Markdown texto={texto} /> : null}
      {estado === 'gerando' && (
        <span className="assistente-status">
          <Spinner size={14} />
          {consulta || (texto ? '' : 'Pensando…')}
        </span>
      )}
      {estado === 'interrompida' && <span className="assistente-status">Interrompida</span>}
    </div>
  )
}

function Partes({ partes }) {
  return partes.map((p, i) => {
    if (p.t === 'forte') return <strong key={i}>{p.v}</strong>
    if (p.t === 'enfase') return <em key={i}>{p.v}</em>
    if (p.t === 'codigo') return <code key={i}>{p.v}</code>
    return <span key={i}>{p.v}</span>
  })
}

export function Markdown({ texto }) {
  return blocosMarkdown(texto).map((b, i) => {
    switch (b.tipo) {
      case 'titulo':
        return (
          <p key={i} className="assistente-titulo">
            <Partes partes={b.partes} />
          </p>
        )
      case 'ul':
      case 'ol': {
        const Lista = b.tipo
        return (
          <Lista key={i}>
            {b.itens.map((item, j) => (
              <li key={j}>
                <Partes partes={item} />
              </li>
            ))}
          </Lista>
        )
      }
      case 'tabela':
        return (
          <div key={i} className="assistente-tabela">
            <table>
              <thead>
                <tr>
                  {b.cabecalho.map((c, j) => (
                    <th key={j}>
                      <Partes partes={c} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.linhas.map((linha, j) => (
                  <tr key={j}>
                    {linha.map((c, k) => (
                      <td key={k}>
                        <Partes partes={c} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      case 'codigo':
        return <pre key={i}>{b.texto}</pre>
      default:
        return (
          <p key={i}>
            {b.linhas.map((linha, j) => (
              <span key={j}>
                {j > 0 && <br />}
                <Partes partes={linha} />
              </span>
            ))}
          </p>
        )
    }
  })
}
