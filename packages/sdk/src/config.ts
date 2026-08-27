import { memoryStorage, type TokenStorage } from './storage'

export interface SdkConfig {
  /** Ex.: https://api.chargegrid.com.br — sem barra no fim. */
  baseUrl: string
  /** `localStorage` na web, `AsyncStorage` no React Native. */
  storage: TokenStorage
  /** Chamado quando a renovação do token é recusada e a sessão morre. */
  onSessionExpired?: () => void
}

const PREFIXO_API = '/api/v1'
const CHAVE_TOKENS = 'chargegrid.tokens'

let config: SdkConfig = {
  baseUrl: 'http://localhost:8000',
  storage: memoryStorage()
}

/**
 * Liga o SDK ao ambiente. Chame uma vez no bootstrap do app, antes de
 * qualquer requisição — é aqui que web e mobile divergem, e só aqui.
 */
export function configureSdk(parcial: Partial<SdkConfig>): void {
  config = { ...config, ...parcial }
  if (parcial.baseUrl) config.baseUrl = parcial.baseUrl.replace(/\/$/, '')
}

export const getConfig = (): SdkConfig => config
export const apiUrl = (caminho: string): string => `${config.baseUrl}${PREFIXO_API}${caminho}`
export const chaveTokens = CHAVE_TOKENS

/** URL do WebSocket: mesma origem da API, protocolo trocado. */
export function socketUrl(caminho: string, token: string | null): string {
  const base = config.baseUrl.replace(/^http/, 'ws')
  return `${base}${PREFIXO_API}${caminho}?token=${encodeURIComponent(token ?? '')}`
}
