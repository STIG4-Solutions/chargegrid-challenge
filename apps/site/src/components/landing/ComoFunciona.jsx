import { useRef } from 'react'
import { CenaAssistente, LEGENDA_ASSISTENTE } from './CenaAssistente.jsx'
import { faixa, useReducedMotion, useScrollProgress } from './hooks.js'
import { TelaApp, TelaFatura, TelaPotencia } from './Telas.jsx'

const suave = (x) => x * x * (3 - 2 * x)

/**
 * As cenas, em ordem. `foco` e' o ponto da tela para onde o zoom suave vai
 * (transform-origin); `zoom` e' quanto ele aproxima.
 */
const CENAS = [
  { id: 'abertura', legenda: null },
  {
    id: 'verde',
    legenda: ['Tudo sob controle.', 'Preço normal.'],
    foco: '50% 14%',
    zoom: 0.07,
    tela: () => <TelaPotencia predio={30} />
  },
  {
    id: 'pico',
    legenda: ['Pico no prédio.', 'Potência ajustada sozinha.'],
    foco: '50% 55%',
    zoom: 0.04,
    // O consumo do predio sobe de 30 a 72 kW no miolo da cena.
    tela: (t) => <TelaPotencia predio={30 + 42 * suave(faixa(t, 0.18, 0.62))} />
  },
  {
    id: 'app',
    legenda: ['O motorista vê.', 'Antes de plugar.'],
    foco: '50% 58%',
    zoom: 0.09,
    tela: () => <TelaApp />
  },
  {
    id: 'fatura',
    legenda: ['O preço que viu.', 'É o preço que paga.'],
    foco: '50% 62%',
    zoom: 0.08,
    tela: () => <TelaFatura />
  },
  // Cena do assistente: remover esta entrada tira a cena sem mexer no resto.
  {
    id: 'assistente',
    legenda: LEGENDA_ASSISTENTE,
    foco: '50% 45%',
    zoom: 0.04,
    tela: (t, ativa, estatica) => <CenaAssistente ativa={ativa} estatica={estatica} />
  }
]

function Abertura({ t, estatica }) {
  const segunda = estatica ? 1 : faixa(t, 0.32, 0.5)
  return (
    <p className="lp-abertura">
      <span>A loja pesou.</span>
      <span
        className="lp-abertura-segunda"
        style={{ opacity: segunda, transform: `translate3d(0, ${(1 - segunda) * 18}px, 0)` }}
      >
        O sistema reagiu.
      </span>
    </p>
  )
}

function Legenda({ linhas }) {
  if (!linhas) return null
  return (
    <p className="lp-legenda">
      <span>{linhas[0]}</span>
      <span className="lp-legenda-acento">{linhas[1]}</span>
    </p>
  )
}

/** Estado visual de uma cena a partir do tempo local dela (0..1 = no palco). */
function estadoDaCena(t) {
  const entra = faixa(t, 0, 0.14)
  const sai = 1 - faixa(t, 0.86, 1)
  const opacidade = Math.min(entra, sai)
  return {
    opacidade,
    blur: (1 - opacidade) * 10,
    escala: 0.95 + 0.05 * entra,
    zoom: suave(faixa(t, 0.2, 0.8))
  }
}

function Estatico() {
  return (
    <div className="lp-conteudo lp-como-estatico">
      <Abertura t={1} estatica />
      {CENAS.slice(1).map((c) => (
        <figure key={c.id} className="lp-como-figura">
          {c.tela(1, true, true)}
          <figcaption>
            <Legenda linhas={c.legenda} />
          </figcaption>
        </figure>
      ))}
    </div>
  )
}

export default function ComoFunciona() {
  const secao = useRef(null)
  const reduzido = useReducedMotion()
  const p = useScrollProgress(secao, !reduzido)

  if (reduzido) {
    return (
      <section id="como-funciona" className="lp-como lp-estatico" aria-label="Como funciona">
        <Estatico />
      </section>
    )
  }

  const pos = p * CENAS.length
  const atual = Math.min(CENAS.length - 1, Math.floor(pos))

  return (
    <section
      id="como-funciona"
      ref={secao}
      className="lp-como"
      style={{ height: `${100 + CENAS.length * 95}vh` }}
      aria-label="Como funciona"
    >
      <div className="lp-como-palco">
        {CENAS.map((c, i) => {
          const t = pos - i
          if (t < -0.05 || t > 1.05) return null
          const e = estadoDaCena(t)
          const ativa = i === atual && e.opacidade > 0.6
          return (
            <div
              key={c.id}
              className="lp-como-cena"
              style={{
                opacity: e.opacidade,
                filter: e.blur > 0.3 ? `blur(${e.blur.toFixed(1)}px)` : 'none'
              }}
              aria-hidden={!ativa}
            >
              {c.tela ? (
                <div
                  className="lp-como-tela"
                  style={{
                    transformOrigin: c.foco,
                    transform: `scale(${(e.escala * (1 + c.zoom * e.zoom)).toFixed(4)})`
                  }}
                >
                  {c.tela(t, ativa, false)}
                </div>
              ) : (
                <Abertura t={t} />
              )}
              <Legenda linhas={c.legenda} />
            </div>
          )
        })}
      </div>
    </section>
  )
}
