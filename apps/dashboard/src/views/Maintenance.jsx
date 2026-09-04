const tickets = [
  { id: 'OM-501', title: 'Inspeção trimestral dos módulos', due: '30/08/2026', status: 'Agendado' },
  { id: 'OM-498', title: 'Substituir medidor MT-METER-01', due: '26/08/2026', status: 'Em andamento' },
  { id: 'OM-490', title: 'Limpeza de placas', due: '20/08/2026', status: 'Concluído' }
]
const cls = (s) => (s === 'Concluído' ? 'badge-green' : s === 'Em andamento' ? 'badge-yellow' : 'badge-blue')

export default function Maintenance() {
  return (
    <div>
      <h1 className="page-title">Operação &amp; Manutenção</h1>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Ticket</th><th>Descrição</th><th>Prazo</th><th>Status</th></tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>{t.title}</td>
                <td className="muted">{t.due}</td>
                <td><span className={'badge ' + cls(t.status)}>{t.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
