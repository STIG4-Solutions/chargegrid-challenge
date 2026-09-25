import { useEffect, useState } from 'react'

/**
 * Cena 5 do "Como funciona": o assistente do painel respondendo com os dados
 * da praca. ISOLADA de proposito - o assistente depende de outro PR. Para tirar
 * a cena, remova a entrada `assistente` de CENAS em ComoFunciona.jsx e apague
 * este arquivo; nada mais depende dele.
 *
 * Recria o widget descrito em .scratch/landing/assistente-front.md: painel de
 * 400 px, cabecalho "Assistente", baloes, indicador de consulta e tabela.
 * Os numeros sao os que a rota de ocupacao devolveu para a praca do seed.
 */

export const LEGENDA_ASSISTENTE = ['Pergunte em português.', 'Resposta com os dados da praça.']

const PERGUNTA = 'Qual ponto se paga e qual fica ocioso?'

const LINHAS = [
  ['CP-04', '23,0%', 'R$ 3,00', 'saudável'],
  ['CP-03', '10,7%', 'R$ 2,68', 'ocioso'],
  ['CP-01', '9,9%', 'R$ 2,53', 'ocioso'],
  ['CP-02', '9,8%', 'R$ 2,40', 'ocioso']
]

// Linha do tempo da cena, em ms depois de ela ficar ativa.
const PAUSA_ANTES = 500
const CONSULTA_MS = 1300
const RESPOSTA_MS = 1400

/** Tempo de cada tecla: ritmo humano, mais lento depois de espaco e pontuacao. */
function atrasoDaTecla(anterior) {
  const base = 45 + Math.random() * 55
  return anterior === ' ' ? base + 40 : anterior === ',' || anterior === '?' ? base + 120 : base
}

function Spinner() {
  return <span className="lp-assist-spinner" aria-hidden="true" />
}

export function CenaAssistente({ ativa, estatica = false }) {
  const [digitado, setDigitado] = useState(estatica ? PERGUNTA.length : 0)
  const [fase, setFase] = useState(estatica ? 'pronta' : 'digitando')
  const [revelado, setRevelado] = useState(estatica ? 1 : 0)

  useEffect(() => {
    if (estatica) return undefined
    if (!ativa) {
      // Saiu da tela: reinicia, para a cena tocar de novo ao voltar.
      setDigitado(0)
      setFase('digitando')
      setRevelado(0)
      return undefined
    }
    let cancelado = false
    const timers = []
    const depois = (ms, fn) => timers.push(setTimeout(() => !cancelado && fn(), ms))

    let t = PAUSA_ANTES
    for (let i = 1; i <= PERGUNTA.length; i++) {
      t += atrasoDaTecla(PERGUNTA[i - 2])
      const n = i
      depois(t, () => setDigitado(n))
    }
    t += 450
    depois(t, () => setFase('consultando'))
    t += CONSULTA_MS
    depois(t, () => setFase('respondendo'))
    // A resposta chega em pedacos, como o fluxo SSE do widget.
    const passos = 14
    for (let k = 1; k <= passos; k++) {
      depois(t + (RESPOSTA_MS * k) / passos, () => setRevelado(k / passos))
    }
    depois(t + RESPOSTA_MS + 50, () => setFase('pronta'))
    return () => {
      cancelado = true
      timers.forEach(clearTimeout)
    }
  }, [ativa, estatica])

  const enviada = fase !== 'digitando'
  const mostra = (limite) => revelado >= limite

  return (
    <div className="lp-ui lp-assist">
      <div className="lp-assist-topo">
        <div>
          <strong>Assistente</strong>
          <span>Consulta os dados desta praça</span>
        </div>
        <span className="lp-assist-btn">Nova conversa</span>
      </div>

      <div className="lp-assist-msgs">
        {enviada && <div className="lp-assist-msg lp-assist-usuario">{PERGUNTA}</div>}
        {enviada && (
          <div className="lp-assist-msg lp-assist-resposta">
            {fase === 'consultando' && (
              <span className="lp-assist-status">
                <Spinner />
                Consultando a ocupação
              </span>
            )}
            {mostra(0.15) && (
              <p>
                Nos últimos 30 dias, o <strong>CP-04</strong> é o que se paga: 23% de ocupação e R$
                3,00 por hora disponível. Os outros três ficam ociosos.
              </p>
            )}
            {mostra(0.45) && (
              <div className="lp-assist-tabela">
                <table>
                  <thead>
                    <tr>
                      <th>Ponto</th>
                      <th>Ocupação</th>
                      <th>R$/h</th>
                      <th>Situação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {LINHAS.map((l, i) =>
                      mostra(0.5 + i * 0.1) ? (
                        <tr key={l[0]}>
                          {l.map((c) => (
                            <td key={c}>{c}</td>
                          ))}
                        </tr>
                      ) : null
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {mostra(0.95) && (
              <p>
                A ociosidade custou <strong>R$ 959,61</strong> no mês. Fonte: aba Ocupação &amp;
                Retorno.
              </p>
            )}
            {fase === 'respondendo' && (
              <span className="lp-assist-status">
                <Spinner />
              </span>
            )}
          </div>
        )}
      </div>

      <div className="lp-assist-entrada">
        <div className="lp-assist-campo">
          {enviada ? (
            <span className="lp-assist-placeholder">Pergunte sobre a operação da praça…</span>
          ) : (
            <span>
              {PERGUNTA.slice(0, digitado)}
              <span className="lp-assist-cursor" aria-hidden="true" />
            </span>
          )}
        </div>
        <div className="lp-assist-rodape">
          <span>{enviada ? 0 : digitado}/2000</span>
          <span className="lp-assist-enviar">
            {fase === 'pronta' || !enviada ? 'Enviar' : 'Parar'}
          </span>
        </div>
      </div>
    </div>
  )
}
