import type { NativeStackScreenProps } from '@react-navigation/native-stack'

export type RotasApp = {
  Mapa: undefined
  Estacao: { siteId: string; nome: string }
  Sessao: undefined
}

export type Props<R extends keyof RotasApp> = NativeStackScreenProps<RotasApp, R>
