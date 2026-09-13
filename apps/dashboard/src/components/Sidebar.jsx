import { NavLink, useLocation } from 'react-router-dom'
import logo from '../assets/goodwe_logo_w.d807055f.png'

// Ícones SVG (stroke) inline, no estilo do SEMS+.
const icons = {
  station: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 10.5 12 4l8 6.5" />
      <path d="M6 10v9h12v-9" />
      <path d="M12 9.2c-1.2 1-1.2 2.3-.2 3 .9.6.9 1.6.2 2.3" />
    </svg>
  ),
  device: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="5" width="18" height="6" rx="1.5" />
      <rect x="3" y="13" width="18" height="6" rx="1.5" />
      <path d="M7 8h.01M7 16h.01" />
    </svg>
  ),
  alarm: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  ),
  report: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h4" />
    </svg>
  ),
  chart: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-9-9v9z" />
      <path d="M13 3a8 8 0 0 1 8 8h-8z" />
    </svg>
  ),
  health: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20.8 6.6a5 5 0 0 0-8.8-1.6A5 5 0 0 0 3.2 6.6C1.5 10 5 14 12 19c7-5 10.5-9 8.8-12.4" />
      <path d="M7 12h3l1.5-3 2 5 1.5-2h2" />
    </svg>
  ),
  ev: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="4" y="4" width="10" height="16" rx="2" />
      <path d="M4 9h10" />
      <path d="M9.5 12.2 7.8 15h2.4l-1.7 2.8" />
      <path d="M17 8l2.5 2.5a2 2 0 0 1 .5 1.4V16a1.5 1.5 0 0 0 3 0v-6" />
    </svg>
  ),
  org: (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3 2 8.5 12 14l10-5.5z" />
      <path d="M5 11v5l7 3.5 7-3.5v-5" />
    </svg>
  )
}

// Itens do menu lateral. O item "ev" é a NOVA seção.
const items = [
  { key: 'station_monitor', to: '/station_monitor', label: 'Usinas', icon: 'station' },
  { key: 'device', to: '/device', label: 'Dispositivos', icon: 'device' },
  { key: 'alarm', to: '/alarm', label: 'Alarmes', icon: 'alarm' },
  { key: 'report', to: '/report', label: 'Relatórios', icon: 'report' },
  { key: 'statistics', to: '/statistics', label: 'Estatísticas', icon: 'chart' },
  { key: 'om', to: '/om', label: 'O&M', icon: 'health' },
  { key: 'ev', to: '/ev', label: 'Recarga EV', icon: 'ev', isNew: true }
]

export default function Sidebar() {
  const { pathname } = useLocation()
  const isActive = (to) => pathname.startsWith(to)

  return (
    <aside className="sider">
      <div className="logo" title="SEMS+ (Local)">
        <img src={logo} alt="SEMS+" className="logo-img" />
        <span className="logo-text">SEMS+</span>
      </div>

      <nav className="menu">
        {items.map((it) => (
          <NavLink
            key={it.key}
            to={it.to}
            className={'menu-item' + (isActive(it.to) ? ' active' : '')}
            title={it.label}
          >
            <span className="ic">{icons[it.icon]}</span>
            {it.isNew && <span className="dot-new" />}
            <span className="tip">{it.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="menu bottom">
        <a className="menu-item" title="Organização" onClick={(e) => e.preventDefault()}>
          <span className="ic">{icons.org}</span>
          <span className="tip">Organização</span>
        </a>
      </div>
    </aside>
  )
}
