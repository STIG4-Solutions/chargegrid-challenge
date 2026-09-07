import { StyleSheet, Text, View } from 'react-native'
import { app, useApi } from '@chargegrid/sdk'
import { cores, espaco, raio } from './theme'

/**
 * "Comece às 22h e pague 30% menos."
 *
 * Conselho que só quem tem o motor de tarifação consegue dar: a conta caminha
 * a sessão pelas janelas horárias com a mesma regra que vai faturar depois,
 * então o número mostrado antes bate com o cobrado no fim.
 *
 * A tela carrega duas honestidades junto com a economia. Esperar atrasa — por
 * isso o horário de término aparece nas duas opções. E economia irrelevante
 * não vira conselho: o servidor só marca `vale_esperar` acima de R$ 1 e de 5%,
 * porque ninguém adia a recarga por troco.
 */
interface Opcao {
  hora: string
  hora_fim: string
  custo_brl: number
  janela: string
}

interface Conselho {
  disponivel: boolean
  motivo?: string
  agora?: Opcao
  melhor?: Opcao
  economia_brl?: number
  economia_pct?: number
  vale_esperar?: boolean
  esperar_minutos?: number
  ponto_ocupado?: boolean
  kwh?: number
}

function brl(v: number): string {
  return `R$ ${v.toFixed(2).replace('.', ',')}`
}

function espera(minutos: number): string {
  if (minutos < 60) return `${minutos} min`
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

export function QuandoComecar({ chargePointId, kwh = 30 }: { chargePointId: string; kwh?: number }) {
  const conselho = useApi<Conselho>(
    () => app.whenToStart(chargePointId, kwh) as unknown as Promise<Conselho>,
    [chargePointId, kwh]
  )

  const d = conselho.data
  // Sem tarifa por janela não há conselho a dar, e um bloco vazio na tela
  // pesaria mais que a ausência dele. Erro também some: isto é um extra, não
  // pode atrapalhar quem só quer apertar "Iniciar".
  if (!d || !d.disponivel || conselho.error) return null

  const agora = d.agora
  const melhor = d.melhor
  if (!agora || !melhor) return null

  if (!d.vale_esperar) {
    return (
      <View style={[s.bloco, s.blocoNeutro]}>
        <Text style={s.tituloNeutro}>Bom momento para carregar</Text>
        <Text style={s.corpo}>
          {agora.janela} · cerca de {brl(agora.custo_brl)} por {d.kwh} kWh, terminando às{' '}
          {agora.hora_fim}.
        </Text>
      </View>
    )
  }

  return (
    <View style={[s.bloco, s.blocoDica]}>
      <Text style={s.titulo}>
        Comece às {melhor.hora} e pague {Math.round(d.economia_pct ?? 0)}% menos
      </Text>
      <Text style={s.corpo}>
        Esperar {espera(d.esperar_minutos ?? 0)} economiza cerca de{' '}
        <Text style={s.destaque}>{brl(d.economia_brl ?? 0)}</Text> em {d.kwh} kWh.
      </Text>

      <View style={s.comparativo}>
        <View style={s.coluna}>
          <Text style={s.colunaRotulo}>Agora</Text>
          <Text style={s.colunaValor}>{brl(agora.custo_brl)}</Text>
          <Text style={s.colunaNota}>termina {agora.hora_fim}</Text>
        </View>
        <View style={s.coluna}>
          <Text style={s.colunaRotulo}>Às {melhor.hora}</Text>
          <Text style={[s.colunaValor, s.colunaValorBom]}>{brl(melhor.custo_brl)}</Text>
          <Text style={s.colunaNota}>termina {melhor.hora_fim}</Text>
        </View>
      </View>

      {d.ponto_ocupado && (
        <Text style={s.ressalva}>
          Este ponto está ocupado agora — se você esperar, ele pode estar livre.
        </Text>
      )}
    </View>
  )
}

const s = StyleSheet.create({
  bloco: {
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: 6
  },
  blocoDica: { borderColor: cores.ambar, backgroundColor: cores.superficieAlta },
  blocoNeutro: { borderColor: cores.borda, backgroundColor: cores.superficieAlta },
  titulo: { color: cores.ambar, fontSize: 15, fontWeight: '700' },
  tituloNeutro: { color: cores.verde, fontSize: 14, fontWeight: '700' },
  corpo: { color: cores.texto, fontSize: 13, lineHeight: 19 },
  destaque: { fontWeight: '700' },
  comparativo: { flexDirection: 'row', gap: espaco.md, marginTop: 4 },
  coluna: { flex: 1, gap: 2 },
  colunaRotulo: {
    color: cores.textoFraco,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase'
  },
  colunaValor: { color: cores.texto, fontSize: 18, fontWeight: '700' },
  colunaValorBom: { color: cores.verde },
  colunaNota: { color: cores.textoFraco, fontSize: 12 },
  ressalva: { color: cores.textoFraco, fontSize: 12, marginTop: 2 }
})
