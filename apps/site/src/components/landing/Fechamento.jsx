import { DEMO_PASSWORD, DEMO_USER } from '../../config/landing.js'
import { BotaoApp, BotaoPainel, CompativelGoodWe, MarcaChargeGrid } from './Marcas.jsx'

const LOJISTA = [
  'Nova receita sem obra na rede elétrica.',
  'Sem multa de demanda.',
  'Saber qual ponto se paga.',
  'Prioridade com nome e horário.',
  'Várias praças num painel.'
]

const MOTORISTA = [
  'Preço antes de plugar.',
  'Sugestão do horário mais barato.',
  'Limite por kWh, tempo ou valor.',
  'Histórico e recibo.'
]

export function Fechamento() {
  return (
    <section id="comecar" className="lp-fechamento" aria-labelledby="comecar-titulo">
      <div className="lp-fechamento-fundo" aria-hidden="true" />
      <div className="lp-conteudo lp-fechamento-conteudo">
        <h2 id="comecar-titulo" className="lp-fechamento-titulo">
          Receita para o lojista. Preço justo para o motorista.
        </h2>

        <div className="lp-colunas">
          <div>
            <h3>Para o lojista</h3>
            <ul>
              {LOJISTA.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Para o motorista</h3>
            <ul>
              {MOTORISTA.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="lp-botoes">
          <BotaoPainel />
          <BotaoApp />
        </div>
        {DEMO_USER && (
          <p className="lp-demo">
            Acesso de demonstração: usuário {DEMO_USER}, senha {DEMO_PASSWORD}
          </p>
        )}
      </div>
    </section>
  )
}

export function Rodape() {
  return (
    <footer className="lp-rodape">
      <div className="lp-conteudo lp-rodape-linha">
        <MarcaChargeGrid />
        <CompativelGoodWe />
        <BotaoApp className="lp-rodape-link" />
        <span className="lp-rodape-ano">© {new Date().getFullYear()} ChargeGrid</span>
      </div>
    </footer>
  )
}
