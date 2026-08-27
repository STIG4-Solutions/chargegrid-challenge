// Dados simulados das telas-réplica do SEMS+ (usinas e estatísticas).
//
// A seção Recarga EV NÃO usa este arquivo: ela consome a API ChargeGrid
// (backend/), via o SDK (packages/sdk). O cenário equivalente é criado pelo
// seed do backend (python -m app.seed), com os mesmos códigos de ponto e tarifas.

export const stations = [
  {
    id: 'st-001',
    name: 'LAB FIAP Eco Station',
    shared: true,
    address: 'Av. Lins de Vasconcelos, 1264 - São Paulo',
    capacity: '7,5 kW',
    status: 'operating',
    todayKwh: 1.9,
    totalKwh: 3631.6,
    yield: 0.31,
    power: 0.0,
    // ilustração embutida (SVG data URI) — funciona 100% offline
    img:
      "data:image/svg+xml;utf8," +
      encodeURIComponent(
        `<svg xmlns='http://www.w3.org/2000/svg' width='180' height='120' viewBox='0 0 180 120'>
          <rect width='180' height='120' fill='#1b2a3a'/>
          <rect width='180' height='64' y='56' fill='#25415c'/>
          <g fill='#2f6fb0' stroke='#7fb3e8' stroke-width='1'>
            <rect x='18' y='20' width='34' height='22'/><rect x='54' y='20' width='34' height='22'/>
            <rect x='90' y='20' width='34' height='22'/><rect x='126' y='20' width='34' height='22'/>
            <rect x='18' y='44' width='34' height='22'/><rect x='54' y='44' width='34' height='22'/>
            <rect x='90' y='44' width='34' height='22'/><rect x='126' y='44' width='34' height='22'/>
          </g>
          <circle cx='150' cy='24' r='12' fill='#ffcc00' opacity='.9'/>
          <rect x='0' y='92' width='180' height='28' fill='#2e7d4f'/>
        </svg>`
      )
  }
]

// helpers de formatação
export const brl = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)

export const num = (v, d = 2) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }).format(v || 0)
