import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { titleFor } from '../router/titles.js'
import { useAuth } from '../auth/AuthContext.jsx'

export default function Header() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const title = titleFor(pathname)
  const initial = (user?.full_name || user?.email || 'G').charAt(0).toUpperCase()

  useEffect(() => {
    document.title = `SEMS+ · ${title}`
  }, [title])

  return (
    <header className="topbar">
      <h1 className="crumb">{title}</h1>

      <div className="actions">
        <button className="ib" title="Buscar">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </button>
        <button className="ib" title="Alarmes">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
            <path d="M13.7 21a2 2 0 0 1-3.4 0" />
          </svg>
        </button>
        <button className="ib" title="Mensagens">
          <span className="dot" />
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
        <button className="ib" title="Idioma">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
          </svg>
        </button>
        <div className="account">
          <div className="account-info">
            <span className="account-name">{user?.full_name}</span>
            <span className="account-role muted">{user?.role}</span>
          </div>
          <div className="avatar" title={user?.email}>
            {initial}
          </div>
          <button className="btn btn-sm" onClick={logout} title="Sair">
            Sair
          </button>
        </div>
      </div>
    </header>
  )
}
