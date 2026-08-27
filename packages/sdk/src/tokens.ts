import { chaveTokens, getConfig } from './config'

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type?: string
  expires_in?: number
}

/**
 * Cache em memória do par de tokens.
 *
 * O armazenamento pode ser assíncrono (React Native), mas partes do código
 * precisam do token de forma síncrona — a URL do WebSocket, por exemplo. O
 * cache resolve isso e ainda evita ir ao disco a cada requisição.
 */
let cache: TokenPair | null = null
let hidratado = false

/** Lê o armazenamento uma vez e popula o cache. Chame no bootstrap do app. */
export async function hydrateTokens(): Promise<TokenPair | null> {
  try {
    const cru = await getConfig().storage.getItem(chaveTokens)
    cache = cru ? (JSON.parse(cru) as TokenPair) : null
  } catch {
    // Armazenamento indisponível ou conteúdo corrompido: segue sem sessão.
    cache = null
  }
  hidratado = true
  return cache
}

export const tokensHidratados = (): boolean => hidratado
export const currentTokens = (): TokenPair | null => cache
export const accessToken = (): string | null => cache?.access_token ?? null

export async function saveTokens(tokens: TokenPair | null): Promise<void> {
  cache = tokens
  hidratado = true
  const { storage } = getConfig()
  try {
    if (tokens) await storage.setItem(chaveTokens, JSON.stringify(tokens))
    else await storage.removeItem(chaveTokens)
  } catch {
    // Falha ao persistir não derruba a sessão em curso: o cache ainda vale.
  }
}
