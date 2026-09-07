import Constants from 'expo-constants'
import * as Device from 'expo-device'
import * as Notifications from 'expo-notifications'
import { Platform } from 'react-native'
import { app } from '@chargegrid/sdk'

/**
 * Registro do aparelho para notificação push.
 *
 * O app fazia polling. Isso cobre o motorista que está com a tela aberta — e o
 * momento em que a notificação importa é justamente o outro: ele foi almoçar,
 * a recarga terminou, e o conector fica ocupado gerando taxa de ociosidade
 * para ele e fila para os demais.
 *
 * Tudo aqui falha em silêncio de propósito. Push é um extra: se a permissão
 * for negada, se o aparelho for um emulador, se o serviço estiver fora do ar,
 * o app continua funcionando exatamente como antes. Um erro de registro não
 * pode impedir alguém de carregar o carro.
 */

// Notificação com o app aberto também aparece. Sem isto ela é entregue e
// engolida: o motorista que está na tela do mapa não fica sabendo que a
// recarga dele terminou.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false
  })
})

let tokenAtual: string | null = null

/** O token registrado nesta sessão, ou null. */
export function tokenRegistrado(): string | null {
  return tokenAtual
}

/**
 * Pede permissão, obtém o token e registra no servidor.
 *
 * Chamado depois do login, não na abertura do app: pedir permissão de
 * notificação para quem ainda não entrou é pedir antes de haver o que
 * notificar, e a recusa é permanente — o sistema não pergunta de novo.
 */
export async function registrar(): Promise<string | null> {
  try {
    // Emulador não recebe push. Tentar assim mesmo gera um erro confuso no
    // console toda vez que o app abre em desenvolvimento.
    if (!Device.isDevice) return null

    // Sem google-services.json o Android não sabe a quem pedir o token, e a
    // chamada falha. O problema não é a falha — é que a permissão teria sido
    // pedida antes dela, e a recusa do sistema é permanente: gastaríamos a
    // única chance num build que nunca receberia nada.
    //
    // O sinal vem de `extra.pushConfigurado`, posto pelo app.config.js, e não
    // de tentar e ver no que dá.
    if (Constants.expoConfig?.extra?.pushConfigurado !== true) return null

    if (Platform.OS === 'android') {
      // Sem canal, o Android 8+ descarta a notificação sem avisar ninguém.
      await Notifications.setNotificationChannelAsync('recargas', {
        name: 'Recargas',
        importance: Notifications.AndroidImportance.DEFAULT,
        sound: 'default'
      })
    }

    const atual = await Notifications.getPermissionsAsync()
    let concedida = atual.granted
    if (!concedida && atual.canAskAgain) {
      concedida = (await Notifications.requestPermissionsAsync()).granted
    }
    if (!concedida) return null

    const { data } = await Notifications.getExpoPushTokenAsync()
    if (!data) return null

    await app.registerPushDevice(data, Platform.OS === 'ios' ? 'ios' : 'android')
    tokenAtual = data
    return data
  } catch {
    // Silêncio deliberado: ver a explicação no topo do arquivo.
    return null
  }
}

/**
 * Remove o aparelho ao sair da conta.
 *
 * Sem isto, o próximo motorista a entrar neste celular continuaria recebendo
 * as notificações do anterior até o primeiro evento reapontar o token — e
 * esse intervalo inclui o código da recarga e o valor de outra pessoa.
 */
export async function remover(): Promise<void> {
  const token = tokenAtual
  tokenAtual = null
  if (!token) return
  try {
    await app.unregisterPushDevice(token)
  } catch {
    // Sair da conta não pode falhar porque o servidor não respondeu.
  }
}
