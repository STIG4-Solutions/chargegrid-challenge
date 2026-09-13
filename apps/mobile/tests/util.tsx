/**
 * Render com o contexto que o app real tem na raiz.
 *
 * `useSafeAreaInsets` estoura sem `SafeAreaProvider` - no aparelho ele vem de
 * `App.tsx`, e no teste tem de vir daqui. As metricas sao fixas de proposito:
 * numero de recorte de tela nao e' o que estes testes verificam, e deixa-lo
 * variar tornaria a suite dependente do aparelho imaginado.
 *
 * `render` da RNTL 14 e' ASSINCRONO - devolve Promise. Escrever `render(...)`
 * sem `await` nao quebra na hora: as consultas simplesmente nao acham nada, e o
 * teste falha dizendo que o texto nao existe. Por isso este utilitario existe
 * tambem como lembrete.
 */
import type { ReactElement } from 'react'
import { render } from '@testing-library/react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'

const METRICAS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 }
}

export function renderNaTela(elemento: ReactElement) {
  return render(<SafeAreaProvider initialMetrics={METRICAS}>{elemento}</SafeAreaProvider>)
}
