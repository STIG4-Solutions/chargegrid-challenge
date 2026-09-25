import { BotaoPainel, MarcaChargeGrid } from './Marcas.jsx'

export default function Cabecalho() {
  return (
    <header className="lp-cabecalho">
      <nav className="lp-cabecalho-barra" aria-label="Principal">
        <a className="lp-cabecalho-marca" href="#inicio" aria-label="ChargeGrid, início">
          <MarcaChargeGrid />
        </a>
        <ul className="lp-ancoras">
          <li>
            <a href="#problema">O problema</a>
          </li>
          <li>
            <a href="#como-funciona">Como funciona</a>
          </li>
          <li>
            <a href="#tecnologia">Tecnologia</a>
          </li>
        </ul>
        <BotaoPainel className="lp-btn lp-btn-primario lp-btn-pilula" />
      </nav>
    </header>
  )
}
