import { useState } from 'react'
import { useAuth } from './AuthContext.jsx'
import { Spinner } from '../components/Async.jsx'
import { getConfig } from '@chargegrid/sdk'
import logo from '../assets/goodwe_logo_w.d807055f.png'

// Atalhos opcionais de login para avaliar o painel em desenvolvimento.
//
// Nada de credencial no código: os valores vêm do .env local (não versionado) e
// só existem se alguém os definir. Sem eles, os botões simplesmente não
// aparecem. A guarda dupla — variável presente E `import.meta.env.DEV` — garante
// que o bundle de produção não os carregue nem por engano: o empacotador remove
// o ramo morto.
const atalho = (rotulo, email, senha) =>
  email && senha ? [{ label: rotulo, email, password: senha }] : []

const DEMO = import.meta.env.DEV
  ? [
      ...atalho('Operador', import.meta.env.VITE_DEMO_OPERATOR_EMAIL, import.meta.env.VITE_DEMO_OPERATOR_PASSWORD),
      ...atalho('Admin', import.meta.env.VITE_DEMO_ADMIN_EMAIL, import.meta.env.VITE_DEMO_ADMIN_PASSWORD)
    ]
  : []

export default function Login() {
  const { login, error: sessionError, clearError } = useAuth()
  const [form, setForm] = useState({ email: DEMO[0]?.email ?? '', password: DEMO[0]?.password ?? '' })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setPending(true)
    setError(null)
    clearError()
    try {
      await login(form.email, form.password)
    } catch (err) {
      setError(err)
    } finally {
      setPending(false)
    }
  }

  const shown = error || (sessionError ? { detail: sessionError } : null)

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <img src={logo} alt="" className="logo-img" />
          <div>
            <div className="login-title">ChargeGrid Intelligence</div>
            <div className="muted" style={{ fontSize: 12 }}>
              Painel comercial de recarga EV
            </div>
          </div>
        </div>

        <div className="form-row">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="username"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        </div>

        <div className="form-row">
          <label htmlFor="password">Senha</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
        </div>

        {shown && (
          <div className="login-error" role="alert">
            {shown.detail || shown.message}
          </div>
        )}

        <button className="btn btn-primary login-submit" type="submit" disabled={pending}>
          {pending ? <Spinner /> : null}
          {pending ? 'Entrando…' : 'Entrar'}
        </button>

        {/* A flag entra literal na condição: vira `false && …` no build e o bloco some inteiro. */}
        {DEMO.length > 0 && (
        <div className="login-demo">
          <span className="muted">Entrar como:</span>
          {DEMO.map((account) => (
            <button
              key={account.email}
              type="button"
              className="btn btn-sm"
              onClick={() => setForm({ email: account.email, password: account.password })}
            >
              {account.label}
            </button>
          ))}
        </div>
        )}

        <div className="muted login-api">API: {getConfig().baseUrl}</div>
      </form>
    </div>
  )
}
