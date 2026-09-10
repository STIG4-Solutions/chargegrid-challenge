import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs'
import type { CompositeScreenProps } from '@react-navigation/native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'

/** Abas de primeiro nivel: o que o motorista alcanca a um toque. */
export type Abas = {
  Mapa: undefined
  Agenda: undefined
  Historico: undefined
  Missoes: undefined
  Frota: undefined
  Perfil: undefined
}

/** Telas empilhadas sobre as abas, sempre alcancadas a partir de uma delas. */
export type RotasApp = {
  Abas: undefined
  Estacao: { siteId: string; nome: string; destaque?: string }
  Sessao: undefined
  NovoAgendamento: undefined
  Escanear: undefined
}

export type Props<R extends keyof RotasApp> = NativeStackScreenProps<RotasApp, R>

/** Uma tela de aba tambem precisa navegar para a pilha (ex.: Mapa -> Estacao). */
export type PropsAba<R extends keyof Abas> = CompositeScreenProps<
  BottomTabScreenProps<Abas, R>,
  NativeStackScreenProps<RotasApp>
>
