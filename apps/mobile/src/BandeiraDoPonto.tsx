import { StyleSheet, Text, View } from 'react-native'
import { brl, num, type Bandeira } from '@chargegrid/sdk'
import { Etiqueta } from './components'
import { cores, espaco } from './theme'

const COR: Record<string, string> = {
  verde: cores.verde,
  amarela: cores.ambar,
  vermelha: cores.acento
}

/**
 * Bandeira do site e preco por kWh de uma recarga iniciada agora.
 *
 * O preco vem pronto do servidor (janela vigente x bandeira), e e' o mesmo que
 * a sessao travaria: a tela nao refaz a conta. Bandeira velha aparece como
 * indisponivel, e o preco dela ja' chega sem multiplicador.
 */
export default function BandeiraDoPonto({
  bandeira,
  preco
}: {
  bandeira: Bandeira | null | undefined
  preco: number | null | undefined
}) {
  if (!bandeira && preco == null) return null
  const velha = bandeira?.desatualizada

  return (
    <View style={s.caixa}>
      {bandeira &&
        (velha ? (
          <Etiqueta texto="Bandeira indisponível" cor={cores.textoFraco} />
        ) : (
          <Etiqueta
            texto={`Bandeira ${bandeira.cor} · x${num(bandeira.multiplicador, 2)}`}
            cor={COR[bandeira.cor] ?? cores.textoFraco}
          />
        ))}
      {preco != null && <Text style={s.preco}>{brl(preco)}/kWh se iniciar agora</Text>}
      {bandeira && !velha && <Text style={s.motivo}>{bandeira.motivo}</Text>}
    </View>
  )
}

const s = StyleSheet.create({
  caixa: { gap: espaco.xs, marginBottom: espaco.sm, alignItems: 'flex-start' },
  preco: { color: cores.texto, fontSize: 15, fontWeight: '600' },
  motivo: { color: cores.textoFraco, fontSize: 13 }
})
