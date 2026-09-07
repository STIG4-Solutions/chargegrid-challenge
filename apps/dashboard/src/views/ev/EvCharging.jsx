import { NavLink, Outlet } from 'react-router-dom'

// Wrapper da nova seção "Recarga EV": sub-navegação + <Outlet> dos módulos filhos.
const modules = [
  { to: '/ev/power', label: 'Gerenciamento de Potência' },
  { to: '/ev/sessions', label: 'Ciclo da Sessão' },
  { to: '/ev/tariff', label: 'Tarifação & Pagamento' },
  { to: '/ev/demand', label: 'Demanda Contratada' },
  { to: '/ev/utilization', label: 'Ocupação & Retorno' }
]

export default function EvCharging() {
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <h1 className="page-title" style={{ marginBottom: 4 }}>
          Recarga EV
          <span className="badge badge-red" style={{ verticalAlign: 'middle', marginLeft: 8 }}>Novo</span>
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          Gerencie a potência dos pontos, acompanhe o ciclo das sessões e configure políticas de
          tarifação e pagamento.
        </p>
      </div>

      <nav className="subnav">
        {modules.map((m) => (
          <NavLink key={m.to} to={m.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            {m.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  )
}
