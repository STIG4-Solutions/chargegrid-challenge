import { useEffect, useState } from 'react'
import { useEntrouNaTela, useReducedMotion } from './hooks.js'

const FATOS = [
  {
    valor: 15,
    unidade: ' min',
    texto: 'A maior média de 15 minutos do mês define a demanda que a loja paga.'
  },
  { valor: 2, unidade: '×', texto: 'Ultrapassar a demanda contratada custa o dobro.' },
  {
    valor: 1,
    unidade: ' mês',
    texto: 'A multa só aparece na fatura seguinte, quando não há mais o que fazer.'
  }
]

const MERCADO = [
  '223 mil carros eletrificados vendidos no Brasil em 2025, 26% a mais que em 2024.',
  '21 mil pontos de recarga públicos, 77% deles em estacionamentos, shoppings e supermercados.',
  'As plataformas atuais cobram e monitoram. Nenhuma controla a demanda do estabelecimento.'
]

/** Conta de 0 ao valor uma unica vez, quando `iniciar` vira true. */
function Contador({ valor, iniciar, reduzido }) {
  const [atual, setAtual] = useState(reduzido ? valor : 0)
  useEffect(() => {
    if (reduzido) return setAtual(valor)
    if (!iniciar) return undefined
    const duracao = 1100
    const t0 = performance.now()
    let quadro = requestAnimationFrame(function passo(t) {
      const x = Math.min(1, (t - t0) / duracao)
      // Desacelera no fim: o numero "assenta" no valor.
      setAtual(Math.round(valor * (1 - Math.pow(1 - x, 3))))
      if (x < 1) quadro = requestAnimationFrame(passo)
    })
    return () => cancelAnimationFrame(quadro)
  }, [iniciar, valor, reduzido])
  return atual
}

export default function Problema() {
  const reduzido = useReducedMotion()
  const [ref, entrou] = useEntrouNaTela({ threshold: 0.4 })

  return (
    <section id="problema" className="lp-secao lp-problema" aria-labelledby="problema-titulo">
      <div className="lp-conteudo">
        <h2 id="problema-titulo" className="lp-h2">
          A conta não é do consumo. É do pico.
        </h2>

        <dl className="lp-fatos" ref={ref}>
          {FATOS.map((f) => (
            <div key={f.texto} className="lp-fato">
              <dt className="lp-fato-numero">
                <span aria-hidden="true">
                  <Contador valor={f.valor} iniciar={entrou} reduzido={reduzido} />
                  {f.unidade}
                </span>
                <span className="lp-so-leitor">
                  {f.valor}
                  {f.unidade}
                </span>
              </dt>
              <dd>{f.texto}</dd>
            </div>
          ))}
        </dl>

        <div className="lp-mercado">
          <ul>
            {MERCADO.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          <p className="lp-fonte">Fonte: ABVE, 2025–2026.</p>
        </div>
      </div>
    </section>
  )
}
