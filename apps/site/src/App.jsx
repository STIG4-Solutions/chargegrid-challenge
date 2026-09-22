import { Route, Routes } from 'react-router-dom'
import DownloadPage from './pages/DownloadPage.jsx'
import LandingPage from './pages/LandingPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/download" element={<DownloadPage />} />
    </Routes>
  )
}
