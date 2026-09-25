import { useEntrouNaTela } from './hooks.js'

const ETAPAS = [
  ['Medidor', 'do estabelecimento'],
  ['Rebalanceador', 'a cada 15 s'],
  ['Carregador', 'limite via Modbus'],
  ['Sessão', 'preço travado ao plugar'],
  ['Fatura', 'o preço que o motorista viu']
]

const PONTOS = [
  {
    titulo: 'Decide a cada 15 segundos.',
    texto: 'Lê prédio, solar e bateria e redistribui a potência antes do contrato estourar.'
  },
  {
    titulo: 'Preço travado ao plugar.',
    texto: 'Mudanças da bandeira valem para a próxima recarga, nunca para a que já começou.'
  },
  {
    titulo: 'Previsão que se declara.',
    texto:
      'O modelo de demanda só é usado quando mede melhor que uma média móvel. Quando não mede, o painel diz isso.'
  },
  {
    titulo: 'Protocolo aberto.',
    texto: 'Comunicação via Modbus, compatível com o carregador HCA G2 da',
    goodwe: true
  }
]

/** Diagrama horizontal (desktop): cinco nos numa linha, a energia passando. */
function FluxoHorizontal() {
  const x = (i) => 120 + i * 215
  return (
    <svg
      className="lp-fluxo lp-fluxo-h"
      viewBox="0 0 1100 150"
      role="img"
      aria-labelledby="fluxo-h"
    >
      <title id="fluxo-h">
        Medidor do estabelecimento, rebalanceador a cada 15 segundos, carregador com limite via
        Modbus, sessão com preço travado ao plugar, fatura.
      </title>
      <path className="lp-fluxo-trilho" d="M120 44 H980" />
      <path className="lp-fluxo-energia" d="M120 44 H980" pathLength="1" />
      {ETAPAS.map(([nome, sub], i) => (
        <g key={nome} transform={`translate(${x(i)} 44)`}>
          <circle className="lp-fluxo-no" r="11" />
          <circle className="lp-fluxo-miolo" r="4" />
          <text className="lp-fluxo-nome" y="46" textAnchor="middle">
            {nome}
          </text>
          <text className="lp-fluxo-sub" y="70" textAnchor="middle">
            {sub}
          </text>
        </g>
      ))}
    </svg>
  )
}

/** Diagrama vertical (celular): o mesmo fluxo, de cima para baixo. */
function FluxoVertical() {
  const y = (i) => 20 + i * 92
  return (
    <svg className="lp-fluxo lp-fluxo-v" viewBox="0 0 320 420" aria-hidden="true">
      <path className="lp-fluxo-trilho" d="M20 20 V388" />
      <path className="lp-fluxo-energia" d="M20 20 V388" pathLength="1" />
      {ETAPAS.map(([nome, sub], i) => (
        <g key={nome} transform={`translate(20 ${y(i)})`}>
          <circle className="lp-fluxo-no" r="11" />
          <circle className="lp-fluxo-miolo" r="4" />
          <text className="lp-fluxo-nome" x="30" y="-2">
            {nome}
          </text>
          <text className="lp-fluxo-sub" x="30" y="20">
            {sub}
          </text>
        </g>
      ))}
    </svg>
  )
}

export default function Tecnologia() {
  const [ref, entrou] = useEntrouNaTela({ threshold: 0.45 })
  return (
    <section id="tecnologia" className="lp-secao lp-tecnologia" aria-labelledby="tecnologia-titulo">
      <div className="lp-conteudo">
        <h2 id="tecnologia-titulo" className="lp-h2">
          Por trás de cada decisão.
        </h2>

        <div ref={ref} className={`lp-fluxo-caixa ${entrou ? 'lp-entrou' : ''}`}>
          <FluxoHorizontal />
          <FluxoVertical />
        </div>

        <ul className="lp-pontos">
          {PONTOS.map((p) => (
            <li key={p.titulo}>
              <h3>{p.titulo}</h3>
              <p>
                {p.texto}
                {p.goodwe && (
                  <>
                    {' '}
                    <img
                      className="lp-pontos-goodwe"
                      src="/landing/goodwe-logo.svg"
                      alt="GoodWe"
                      width="74"
                      height="11"
                    />
                    .
                  </>
                )}
              </p>
            </li>
          ))}
        </ul>

        <p className="lp-numeros">
          <span>100+ endpoints na API</span>
          <span>800+ testes automatizados</span>
          <span>3 aplicações integradas</span>
        </p>
      </div>
    </section>
  )
}
