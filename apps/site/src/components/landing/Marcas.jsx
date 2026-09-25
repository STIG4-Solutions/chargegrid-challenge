import { Link } from 'react-router-dom'
import { DASHBOARD_URL } from '../../config/landing.js'

/** Icone e nome do ChargeGrid, como no app. */
export function MarcaChargeGrid({ className = '' }) {
  return (
    <span className={`lp-marca ${className}`}>
      <img src="/chargegrid-app-icon.png" alt="" width="28" height="28" />
      <span>ChargeGrid</span>
    </span>
  )
}

/** Logo oficial da GoodWe. Sempre o SVG, nunca texto. */
export function LogoGoodWe({ className = '' }) {
  return (
    <span className={`lp-goodwe ${className}`}>
      <img src="/landing/goodwe-logo.svg" alt="GoodWe" width="92" height="14" />
    </span>
  )
}

/**
 * "Acessar o painel". Sem endereco configurado, rola ate' o fechamento - o
 * botao nunca leva a lugar nenhum.
 */
export function BotaoPainel({ className = 'lp-btn lp-btn-primario' }) {
  const destino = DASHBOARD_URL || '#comecar'
  return (
    <a className={className} href={destino}>
      Acessar o painel
    </a>
  )
}

export function BotaoApp({ className = 'lp-btn lp-btn-secundario' }) {
  return (
    <Link className={className} to="/download">
      Baixar o app
    </Link>
  )
}
