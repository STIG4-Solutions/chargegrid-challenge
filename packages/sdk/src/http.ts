import { apiUrl, getConfig } from './config'
import { ApiError } from './errors'
import {
  accessToken,
  currentTokens,
  hydrateTokens,
  saveTokens,
  tokensHidratados,
  type TokenPair
} from './tokens'

export type Metodo = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  method?: Metodo
  body?: unknown
  params?: Record<string, string | number | boolean | undefined | null>
  auth?: boolean
  retry?: boolean
  /**
   * Devolve o corpo cru em vez de fazer JSON.parse.
   *
   * Existe para o recibo, que a API entrega em HTML. Sem isto a tela teria de
   * chamar `fetch` direto e montar o cabecalho de autorizacao na mao — e a
   * regra de que nenhuma tela fala HTTP e' o que mantem renovacao de token e
   * traducao de erro num lugar so'.
   */
  texto?: boolean
}

// Uma única renovação em voo: várias requisições que tomam 401 ao mesmo tempo
// esperam a mesma promise, em vez de dispararem N refreshes concorrentes.
let renovando: Promise<TokenPair | null> | null = null

async function renovarToken(): Promise<TokenPair | null> {
  const { onSessionExpired } = getConfig()
  const refresh = currentTokens()?.refresh_token
  if (!refresh) return null

  renovando =
    renovando ??
    fetch(apiUrl('/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh })
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('refresh recusado')
        const novos = (await res.json()) as TokenPair
        await saveTokens(novos)
        return novos
      })
      .catch(async () => {
        await saveTokens(null)
        onSessionExpired?.()
        return null
      })
      .finally(() => {
        renovando = null
      })

  return renovando
}

async function traduzirErro(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`
  let detail = res.statusText || 'erro na requisição'
  try {
    const corpo = (await res.json()) as Record<string, unknown>
    // Erro de domínio responde {code, detail}; HTTPException, só {detail}.
    if (typeof corpo?.code === 'string') code = corpo.code
    const bruto = corpo?.detail
    if (typeof bruto === 'string') detail = bruto
    else if (Array.isArray(bruto)) {
      // Validação do FastAPI: junta as mensagens por campo.
      detail = bruto
        .map((e: { loc?: unknown[]; msg?: string }) => `${e.loc?.slice(1).join('.')}: ${e.msg}`)
        .join('; ')
    }
  } catch {
    // Corpo não-JSON: mantém o statusText.
  }
  return new ApiError(res.status, code, detail)
}

/**
 * Monta, envia, renova o token em 401 e traduz erro — tudo menos ler o corpo.
 *
 * Separado de `request` por causa do fluxo do assistente: a resposta dele é
 * lida aos pedaços, e ler o corpo inteiro aqui esperaria a resposta acabar.
 * O resto — site_id, Bearer, a renovação, a tradução de erro — tem de ser o
 * mesmo, senão o fluxo seria o único caminho do SDK com regras próprias.
 */
async function enviar(
  caminho: string,
  opcoes: RequestOptions,
  signal?: AbortSignal
): Promise<Response> {
  const { method = 'GET', body, params, auth = true, retry = true } = opcoes

  if (!tokensHidratados()) await hydrateTokens()

  const url = new URL(apiUrl(caminho))
  // O site escolhido entra antes dos params da chamada, para que uma rota que
  // passe o próprio site_id explicitamente continue vencendo o seletor.
  const { siteId } = getConfig()
  if (siteId) url.searchParams.set('site_id', siteId)
  if (params) {
    for (const [chave, valor] of Object.entries(params)) {
      if (valor !== undefined && valor !== null && valor !== '') {
        url.searchParams.set(chave, String(valor))
      }
    }
  }

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = accessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let res: Response
  try {
    res = await fetch(url.toString(), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal
    })
  } catch (erro) {
    // Cancelado por quem chamou (botão parar): não é falta de rede, e a tela
    // não deve dizer que o backend caiu.
    if (signal?.aborted) throw erro
    throw new ApiError(
      0,
      'network',
      `Sem conexão com a API (${getConfig().baseUrl}). O backend está no ar?`
    )
  }

  // Token expirado: renova uma vez e repete a requisição original.
  if (res.status === 401 && auth && retry) {
    const novos = await renovarToken()
    if (novos) return enviar(caminho, { ...opcoes, retry: false }, signal)
  }

  if (!res.ok) throw await traduzirErro(res)
  return res
}

export async function request<T>(caminho: string, opcoes: RequestOptions = {}): Promise<T> {
  const res = await enviar(caminho, opcoes)
  if (res.status === 204) return undefined as T
  const texto = await res.text()
  if (opcoes.texto) return texto as T
  return (texto ? JSON.parse(texto) : undefined) as T
}

/**
 * POST cuja resposta chega aos pedaços (`text/event-stream`).
 *
 * Erros ANTES do fluxo abrir — 401 sem refresh, 404, 409, 422, 429 — chegam
 * como `ApiError`, iguais a qualquer outra chamada. Depois de aberto, o que
 * der errado vem como evento dentro do próprio fluxo.
 */
export async function streamRequest(
  caminho: string,
  body: unknown,
  { signal }: { signal?: AbortSignal } = {}
): Promise<ReadableStream<Uint8Array>> {
  const res = await enviar(caminho, { method: 'POST', body }, signal)
  if (!res.body) {
    throw new ApiError(0, 'stream_unsupported', 'Este ambiente não lê respostas em fluxo.')
  }
  return res.body
}

export const api = {
  get: <T>(p: string, params?: RequestOptions['params']) => request<T>(p, { params }),
  post: <T>(p: string, body?: unknown, params?: RequestOptions['params']) =>
    request<T>(p, { method: 'POST', body, params }),
  put: <T>(p: string, body?: unknown) => request<T>(p, { method: 'PUT', body }),
  patch: <T>(p: string, body?: unknown) => request<T>(p, { method: 'PATCH', body }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
  /** GET que devolve o corpo como texto (HTML, CSV) em vez de JSON. */
  getText: (p: string) => request<string>(p, { texto: true })
}
