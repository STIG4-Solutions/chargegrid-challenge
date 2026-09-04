import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.jsx'
import { configureSdk } from '@chargegrid/sdk'
import { AuthProvider } from './auth/AuthContext.jsx'
import './assets/styles.css'

// Liga o SDK ao ambiente do navegador. No app mobile, a única diferença é
// trocar localStorage por AsyncStorage aqui.
// __API_PADRAO__ vem de config/domains.json, injetado pelo Vite no build.
// VITE_API_URL continua ganhando dele: é assim que se aponta para outro
// ambiente sem tocar em arquivo versionado.
configureSdk({
  baseUrl: import.meta.env?.VITE_API_URL || __API_PADRAO__,
  storage: localStorage
})

// HashRouter => URLs no formato #/... igual ao SEMS+ original
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <HashRouter>
        <App />
      </HashRouter>
    </AuthProvider>
  </React.StrictMode>
)
