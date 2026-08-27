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
 */
function baseUrlDeDesenvolvimento(): string {
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost
  const host = hostUri?.split(':')[0]
  return host ? `http://${host}:8000` : 'http://localhost:8000'
}

export const API_URL = process.env.EXPO_PUBLIC_API_URL || baseUrlDeDesenvolvimento()

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
