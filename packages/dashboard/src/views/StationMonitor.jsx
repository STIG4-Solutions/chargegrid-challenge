import { useState } from 'react'
import { stations, num } from '../data/mockData.js'

const tabs = [
  { key: 'all', label: 'Todos' },
  { key: 'month', label: 'Criados este mês' },
  { key: 'operating', label: 'Em operação', dot: 'green' },
  { key: 'waiting', label: 'Aguardando', dot: 'yellow' },
  { key: 'offline', label: 'Offline', dot: 'gray' },
  { key: 'fault', label: 'Falha', dot: 'red' },
  { key: 'building', label: 'Em construção', dot: 'blue' }
]

const count = (key) => {
  if (key === 'all') return stations.length
  if (key === 'operating') return stations.filter((s) => s.status === 'operating').length
  return 0
}

export default function StationMonitor() {
  const [active, setActive] = useState('all')
  const rows = active === 'all' || active === 'operating' ? stations : []

  return (
    <div>
      <h1 className="page-title">Lista de usinas</h1>

      <div className="panel deep">
        <div className="filterbar">
          <button className="btn">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5h18l-7 8v6l-4-2v-4z" /></svg>
            Filtro
          </button>
          <input className="input" placeholder="Nome da planta, nome ou SN do dispositivo" />
          <input className="input" placeholder="Endereço da usina" />
          <input className="input" placeholder="Email" />
          <button className="btn btn-icon">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
          </button>
          <button className="btn btn-icon" title="Recarregar">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
          </button>
          <button className="btn btn-primary nova">+ Nova usina</button>
        </div>

        <div className="tabs">
          {tabs.map((t) => (
            <div
              key={t.key}
              className={'tab' + (active === t.key ? ' active' : '')}
              onClick={() => setActive(t.key)}
            >
              {t.dot && <span className={'s-dot ' + t.dot} />}
              {t.label}
              <span className="count">({count(t.key)})</span>
            </div>
          ))}
        </div>

        <table className="table stations">
          <thead>
            <tr>
              <th>Informações da usina</th>
              <th>Status da usina</th>
              <th>Geração de hoje (kWh)</th>
              <th>Geração total (kWh)</th>
              <th>Rendimento Específico (kWh/kWp)</th>
              <th>Potência FV (kW)</th>
              <th>Operação</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>
                  <div className="st-info">
                    <img src={s.img} alt="" className="thumb" />
                    <div>
                      <div className="st-name">
                        {s.name}
                        {s.shared && <span className="badge badge-green">Compartilhado</span>}
                      </div>
                      <div className="muted">{s.address}</div>
                      <div className="muted cap">▣ {s.capacity}</div>
                    </div>
                  </div>
                </td>
                <td><span className="badge badge-green">✓ Em operação</span></td>
                <td>{num(s.todayKwh)}</td>
                <td>{num(s.totalKwh)}</td>
                <td>{num(s.yield)}</td>
                <td>{num(s.power)}</td>
                <td>
                  <div className="ops">
                    <span className="op">☆</span>
                    <span className="op">⋯</span>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 40 }}>
                  Nenhuma usina neste filtro.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="pager">
          <button className="pg" disabled>‹</button>
          <button className="pg active">1</button>
          <button className="pg" disabled>›</button>
          <select className="input pgsize"><option>15 / página</option></select>
        </div>
      </div>
    </div>
  )
}
