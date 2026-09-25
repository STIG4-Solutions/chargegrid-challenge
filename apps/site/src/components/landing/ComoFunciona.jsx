import { useRef } from 'react'
import { ESTADOS_ASSISTENTE, PainelDoAssistente } from './CenaAssistente.jsx'
import { useReducedMotion } from './hooks.js'
import {
  expo,
  janela,
  lerp,
  suave,
  useEncaixeNaChegada,
  useJanela,
  useLinhaDoTempo
} from './linhaDoTempo.js'
import { estadoDaPraca, TelaApp, TelaFatura, TelaPotencia, TelaTravando } from './Telas.jsx'

/**
 * "Como funciona": uma animacao de ~35 s com linha do tempo propria, que toca
 * sozinha quando a secao aparece. NAO e' controlada pela rolagem.
 *
 * O PRINCIPIO E' CONTINUIDADE. Existe um card so'. Entre um estado e outro ele
 * muda de tamanho pela tecnica FLIP - o elemento assume o tamanho novo e nasce
 * escalado para o tamanho antigo, voltando a escala 1 (so' transform) -, e o
 * conteudo troca por esmaecimento e desfoque leve. Nenhuma tela some para outra
 * aparecer do nada.
 */

const MORFO = 0.9 // segundos da mudanca de tamanho do card
const PREDIO_INICIAL = 30
const PREDIO_PICO = 72

const tamanhoPotencia = (movel, vw) => (movel ? { w: vw - 32, h: 520 } : { w: 980, h: 548 })

const predioNoPico = (tl) =>
  PREDIO_INICIAL + (PREDIO_PICO - PREDIO_INICIAL) * suave(janela(tl, 0.4, 2.4))

const ESTADOS = [
  { id: 'abertura', dur: 4.0 },
  {
    id: 'verde',
    dur: 5.0,
    conteudoId: 'potencia',
    legenda: ['Tudo sob controle.', 'Preço normal.'],
    tamanho: tamanhoPotencia,
    foco: { z: 0.05, x: -330, y: -200, de: 2.0, ate: 3.9 },
    conteudo: () => <TelaPotencia predio={PREDIO_INICIAL} />
  },
  {
    id: 'pico',
    dur: 4.6,
    conteudoId: 'potencia',
    legenda: ['Pico no prédio.', 'Potência ajustada sozinha.'],
    tamanho: tamanhoPotencia,
    foco: { z: 0.035, x: 0, y: 90, de: 0.3, ate: 3.3 },
    conteudo: (tl) => <TelaPotencia predio={predioNoPico(tl)} />
  },
  {
    id: 'app',
    dur: 4.4,
    legenda: ['O motorista vê.', 'Antes de plugar.'],
    tamanho: (movel, vw) => ({ w: Math.min(380, vw - 32), h: 256 }),
    foco: { z: 0.06, x: 0, y: -10, de: 0.9, ate: 3.0 },
    conteudo: (tl) => <TelaApp pressionado={tl >= 3.1 && tl < 3.45} />
  },
  {
    id: 'travando',
    dur: 1.8,
    legenda: ['O preço que viu.', 'É o preço que paga.'],
    tamanho: (movel, vw) => ({ w: Math.min(440, vw - 32), h: 140 }),
    entra: [0.3, 0.6],
    conteudo: (tl) => <TelaTravando progresso={expo(janela(tl, 0.45, 1.5))} />
  },
  {
    id: 'fatura',
    dur: 3.6,
    legenda: ['O preço que viu.', 'É o preço que paga.'],
    tamanho: (movel, vw) => (movel ? { w: vw - 32, h: 330 } : { w: 720, h: 300 }),
    foco: { z: 0.05, x: 0, y: 40, de: 1.3, ate: 2.6 },
    conteudo: (tl) => <TelaFatura destaque={suave(janela(tl, 1.2, 1.8))} />
  },
  // Assistente: remover esta linha (e o import) tira a cena inteira.
  ...ESTADOS_ASSISTENTE,
  { id: 'final', dur: 2.8 }
]

// Inicio de cada estado = soma das duracoes anteriores.
let acumulado = 0
for (const e of ESTADOS) {
  e.inicio = acumulado
  acumulado += e.dur
}
const DURACAO = acumulado

function estadoEm(t) {
  for (let i = ESTADOS.length - 1; i >= 0; i--) if (t >= ESTADOS[i].inicio) return i
  return 0
}

