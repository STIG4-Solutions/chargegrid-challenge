/**
 * SDK ChargeGrid — cliente compartilhado pelo painel comercial (React) e pelo
 * app do motorista (React Native).
 *
 * Ligue ao ambiente uma vez, no bootstrap:
 *
 *     configureSdk({ baseUrl: 'http://localhost:8000', storage: localStorage })
 *     await hydrateTokens()
 */
export { configureSdk, getConfig, socketUrl } from './config'
export { memoryStorage, type TokenStorage } from './storage'
export { ApiError } from './errors'
export {
  accessToken,
  currentTokens,
  hydrateTokens,
  saveTokens,
  tokensHidratados,
  type TokenPair
} from './tokens'
export { api, request, type Metodo, type RequestOptions } from './http'
export { app, auth, campaigns, payments, platform, power, sessions, tariffs } from './endpoints'
export * from './format'
export { useAction, useApi, type UseActionResult, type UseApiOptions, type UseApiResult } from './hooks'
export { useSiteStream, type StatusDoStream, type TelemetriaDoSite } from './stream'
export type * from './types'
