import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { power, useApi } from '@chargegrid/sdk'
import SiteSwitcher from '../../components/SiteSwitcher.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { abasDaSecao } from './auditoria.js'

// Wrapper da nova seção "Recarga EV": sub-navegação + <Outlet> dos módulos filhos.
const modules = [
  // Primeira de proposito: e' a leitura de quem decide, e as abas seguintes
  // sao o detalhe operacional de cada pergunta que ela levanta.
  { to: '/ev/analytics', label: 'Analytics' },
  { to: '/ev/power', label: 'Gerenciamento de Potência' },
  { to: '/ev/sessions', label: 'Ciclo da Sessão' },
  { to: '/ev/tariff', label: 'Tarifação & Pagamento' },
  { to: '/ev/demand', label: 'Demanda Contratada' },
  { to: '/ev/utilization', label: 'Ocupação & Retorno' },
  { to: '/ev/priority', label: 'Regras de Prioridade' },
  { to: '/ev/campaigns', label: 'Campanhas' },
  { to: '/ev/contract', label: 'Plano & Contrato' }
]

export default function EvCharging() {
  const sites = useApi(() => power.visibleSites(), [])
  // Troca de praça precisa remontar as telas filhas: elas carregam no mount e
  // guardam o resultado. Sem a chave, o seletor mudaria a URL das próximas
  // requisições e a tela continuaria mostrando os números da praça anterior —
  // o tipo de erro que ninguém percebe, porque a tela parece funcionar.
  const [praca, setPraca] = useState('padrao')

  const { isAdmin } = useAuth()
  const rede = (sites.data?.length ?? 0) > 1
  // A aba de auditoria é de ADMIN, e não "de quem vê mais de uma praça": a rota
  // recusa operador, e uma aba que sempre volta 403 é pior que aba nenhuma.
  const abas = abasDaSecao(modules, { rede, isAdmin })

  return (
    <div>
      <div
        style={{
          marginBottom: 8,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
          flexWrap: 'wrap'
        }}
      >
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Recarga EV
            <span className="badge badge-red" style={{ verticalAlign: 'middle', marginLeft: 8 }}>
              Novo
            </span>
          </h1>
          <p className="muted" style={{ margin: 0 }}>
            Gerencie a potência dos pontos, acompanhe o ciclo das sessões e configure políticas de
            tarifação e pagamento.
          </p>
        </div>
        <SiteSwitcher onTrocar={(id) => setPraca(id || 'padrao')} />
      </div>

      <nav className="subnav">
        {abas.map((m) => (
          <NavLink key={m.to} to={m.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            {m.label}
          </NavLink>
        ))}
      </nav>

      <Outlet key={praca} />
    </div>
  )
}
