const alarms = [
  {
    id: 'AL-9021',
    device: 'MT-METER-01',
    level: 'Aviso',
    msg: 'Medidor offline',
    time: '23/08 21:10',
    status: 'open'
  },
  {
    id: 'AL-9018',
    device: 'CP-04',
    level: 'Falha',
    msg: 'Ponto de recarga em falha',
    time: '24/08 07:02',
    status: 'open'
  },
  {
    id: 'AL-9010',
    device: 'GW7500-ES-01',
    level: 'Info',
    msg: 'Firmware atualizado',
    time: '22/08 14:30',
    status: 'closed'
  }
]
const cls = (l) => (l === 'Falha' ? 'badge-red' : l === 'Aviso' ? 'badge-yellow' : 'badge-blue')

export default function Alarms() {
  return (
    <div>
      <h1 className="page-title">Alarmes</h1>
      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Dispositivo</th>
              <th>Nível</th>
              <th>Mensagem</th>
              <th>Horário</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {alarms.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td>{a.device}</td>
                <td>
                  <span className={'badge ' + cls(a.level)}>{a.level}</span>
                </td>
                <td>{a.msg}</td>
                <td className="muted">{a.time}</td>
                <td>
                  <span className={'badge ' + (a.status === 'open' ? 'badge-red' : 'badge-gray')}>
                    {a.status === 'open' ? 'Aberto' : 'Resolvido'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
