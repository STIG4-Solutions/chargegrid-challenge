const reports = [
  { name: 'Geração diária', period: 'Agosto/2026', format: 'PDF' },
  { name: 'Consumo por usina', period: 'Agosto/2026', format: 'XLSX' },
  { name: 'Sessões de recarga EV', period: 'Agosto/2026', format: 'XLSX' }
]

export default function Reports() {
  return (
    <div>
      <h1 className="page-title">Relatórios</h1>
      <div className="grid grid-3">
        {reports.map((r) => (
          <div className="card" key={r.name}>
            <div className="card-title">{r.name}</div>
            <div className="card-sub">Período: {r.period}</div>
            <div className="flex items-center gap-8">
              <span className="badge badge-gray">{r.format}</span>
              <button className="btn btn-sm">Gerar</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
