/**
 * Sessao do motorista. E a mesma logica do AuthContext do painel — inclusive
 * a hidratacao assincrona, que la existe por causa daqui: o AsyncStorage so
 * responde por Promise.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from 'react'
import {
  auth as authApi,
  hydrateTokens,
  saveTokens,
  type ApiError,
  type Usuario
} from '@chargegrid/sdk'
import { iniciarSdk } from './api'
import * as push from './push'

type Estado = 'checking' | 'anonymous' | 'authenticated'

interface Sessao {
  user: Usuario | null
  status: Estado
  error: string | null
  login: (email: string, senha: string) => Promise<void>
  logout: () => Promise<void>
  /** Rele o perfil na API. Usado depois de mexer na carteira, para o saldo
   *  exibido nao ficar atras do que o servidor ja registrou. */
  recarregarPerfil: () => Promise<void>
  limparErro: () => void
}

const AuthContext = createContext<Sessao | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null)
  const [status, setStatus] = useState<Estado>('checking')
  const [error, setError] = useState<string | null>(null)

  // Configura o SDK antes de qualquer requisicao. O callback derruba a sessao
  // quando o refresh e recusado pelo servidor.
  useEffect(() => {
    iniciarSdk(() => {
      setUser(null)
      setStatus('anonymous')
      setError('Sua sessao expirou. Entre novamente.')
    })
  }, [])

  // Token guardado nao significa sessao valida — confirmamos com /auth/me.
  useEffect(() => {
    if (status !== 'checking') return undefined
    let cancelado = false

    void (async () => {
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
        const falha = err as ApiError
        // API fora do ar nao apaga o token: pode voltar em seguida.
        if (!falha.isOffline) await saveTokens(null)
        else setError(falha.detail)
        setStatus('anonymous')
      }
    })()

    return () => {
      cancelado = true
    }
  }, [status])

  const login = useCallback(async (email: string, senha: string) => {
    setError(null)
    const tokens = await authApi.login(email, senha)
    await saveTokens(tokens)
    const eu = await authApi.me()
    if (eu.role !== 'driver') {
      await saveTokens(null)
      throw new Error('Esta conta e do painel comercial. Use o app com uma conta de motorista.')
    }
    setUser(eu)
    setStatus('authenticated')
    // Depois do login, nao na abertura: pedir permissao de notificacao para
    // quem ainda nao entrou e' pedir antes de haver o que notificar, e a
    // recusa e' permanente - o sistema nao pergunta de novo. Nao aguardamos:
    // registro de push nao pode atrasar a entrada na conta.
    void push.registrar()
  }, [])

  const recarregarPerfil = useCallback(async () => {
    try {
      setUser(await authApi.me())
    } catch {
      // Falha aqui nao derruba a sessao: o saldo exibido apenas continua o antigo.
    }
  }, [])

  const logout = useCallback(async () => {
    // Antes de descartar o token: a chamada precisa do cabecalho de
    // autorizacao. Depois de saveTokens(null) ela sairia sem credencial e o
    // aparelho continuaria recebendo as notificacoes de quem saiu.
    await push.remover()
    await saveTokens(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  const valor = useMemo<Sessao>(
    () => ({
      user,
      status,
      error,
      login,
      logout,
      recarregarPerfil,
      limparErro: () => setError(null)
    }),
    [user, status, error, login, logout, recarregarPerfil]
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth(): Sessao {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>')
  return ctx
}
