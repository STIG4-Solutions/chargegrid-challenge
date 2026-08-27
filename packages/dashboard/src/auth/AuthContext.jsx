import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { auth as authApi, configureSdk, hydrateTokens, saveTokens } from '@chargegrid/sdk'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Sempre começa em "checking": o armazenamento pode ser assíncrono (é no
  // React Native), então só depois de hidratar dá para saber se há sessão.
  const [status, setStatus] = useState('checking')
  const [error, setError] = useState(null)

  const logout = useCallback(async () => {
    await saveTokens(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  // O SDK avisa quando a renovação é recusada: aí a sessão acabou mesmo.
  useEffect(() => {
    configureSdk({
      onSessionExpired: () => {
        setUser(null)
        setStatus('anonymous')
        setError('Sua sessão expirou. Entre novamente.')
      }
    })
  }, [])

  // Token guardado não significa sessão válida — confirmamos com /auth/me.
  useEffect(() => {
    if (status !== 'checking') return undefined
    let cancelado = false

    ;(async () => {
      const tokens = await hydrateTokens()
      if (cancelado) return
      if (!tokens) {
        setStatus('anonymous')
        return
      }
      try {
        const eu = await authApi.me()
        if (cancelado) return
        setUser(eu)
        setStatus('authenticated')
      } catch (err) {
        if (cancelado) return
        // Backend fora do ar não deve apagar o token: pode voltar em seguida.
        if (!err.isOffline) await saveTokens(null)
        setStatus('anonymous')
        if (err.isOffline) setError(err.detail)
      }
    })()

    return () => {
      cancelado = true
    }
  }, [status])

  const login = useCallback(async (email, senha) => {
    setError(null)
    const tokens = await authApi.login(email, senha)
    await saveTokens(tokens)
    const eu = await authApi.me()
    setUser(eu)
    setStatus('authenticated')
    return eu
  }, [])

  const value = useMemo(
    () => ({
      user,
      status,
      error,
      isAuthenticated: status === 'authenticated',
      isOperator: user?.role === 'admin' || user?.role === 'operator',
      login,
      logout,
      clearError: () => setError(null)
    }),
    [user, status, error, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>')
  return ctx
}