/** Zoom suave na informacao do estado: sobe, segura e volta antes da troca. */
function zoomDoFoco(foco, tl) {
  if (!foco) return 0
  const sobe = suave(janela(tl, foco.de, foco.de + 1))
  const desce = suave(janela(tl, foco.ate, foco.ate + 0.7))
  return foco.z * sobe * (1 - desce)
}

function Chip({ x, y, direita = false, visivel, voo, children, className = '' }) {
  // `voo` 0 -> 1: vem de fora (lado oposto a ancora), pousa no lugar.
  const k = expo(voo)
  const dx = (1 - k) * (direita ? 520 : -520)
  const dy = (1 - k) * -40
  return (
    <div
      className={`lp-cf-chip ${className}`}
      style={{
        transform: `translate3d(${x + dx}px, ${y + dy}px, 0)${direita ? ' translateX(-100%)' : ''}`,
        opacity: visivel * Math.min(1, voo * 3)
      }}
    >
      {children}
    </div>
  )
}

function Cursor({ x, y, opacidade, clique }) {
  return (
    <div
      className="lp-cf-cursor"
      style={{ transform: `translate3d(${x}px, ${y}px, 0)`, opacity: opacidade }}
      aria-hidden="true"
    >
      {clique > 0 && clique < 1 && (
        <span
          className="lp-cf-pulso"
          style={{ transform: `scale(${0.4 + clique * 1.4})`, opacity: 0.55 * (1 - clique) }}
        />
      )}
      <svg viewBox="0 0 24 24" width="26" height="26">
        <path
          d="M5 3.5 19 11l-6.2 1.6L9.6 18.8 5 3.5Z"
          fill="#f5f6f8"
          stroke="#0d0d0f"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

function Legenda({ linhas, opacidade }) {
  if (!linhas) return null
  return (
    <p className="lp-legenda" style={{ opacity: opacidade }}>
      <span>{linhas[0]}</span>
      <span className="lp-legenda-acento">{linhas[1]}</span>
    </p>
  )
}

function IconeCG({ tamanho = 64 }) {
  return <img src="/chargegrid-app-icon.png" alt="" width={tamanho} height={tamanho} />
}

// ------------------------------------------------------------ versao estatica

function Estatico() {
  const vermelha = estadoDaPraca(PREDIO_PICO)
  const blocos = [
    {
      chave: 'abertura',
      corpo: (
        <p className="lp-abertura">
          <span>A loja pesou.</span>
          <span className="lp-abertura-segunda">O sistema reagiu.</span>
        </p>
      )
    },
    {
      chave: 'verde',
      legenda: ESTADOS[1].legenda,
      corpo: (
        <div className="lp-cf-card-estatico lp-cf-com-chips">
          <div className="lp-cf-chips-estaticos">
            <span className="lp-cf-chip lp-cf-chip-verde">Bandeira verde · x1,00</span>
          </div>
          <TelaPotencia predio={PREDIO_INICIAL} />
        </div>
      )
    },
    {
      chave: 'pico',
      legenda: ESTADOS[2].legenda,
      corpo: (
        <div className="lp-cf-card-estatico lp-cf-com-chips">
          <div className="lp-cf-chips-estaticos">
            <span className={`lp-cf-chip lp-cf-chip-${vermelha.cor}`}>
              Bandeira {vermelha.cor} · x{vermelha.mult}
            </span>
            <span className="lp-cf-chip">Prédio em 90% do contrato</span>
          </div>
          <TelaPotencia predio={PREDIO_PICO} />
        </div>
      )
    },
    {
      chave: 'app',
      legenda: ESTADOS[3].legenda,
      corpo: (
        <div className="lp-cf-card-estatico lp-cf-card-app">
          <TelaApp />
        </div>
      )
    },
    {
      chave: 'fatura',
      legenda: ESTADOS[5].legenda,
      corpo: (
        <div className="lp-cf-card-estatico lp-cf-card-fatura">
          <TelaFatura destaque={1} />
        </div>
      )
    },
    {
      chave: 'assistente',
      legenda: ESTADOS_ASSISTENTE[0]?.legenda,
      corpo: (
        <div className="lp-cf-card-estatico lp-cf-card-assist">
          <PainelDoAssistente estatico />
        </div>
      )
    },
    {
      chave: 'final',
      corpo: (
        <div className="lp-cf-final lp-cf-final-estatico">
          <IconeCG />
          <p>Decide sozinho. Cobra certo.</p>
        </div>
      )
    }
  ]
  return (
    <div className="lp-cf-estatico">
      {blocos.map((b) => (
        <figure key={b.chave} className="lp-como-figura">
          {b.corpo}
          {b.legenda && (
            <figcaption>
              <Legenda linhas={b.legenda} opacidade={1} />
            </figcaption>
          )}
        </figure>
      ))}
    </div>
  )
}

// ------------------------------------------------------------ animacao

export default function ComoFunciona() {
  const palco = useRef(null)
  const reduzido = useReducedMotion()
  const { w: vw, h: vh } = useJanela()
  const { t, fim, reiniciar } = useLinhaDoTempo(palco, DURACAO, !reduzido)
  useEncaixeNaChegada(palco, !reduzido)

  if (reduzido) {
    return (
      <section id="como-funciona" className="lp-cf lp-estatico" aria-label="Como funciona">
        <Estatico />
      </section>
    )
  }

  const movel = vw < 720
  const i = estadoEm(t)
  const e = ESTADOS[i]
  const tl = t - e.inicio
  const anterior = ESTADOS[i - 1]
  const proximo = ESTADOS[i + 1]

  // ---------- card (FLIP)
  const C = e.tamanho?.(movel, vw, vh)
  const Pant = anterior?.tamanho?.(movel, vw, vh) ?? { w: 80, h: 80 }
  const k = expo(janela(tl, 0, MORFO))
  let card = null
  if (C) {
    const sx = lerp(Pant.w / C.w, 1, k)
    const sy = lerp(Pant.h / C.h, 1, k)
    const nasce = anterior?.tamanho ? 1 : k
    card = { ...C, sx, sy, opacidade: nasce, raio: e.raio ?? 16 }
  } else if (e.id === 'final' && anterior?.tamanho) {
    const P = anterior.tamanho(movel, vw, vh)
    const recua = expo(janela(tl, 0, MORFO))
    card = {
      ...P,
      sx: 1 - 0.15 * recua,
      sy: 1 - 0.15 * recua,
      opacidade: 1 - recua,
      raio: anterior.raio ?? 16
    }
  }

  // ---------- conteudo: entra depois do morfo, sai antes da troca
  const mesmoQueAnterior = anterior?.conteudoId && anterior.conteudoId === e.conteudoId
  const mesmoQueProximo = proximo?.conteudoId && proximo.conteudoId === e.conteudoId
  const [ea, eb] = e.entra ?? [0.3, 0.65]
  const entra = mesmoQueAnterior ? 1 : janela(tl, ea, eb)
  const sai = mesmoQueProximo ? 1 : 1 - janela(tl, e.dur - 0.3, e.dur - 0.02)
  const opConteudo = Math.min(entra, sai)

  // ---------- chips (so' na aba Potencia)
  const potencia = e.conteudoId === 'potencia'
  const Cp = tamanhoPotencia(movel, vw)
  const chipX = -Cp.w / 2 + (movel ? 14 : 22)
  const chipY = -Cp.h / 2 + (movel ? 48 : 60)
  const predio = e.id === 'pico' ? predioNoPico(tl) : PREDIO_INICIAL
  const praca = estadoDaPraca(predio)
  const vooBandeira = e.id === 'verde' ? janela(tl, 1.0, 1.9) : e.id === 'pico' ? 1 : 0
  const vooMotivo = e.id === 'pico' ? janela(tl, 2.6, 3.5) : 0
  const chipsVisiveis = potencia ? (e.id === 'pico' ? sai : 1) : 0

  // ---------- cursor (so' no app)
  let cursor = null
  if (e.id === 'app' && C) {
    const mov = expo(janela(tl, 1.8, 2.9))
    const de = { x: C.w / 2 + 150, y: C.h / 2 + 130 }
    const para = { x: 12, y: C.h / 2 - 44 }
    cursor = {
      x: lerp(de.x, para.x, mov),
      y: lerp(de.y, para.y, mov),
      opacidade: janela(tl, 1.6, 1.9) * (1 - janela(tl, 3.6, 4.0)),
      clique: janela(tl, 3.1, 3.6)
    }
  }

  // ---------- camera
  const camera = 1 + 0.04 * (t / DURACAO)
  const foco = e.foco
  const zf = zoomDoFoco(foco, tl)
  const caber = Math.min(1, (vh - 200) / 580)
  const origem = foco ? `${foco.x}px ${foco.y}px` : '0px 0px'

  // ---------- legenda
  const mesmaLegendaAntes = anterior?.legenda && e.legenda && anterior.legenda[0] === e.legenda[0]
  const mesmaLegendaDepois = proximo?.legenda && e.legenda && proximo.legenda[0] === e.legenda[0]
  const opLegenda = e.legenda
    ? Math.min(
        mesmaLegendaAntes ? 1 : janela(tl, 0.3, 0.8),
        mesmaLegendaDepois ? 1 : 1 - janela(tl, e.dur - 0.35, e.dur)
      )
    : 0

  // ---------- abertura e final
  const abre = i === 0
  const linha1 = janela(t, 0.3, 1.1)
  const linha2 = janela(t, 1.6, 2.4)
  const saiAbertura = 1 - janela(t, 3.5, 4.0)
  const final = e.id === 'final' ? janela(tl, 0.5, 1.3) : 0

  return (
    // ~180vh com o palco fixo: a secao segura a tela por uma rolagem de trackpad
    // antes de liberar. Nada de wheel/touch/teclado e' interceptado.
    <section id="como-funciona" className="lp-cf" aria-label="Como funciona">
      <div className="lp-cf-palco" ref={palco}>
        <span className="lp-cf-brilho lp-cf-brilho-a" aria-hidden="true" />
        <span className="lp-cf-brilho lp-cf-brilho-b" aria-hidden="true" />

        <div className="lp-cf-camera" style={{ transform: `scale(${camera.toFixed(4)})` }}>
          <div
            className="lp-cf-grupo"
            style={{
              transformOrigin: origem,
              transform: `scale(${(caber * (1 + zf)).toFixed(4)})`
            }}
          >
            {abre && (
              <p
                className="lp-abertura lp-cf-abertura"
                style={{
                  opacity: saiAbertura,
                  filter: saiAbertura < 1 ? `blur(${(1 - saiAbertura) * 8}px)` : 'none'
                }}
              >
                <span
                  style={{
                    opacity: linha1,
                    transform: `translate3d(0, ${(1 - expo(linha1)) * 22}px, 0)`
                  }}
                >
                  A loja pesou.
                </span>
                <span
                  className="lp-abertura-segunda"
                  style={{
                    opacity: linha2,
                    transform: `translate3d(0, ${(1 - expo(linha2)) * 22}px, 0)`
                  }}
                >
                  O sistema reagiu.
                </span>
              </p>
            )}

            {card && (
              <div
                className="lp-cf-card"
                style={{
                  width: card.w,
                  height: card.h,
                  borderRadius: card.raio,
                  opacity: card.opacidade,
                  transform: `translate(-50%, -50%) scale(${card.sx.toFixed(4)}, ${card.sy.toFixed(4)})`
                }}
              >
                {e.conteudo && (
                  <div
                    className="lp-cf-conteudo"
                    style={{
                      opacity: opConteudo,
                      filter:
                        opConteudo < 0.98 ? `blur(${((1 - opConteudo) * 6).toFixed(1)}px)` : 'none'
                    }}
                  >
                    {e.conteudo(tl)}
                  </div>
                )}
              </div>
            )}

            {potencia && (
              <>
                <Chip
                  x={chipX}
                  y={chipY}
                  visivel={chipsVisiveis}
                  voo={vooBandeira}
                  className={`lp-cf-chip-${praca.cor}`}
                >
                  <span className={`lp-bolinha lp-bolinha-${praca.cor}`} aria-hidden="true" />
                  Bandeira {praca.cor} · x{praca.mult}
                </Chip>
                <Chip
                  x={movel ? chipX : Cp.w / 2 - 22}
                  y={movel ? chipY + 40 : chipY}
                  direita={!movel}
                  visivel={chipsVisiveis}
                  voo={vooMotivo}
                >
                  Prédio em 90% do contrato
                </Chip>
              </>
            )}

            {cursor && <Cursor {...cursor} />}

            {e.id === 'final' && (
              <div
                className="lp-cf-final"
                style={{
                  opacity: final,
                  transform: `translate(-50%, -50%) translate3d(0, ${(1 - expo(final)) * 18}px, 0)`
                }}
              >
                <IconeCG />
                <p>Decide sozinho. Cobra certo.</p>
              </div>
            )}
          </div>
        </div>

        <Legenda key={e.legenda?.[0] ?? 'nenhuma'} linhas={e.legenda} opacidade={opLegenda} />

        {fim && (
          <button type="button" className="lp-cf-denovo" onClick={reiniciar}>
            Assistir de novo
          </button>
        )}
      </div>
    </section>
  )
}
