import { num } from '../data/mockData.js'

const days = [
  { d: '18', v: 6.2 }, { d: '19', v: 5.1 }, { d: '20', v: 7.3 }, { d: '21', v: 4.8 },
  { d: '22', v: 6.9 }, { d: '23', v: 5.5 }, { d: '24', v: 1.9 }
]
const max = Math.max(...days.map((x) => x.v))

export default function Statistics() {
  return (
    <div>
      <h1 className="page-title">Estatísticas</h1>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="stat"><div className="label">Geração hoje</div><div className="value">1,9<small>kWh</small></div></div>
        <div className="stat"><div className="label">Geração mês</div><div className="value">148,2<small>kWh</small></div></div>
        <div className="stat"><div className="label">Geração total</div><div className="value">3.631,6<small>kWh</small></div></div>
        <div className="stat"><div className="label">CO₂ evitado</div><div className="value">2,58<small>t</small></div></div>
      </div>
      <div className="panel">
        <div className="card-title">Geração — últimos 7 dias</div>
        <div className="card-sub">kWh por dia</div>
        <div className="bars">
          {days.map((b) => (
            <div className="bar-col" key={b.d}>
              <div className="bar" style={{ height: (b.v / max) * 160 + 'px' }} title={num(b.v) + ' kWh'} />
              <div className="muted">{b.d}/08</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
