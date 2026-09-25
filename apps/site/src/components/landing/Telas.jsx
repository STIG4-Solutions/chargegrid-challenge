/**
 * Telas da plataforma recriadas em HTML/CSS, com os tokens, a tipografia e a
 * hierarquia reais do painel (apps/dashboard) e do app (apps/mobile). Nada e'
 * print: sao componentes, e os numeros vem das props para a conta fechar.
 *
 * Aqui elas sao o CONTEUDO do card unico do "Como funciona": nao desenham
 * fundo proprio - o fundo e' o card, que muda de tamanho entre os estados.
 */

export const kw = (v, casas = 1) =>
  new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas
  }).format(v)

// Mesma regra de services/bandeira.py: bordas pertencem a faixa de cima.
export function bandeiraDaFolga(folga) {
  if (folga >= 0.5) return { cor: 'verde', mult: '1,00' }
  if (folga >= 0.2) return { cor: 'amarela', mult: '1,15' }
  return { cor: 'vermelha', mult: '1,30' }
}

export const CONTRATO_KW = 80

/** Tudo o que a aba Potencia mostra sai do consumo do predio, como no rateio. */
export function estadoDaPraca(predio) {
  const livre = Math.max(0, CONTRATO_KW - predio)
  const porPonto = Math.min(11, livre / 4)
  const folga = livre / CONTRATO_KW
  return { livre, porPonto, folga, ...bandeiraDaFolga(folga) }
}

/**
 * Aba Potencia da "Praca Centro". Contrato 80 kW, 4 carregadores de 11 kW.
 * A linha logo abaixo do titulo fica vazia: e' onde os chips da bandeira e do
 * motivo pousam, vindos de fora do card.
 */
export function TelaPotencia({ predio }) {
  const { livre, porPonto } = estadoDaPraca(predio)
  const pctContrato = Math.round((predio / CONTRATO_KW) * 100)

  return (
    <div className="lp-ui lp-ui-painel">
      <div className="lp-ui-topo">
        <span className="lp-ui-praca">Praça Centro</span>
        <span className="lp-ui-muted">Recarga EV · Gerenciamento de Potência</span>
      </div>
      <div className="lp-ui-chips-espaco" aria-hidden="true" />
      <div className="lp-ui-stats">
        <div className="lp-ui-stat">
          <div className="lp-ui-label">Potência disponível no site</div>
          <div className="lp-ui-value">
            {kw(livre)}
            <small>kW</small>
          </div>
          <div className="lp-ui-trend lp-ui-muted">
            Contrato {CONTRATO_KW} − Prédio {kw(predio, 0)}
          </div>
        </div>
        <div className="lp-ui-stat">
          <div className="lp-ui-label">Consumo do prédio</div>
          <div className="lp-ui-value">
            {kw(predio)}
            <small>kW</small>
          </div>
          <div className="lp-ui-trend lp-ui-muted">{pctContrato}% do contrato</div>
        </div>
        <div className="lp-ui-stat">
          <div className="lp-ui-label">Potência alocada (limites)</div>
          <div className="lp-ui-value">
            {kw(porPonto * 4)}
            <small>kW</small>
          </div>
          <div className="lp-ui-trend lp-ui-muted">Dentro do limite</div>
        </div>
        <div className="lp-ui-stat">
          <div className="lp-ui-label">Pontos ativos</div>
          <div className="lp-ui-value">
            4<small>/ 4</small>
          </div>
          <div className="lp-ui-trend lp-ui-muted">carregando agora</div>
        </div>
      </div>
      <div className="lp-ui-panel">
        <div className="lp-ui-predio">
          <span className="lp-ui-card-title">Consumo do prédio</span>
          <span className="lp-ui-meter lp-ui-meter-predio" aria-hidden="true">
            <span style={{ transform: `scaleX(${predio / CONTRATO_KW})` }} />
          </span>
          <span className="lp-ui-kw">
            {kw(predio, 0)} de {CONTRATO_KW} kW
          </span>
        </div>
        <ul className="lp-ui-pontos">
          {['01', '02', '03', '04'].map((n) => (
            <li key={n}>
              <span className="lp-ui-ponto-nome">
                CP-{n}
                <span className="lp-ui-muted">Ponto de Recarga {n}</span>
              </span>
              <span className="lp-badge lp-badge-azul">Carregando</span>
              <span className="lp-ui-meter" aria-hidden="true">
                <span style={{ transform: `scaleX(${porPonto / 11})` }} />
              </span>
              <span className="lp-ui-kw">{kw(porPonto)} kW</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** Card de um ponto no app do motorista (StationScreen + BandeiraDoPonto). */
export function TelaApp({ pressionado = false }) {
  return (
    <div className="lp-ui lp-ui-app">
      <div className="lp-ui-app-nome">Ponto de Recarga 02</div>
      <div className="lp-ui-app-meta">Praça Centro · CP-02 · Type 2 · 11 kW</div>
      <span className="lp-ui-etiqueta lp-ui-etiqueta-vermelha">Bandeira vermelha · x1,30</span>
      <div className="lp-ui-app-preco">R$ 2,34/kWh se iniciar agora</div>
      <div className="lp-ui-app-motivo">Prédio em 90% do contrato</div>
      <div className={`lp-ui-app-botao ${pressionado ? 'lp-pressionado' : ''}`}>
        Iniciar recarga
      </div>
    </div>
  )
}

/** A sessao comecando: o preco da bandeira fica gravado nela. */
export function TelaTravando({ progresso }) {
  return (
    <div className="lp-ui lp-ui-travando">
      <div className="lp-ui-travando-linha">
        <span className="lp-assist-spinner" aria-hidden="true" />
        <strong>Travando o preço…</strong>
      </div>
      <div className="lp-ui-muted">Bandeira vermelha · x1,30 · R$ 2,34/kWh</div>
      <span className="lp-ui-progresso" aria-hidden="true">
        <span style={{ transform: `scaleX(${progresso})` }} />
      </span>
    </div>
  )
}

/** Fatura de uma sessao, como o Ciclo da Sessao e o recibo mostram. */
export function TelaFatura({ destaque = 0 }) {
  return (
    <div className="lp-ui lp-ui-fatura">
      <div className="lp-ui-topo">
        <span className="lp-ui-praca">Fatura INV-2041</span>
        <span className="lp-badge lp-badge-cinza">Emitida</span>
      </div>
      <div className="lp-ui-muted lp-ui-fatura-sub">Sessão SES-20483 · CP-02 · Praça Centro</div>
      <table className="lp-ui-tabela">
        <thead>
          <tr>
            <th>Descrição</th>
            <th>Quantidade</th>
            <th>Preço</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Energia — Tarifa padrão</td>
            <td>18,4 kWh</td>
            <td>R$ 1,80</td>
            <td>R$ 33,12</td>
          </tr>
          <tr className="lp-ui-linha-bandeira" style={{ '--lp-destaque': destaque.toFixed(3) }}>
            <td>Bandeira vermelha (x1,30)</td>
            <td>1 un</td>
            <td>R$ 9,94</td>
            <td>R$ 9,94</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colSpan="3">Total</td>
            <td>R$ 43,06</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
