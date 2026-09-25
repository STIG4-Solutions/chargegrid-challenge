import { janela } from './linhaDoTempo.js'

/**
 * Os dois estados do assistente no "Como funciona": a barra de chat, onde a
 * pergunta e' digitada, e o painel, em que a barra se transforma com a resposta.
 *
 * ISOLADO de proposito - o assistente depende de outro PR. Para tirar a cena,
 * remova `...ESTADOS_ASSISTENTE` e o import em ComoFunciona.jsx e apague este
 * arquivo: a linha do tempo encolhe sozinha, porque os inicios sao calculados
 * pela soma das duracoes.
 *
 * Visual do widget descrito em .scratch/landing/assistente-front.md. Os numeros
 * sao os que a rota de ocupacao devolveu para a praca do seed.
 */

export const LEGENDA_ASSISTENTE = ['Pergunte em português.', 'Resposta com os dados da praça.']

const PERGUNTA = 'Qual ponto se paga e qual fica ocioso?'

const LINHAS = [
  ['CP-04', '23,0%', 'R$ 3,00', 'saudável'],
  ['CP-03', '10,7%', 'R$ 2,68', 'ocioso'],
  ['CP-01', '9,9%', 'R$ 2,53', 'ocioso'],
  ['CP-02', '9,8%', 'R$ 2,40', 'ocioso']
]

// Instante (s, a partir do inicio da barra) em que cada tecla aparece. Ritmo
// humano e deterministico: mais lento depois de espaco e de virgula, e sempre
// igual - o video gravado e o ao vivo mostram a mesma digitacao.
const INICIO_DIGITACAO = 0.9
const TECLAS = (() => {
  const tempos = []
  let t = INICIO_DIGITACAO
  for (let i = 0; i < PERGUNTA.length; i++) {
    const ruido = (Math.sin(i * 12.9898) * 43758.5453) % 1
    const anterior = PERGUNTA[i - 1]
    t += 0.035 + Math.abs(ruido) * 0.035 + (anterior === ' ' ? 0.03 : 0)
    tempos.push(t)
  }
  return tempos
})()
const FIM_DIGITACAO = TECLAS[TECLAS.length - 1]

function Spinner() {
  return <span className="lp-assist-spinner" aria-hidden="true" />
}

function IconeEnviar() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path
        d="M12 19V5m0 0-6 6m6-6 6 6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** A barra: o operador digita e envia. */
function BarraDoAssistente({ tl }) {
  const digitado = TECLAS.filter((x) => x <= tl).length
  const enviando = tl > FIM_DIGITACAO + 0.35
  return (
    <div className="lp-ui lp-assist-barra">
      <span className="lp-assist-barra-marca" aria-hidden="true">
        <img src="/chargegrid-app-icon.png" alt="" width="22" height="22" />
      </span>
      <span className="lp-assist-barra-texto">
        {digitado === 0 ? (
          <span className="lp-assist-placeholder">Pergunte sobre a operação da praça…</span>
        ) : (
          PERGUNTA.slice(0, digitado)
        )}
        {!enviando && <span className="lp-assist-cursor" aria-hidden="true" />}
      </span>
      <span className={`lp-assist-barra-enviar ${enviando ? 'lp-pressionado' : ''}`}>
        <IconeEnviar />
      </span>
    </div>
  )
}

/** O painel: a pergunta enviada, a consulta e a resposta chegando em partes. */
export function PainelDoAssistente({ tl, estatico = false }) {
  const t = estatico ? 99 : tl
  const consultando = t >= 0.7 && t < 1.9
  const parte = (instante) => t >= instante
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
        <div className="lp-assist-msg lp-assist-usuario">{PERGUNTA}</div>
        <div className="lp-assist-msg lp-assist-resposta">
          {consultando && (
            <span className="lp-assist-status">
              <Spinner />
              Consultando a ocupação
            </span>
          )}
          {!consultando && !parte(1.9) && (
            <span className="lp-assist-status">
              <Spinner />
              Pensando…
            </span>
          )}
          {parte(1.9) && (
            <p className="lp-assist-parte" style={{ opacity: estatico ? 1 : janela(t, 1.9, 2.2) }}>
              Nos últimos 30 dias, o <strong>CP-04</strong> é o que se paga: 23% de ocupação e R$
              3,00 por hora disponível. Os outros três ficam ociosos.
            </p>
          )}
          {parte(2.3) && (
            <div
              className="lp-assist-tabela lp-assist-parte"
              style={{ opacity: estatico ? 1 : janela(t, 2.3, 2.6) }}
            >
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
                    parte(2.5 + i * 0.2) ? (
                      <tr
                        key={l[0]}
                        style={{ opacity: estatico ? 1 : janela(t, 2.5 + i * 0.2, 2.8 + i * 0.2) }}
                      >
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
          {parte(3.5) && (
            <p className="lp-assist-parte" style={{ opacity: estatico ? 1 : janela(t, 3.5, 3.8) }}>
              A ociosidade custou <strong>R$ 959,61</strong> no mês. Fonte: aba Ocupação &amp;
              Retorno.
            </p>
          )}
        </div>
      </div>

      <div className="lp-assist-entrada">
        <div className="lp-assist-campo">
          <span className="lp-assist-placeholder">Pergunte sobre a operação da praça…</span>
        </div>
        <div className="lp-assist-rodape">
          <span>0/2000</span>
          <span className="lp-assist-enviar">Enviar</span>
        </div>
      </div>
    </div>
  )
}

/**
 * Os estados, no formato da linha do tempo de ComoFunciona: duracao em
 * segundos, tamanho do card (desktop e celular) e o conteudo em funcao do
 * tempo local.
 */
export const ESTADOS_ASSISTENTE = [
  {
    id: 'assistente-barra',
    dur: 4.0,
    legenda: LEGENDA_ASSISTENTE,
    tamanho: (movel, vw) => (movel ? { w: vw - 32, h: 64 } : { w: 760, h: 72 }),
    raio: 999,
    conteudo: (tl) => <BarraDoAssistente tl={tl} />
  },
  {
    id: 'assistente-painel',
    dur: 4.8,
    legenda: LEGENDA_ASSISTENTE,
    tamanho: (movel, vw, vh) =>
      movel ? { w: vw - 32, h: Math.min(560, vh - 230) } : { w: 440, h: 560 },
    foco: { z: 0.035, x: 0, y: 40, de: 1.9, ate: 3.8 },
    conteudo: (tl) => <PainelDoAssistente tl={tl} />
  }
]
