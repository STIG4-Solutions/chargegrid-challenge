/** Pecas de UI reaproveitadas pelas telas. */
import type { ReactNode } from 'react'
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { cores, espaco, raio } from './theme'

/**
 * Raiz das telas de aba.
 *
 * O Android 16 tornou o desenho ponta a ponta obrigatorio: o app pinta por baixo
 * da barra de status e da barra de navegacao. As telas de aba nao tem cabecalho
 * do navegador para segurar o topo, entao sem este recuo o conteudo encosta nos
 * icones do sistema - e o primeiro toque cai na barra, nao no botao.
 *
 * As telas empilhadas (Estacao, Sessao, Escanear) nao usam este componente: o
 * cabecalho do navegador ja reserva o espaco delas.
 */
export function Tela({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const bordas = useSafeAreaInsets()
  return (
    <View style={[s.telaBase, { paddingTop: bordas.top }, style]}>{children}</View>
  )
}

/** Recuo inferior para listas e rolagens, para o ultimo item nao ficar colado. */
export function useRecuoInferior(extra = 0) {
  const bordas = useSafeAreaInsets()
  return bordas.bottom + extra
}

export function Botao({
  titulo,
  onPress,
  pending = false,
  disabled = false,
  variante = 'primario',
  style
}: {
  titulo: string
  onPress: () => void
  pending?: boolean
  disabled?: boolean
  variante?: 'primario' | 'secundario'
  style?: StyleProp<ViewStyle>
}) {
  const inativo = disabled || pending
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inativo, busy: pending }}
      onPress={onPress}
      disabled={inativo}
      style={({ pressed }) => [
        s.botao,
        variante === 'secundario' && s.botaoSecundario,
        inativo && s.botaoInativo,
        pressed && !inativo && s.botaoPressionado,
        style
      ]}
    >
      {pending ? (
        <ActivityIndicator color={cores.texto} size="small" />
      ) : (
        <Text style={[s.botaoTexto, variante === 'secundario' && s.botaoTextoSecundario]}>
          {titulo}
        </Text>
      )}
    </Pressable>
  )
}

/** Erro da API na tela. O `detail` do backend ja vem escrito para gente ler. */
export function Aviso({ mensagem, tom = 'erro' }: { mensagem: string; tom?: 'erro' | 'info' }) {
  return (
    <View style={[s.aviso, tom === 'info' && s.avisoInfo]}>
      <Text style={[s.avisoTexto, tom === 'info' && s.avisoTextoInfo]}>{mensagem}</Text>
    </View>
  )
}

export function Carregando({ rotulo = 'Carregando...' }: { rotulo?: string }) {
  return (
    <View style={s.centro}>
      <ActivityIndicator color={cores.acento} size="large" />
      <Text style={s.carregandoTexto}>{rotulo}</Text>
    </View>
  )
}

export function Etiqueta({ texto, cor }: { texto: string; cor: string }) {
  return (
    <View style={[s.etiqueta, { backgroundColor: cor + '22', borderColor: cor + '55' }]}>
      <Text style={[s.etiquetaTexto, { color: cor }]}>{texto}</Text>
    </View>
  )
}

export function Campo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <View style={s.campo}>
      <Text style={s.campoRotulo}>{rotulo}</Text>
      <Text style={s.campoValor}>{valor}</Text>
    </View>
  )
}

const s = StyleSheet.create({
  telaBase: { flex: 1, backgroundColor: cores.fundo },
  botao: {
    backgroundColor: cores.acento,
    borderRadius: raio.md,
    paddingVertical: 14,
    paddingHorizontal: espaco.lg,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48
  },
  botaoSecundario: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: cores.borda
  },
  botaoInativo: { opacity: 0.45 },
  botaoPressionado: { opacity: 0.8 },
  botaoTexto: { color: cores.texto, fontSize: 15, fontWeight: '600' },
  botaoTextoSecundario: { color: cores.textoFraco },
  aviso: {
    backgroundColor: '#FF323A22',
    borderColor: '#FF323A55',
    borderWidth: 1,
    borderRadius: raio.sm,
    padding: espaco.md
  },
  avisoInfo: { backgroundColor: '#3B82F622', borderColor: '#3B82F655' },
  avisoTexto: { color: '#FF8A8F', fontSize: 13, lineHeight: 18 },
  avisoTextoInfo: { color: '#93C5FD' },
  centro: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: espaco.md },
  carregandoTexto: { color: cores.textoFraco, fontSize: 13 },
  etiqueta: {
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 3,
    alignSelf: 'flex-start'
  },
  etiquetaTexto: { fontSize: 11, fontWeight: '700' },
  campo: { gap: 2 },
  campoRotulo: { color: cores.textoFraco, fontSize: 11 },
  campoValor: { color: cores.texto, fontSize: 16, fontWeight: '600' }
})
