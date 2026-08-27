/**
 * Hooks de dados. React é o mesmo no navegador e no React Native, então estes
 * servem os dois clientes sem alteração — a diferença mora nos componentes.
 */
import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import type { ApiError } from './errors'

export interface UseApiOptions {
  /** Recarga periódica silenciosa, em ms. Zero desliga. */
  pollMs?: number
  enabled?: boolean
  /** Mantém o dado anterior enquanto uma recarga falha. */
  keepPreviousData?: boolean
}

export interface UseApiResult<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  refetch: (opcoes?: { silent?: boolean }) => Promise<void>
  setData: Dispatch<SetStateAction<T | null>>
}

/**
 * Busca com ciclo de vida completo: carregando, erro, recarga e atualização
 * periódica. Substitui o `useState(mock)` que as telas usariam.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: UseApiOptions = {}
): UseApiResult<T> {
  const { pollMs = 0, enabled = true, keepPreviousData = true } = options

  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(enabled)

  // A ref evita recriar o efeito quando o chamador passa uma arrow inline.
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const requestId = useRef(0)

  const run = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!enabled) return
      const id = ++requestId.current
      if (!silent) setLoading(true)
      try {
        const resultado = await fetcherRef.current()
        // Resposta antiga chegando depois da nova: descarta.
        if (id !== requestId.current) return
        setData(resultado)
        setError(null)
      } catch (err) {
        if (id !== requestId.current) return
        setError(err as ApiError)
        if (!keepPreviousData) setData(null)
      } finally {
        if (id === requestId.current) setLoading(false)
      }
    },
    [enabled, keepPreviousData]
  )

  useEffect(() => {
    void run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled])

  // Recarga periódica silenciosa: a tela não pisca a cada ciclo.
  useEffect(() => {
    if (!pollMs || !enabled) return
    const timer = setInterval(() => void run({ silent: true }), pollMs)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs, enabled, ...deps])

  return { data, error, loading, refetch: run, setData }
}

export interface UseActionResult<A extends unknown[], R> {
  run: (...args: A) => Promise<R | null>
  pending: boolean
  error: ApiError | null
  clearError: () => void
}

/**
 * Ação que escreve na API (botão, slider, toggle). Expõe `pending` para
 * desabilitar o controle e `error` para exibir o motivo.
 */
export function useAction<A extends unknown[], R>(
  action: (...args: A) => Promise<R>,
  callbacks: { onSuccess?: (r: R) => void; onError?: (e: ApiError) => void } = {}
): UseActionResult<A, R> {
  const { onSuccess, onError } = callbacks
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const run = useCallback(
    async (...args: A) => {
      setPending(true)
      setError(null)
      try {
        const resultado = await action(...args)
        onSuccess?.(resultado)
        return resultado
      } catch (err) {
        setError(err as ApiError)
        onError?.(err as ApiError)
        return null
      } finally {
        setPending(false)
      }
    },
    [action, onSuccess, onError]
  )

  return { run, pending, error, clearError: () => setError(null) }
}
