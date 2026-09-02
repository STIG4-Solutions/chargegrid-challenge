/**
 * Ligacao do SDK ao ambiente React Native.
 *
 * E o unico arquivo do app que sabe que estamos no mobile: o resto do codigo
 * chama `app.stations()`, `auth.login()` etc. exatamente como o painel faz.
 */
import AsyncStorage from '@react-native-async-storage/async-storage'
import Constants from 'expo-constants'
import { configureSdk } from '@chargegrid/sdk'

/**
 * Em desenvolvimento, `localhost` aponta para o proprio aparelho — nunca para
 * a maquina que roda a API. O Expo ja sabe o IP do computador que serve o
 * bundle (`hostUri`), entao reaproveitamos ele e so trocamos a porta.
 *
 * `hostUri` so existe quando ha um servidor de desenvolvimento servindo o
 * bundle. Num APK instalado ele e' nulo, e e' assim que distinguimos os dois
 * mundos sem precisar de flag.
 */
function baseUrlDeDesenvolvimento(): string | null {
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost
  const host = hostUri?.split(':')[0]
  return host ? `http://${host}:8000` : null
}

/**
 * Endereco da API, em ordem de precedencia:
 *
 *   1. EXPO_PUBLIC_API_URL   — sobrepoe tudo; e' o que o emulador usa
 *   2. hostUri               — maquina que serve o bundle, em desenvolvimento
 *   3. extra.apiPadrao       — dominio de producao, de config/dominios.json
 *
 * O terceiro fica congelado no pacote: um app instalado nao le configuracao do
 * servidor. Trocar de dominio exige um build novo - nao ha como contornar isso
 * num APK, so' num app que busque a configuracao ao abrir.
 */
const apiPadrao = (Constants.expoConfig?.extra?.apiPadrao as string | undefined) ?? ''

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL || baseUrlDeDesenvolvimento() || apiPadrao

/** Base das URLs impressas nos adesivos de QR. */
export const SITE_URL = (Constants.expoConfig?.extra?.siteUrl as string | undefined) ?? ''

/**
 * `AsyncStorage` satisfaz `TokenStorage` sem adaptador: a interface do SDK tem
 * a mesma forma do `localStorage` e aceita retorno sincrono ou Promise.
 */
export function iniciarSdk(aoExpirarSessao: () => void): void {
  configureSdk({
    baseUrl: API_URL,
    storage: AsyncStorage,
    onSessionExpired: aoExpirarSessao
  })
}
