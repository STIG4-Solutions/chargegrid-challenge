const devices = [
  {
    sn: 'GW7500-ES-01',
    type: 'Inversor',
    model: 'GW7.5K-ET',
    status: 'online',
    power: '4,2 kW',
    updated: '24/08 09:58'
  },
  {
    sn: 'LX-BAT-01',
    type: 'Bateria',
    model: 'Lynx Home F',
    status: 'online',
    power: '12,0 kW',
    updated: '24/08 09:58'
  },
  {
    sn: 'MT-METER-01',
    type: 'Medidor',
    model: 'GM3000',
    status: 'offline',
    power: '—',
    updated: '23/08 21:10'
  }
]

export default function Devices() {
  return (
    <div>
      <h1 className="page-title">Dispositivos</h1>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="stat">
          <div className="label">Total</div>
          <div className="value">3</div>
        </div>
        <div className="stat">
          <div className="label">Online</div>
          <div className="value" style={{ color: 'var(--sems-green)' }}>
            2
          </div>
        </div>
        <div className="stat">
          <div className="label">Offline</div>
          <div className="value" style={{ color: 'var(--sems-muted)' }}>
            1
          </div>
        </div>
        <div className="stat">
          <div className="label">Em falha</div>
          <div className="value" style={{ color: 'var(--sems-red)' }}>
            0
          </div>
        </div>
      </div>
      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>SN</th>
              <th>Tipo</th>
              <th>Modelo</th>
              <th>Status</th>
              <th>Potência</th>
              <th>Atualizado</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.sn}>
                <td>{d.sn}</td>
                <td>{d.type}</td>
                <td className="muted">{d.model}</td>
                <td>
                  <span
                    className={'badge ' + (d.status === 'online' ? 'badge-green' : 'badge-gray')}
                  >
                    {d.status === 'online' ? 'Online' : 'Offline'}
                  </span>
                </td>
                <td>{d.power}</td>
                <td className="muted">{d.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
