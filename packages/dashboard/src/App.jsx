import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Header from './components/Header.jsx'
import { Loading } from './components/Async.jsx'
import { useAuth } from './auth/AuthContext.jsx'
import Login from './auth/Login.jsx'

import StationMonitor from './views/StationMonitor.jsx'
import Devices from './views/Devices.jsx'
import Alarms from './views/Alarms.jsx'
import Reports from './views/Reports.jsx'
import Statistics from './views/Statistics.jsx'
import Maintenance from './views/Maintenance.jsx'

import EvCharging from './views/ev/EvCharging.jsx'
import PowerManagement from './views/ev/PowerManagement.jsx'
import SessionCycle from './views/ev/SessionCycle.jsx'
import TariffPayment from './views/ev/TariffPayment.jsx'
import DemandContract from './views/ev/DemandContract.jsx'

export default function App() {
  const { status } = useAuth()

  // Validando o token guardado: evita piscar a tela de login em cada F5.
  if (status === 'checking') {
    return (
      <div className="login-shell">
        <Loading label="Restaurando sessão…" />
      </div>
    )
  }

  if (status !== 'authenticated') return <Login />

  return (
    <div className="shell">
      <Sidebar />
      <div className="main">
        <Header />
        <div className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/station_monitor" replace />} />
            <Route path="/station_monitor" element={<StationMonitor />} />
            <Route path="/device" element={<Devices />} />
            <Route path="/alarm" element={<Alarms />} />
            <Route path="/report" element={<Reports />} />
            <Route path="/statistics" element={<Statistics />} />
            <Route path="/om" element={<Maintenance />} />

            {/* ====== NOVA SEÇÃO: RECARGA EV (conectada à API ChargeGrid) ====== */}
            <Route path="/ev" element={<EvCharging />}>
              <Route index element={<Navigate to="/ev/power" replace />} />
              <Route path="power" element={<PowerManagement />} />
              <Route path="sessions" element={<SessionCycle />} />
              <Route path="tariff" element={<TariffPayment />} />
              <Route path="demand" element={<DemandContract />} />
            </Route>

            <Route path="*" element={<Navigate to="/station_monitor" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
