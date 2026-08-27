import { ScrollView, StyleSheet, Text, View } from 'react-native'
import {
  app,
  brl,
  duration,
  meta,
  num,
  sessionState,
  useAction,
  useApi,
  type Precificacao,
  type SessaoDetalhada
} from '@chargegrid/sdk'
import { Aviso, Botao, Campo, Carregando, Etiqueta } from '../components'
import { cores, espaco, raio } from '../theme'
import type { Props } from '../navigation'

export default function SessionScreen({ navigation }: Props<'Sessao'>) {
  // 5s: e uma tela que o motorista deixa aberta olhando a recarga subir.
  const sessao = useApi<SessaoDetalhada | null>(() => app.activeSession(), [], { pollMs: 5000 })
  const id = sessao.data?.id

  const previa = useApi<Precificacao>(
    () => app.sessionPreview(id as string),
    [id],
    { pollMs: 15000, enabled: Boolean(id) }
  )

  const encerrar = useAction(() => app.stopSession(id as string), {
    onSuccess: () => navigation.navigate('Mapa')
  })

  if (sessao.loading && !sessao.data) return <Carregando rotulo="Buscando sua recarga..." />

  if (sessao.error) {
    return (
      <View style={s.vazio}>
        <Aviso mensagem={sessao.error.detail} />
        <Botao titulo="Tentar de novo" onPress={() => void sessao.refetch()} />
      </View>
    )
  }

  if (!sessao.data) {
    return (
      <View style={s.vazio}>
        <Aviso tom="info" mensagem="Nenhuma recarga em andamento." />
        <Botao titulo="Ver estacoes" onPress={() => navigation.navigate('Mapa')} />
      </View>
    )
  }

  const ses = sessao.data
  const rotulo = meta(sessionState, ses.state)
  const naFila = ses.state === 'queued'

  return (
    <ScrollView style={s.tela} contentContainerStyle={s.conteudo}>
      <View style={s.cabecalho}>
        <Text style={s.codigo}>{ses.code}</Text>
        <Etiqueta texto={rotulo.label} cor={naFila ? cores.ambar : cores.verde} />
      </View>

      {naFila && (
        <Aviso
          tom="info"
          mensagem={
            ses.queue_position != null
              ? `Voce e o ${ses.queue_position}o da fila. A recarga comeca sozinha assim que houver potencia livre no local.`
              : 'Aguardando potencia livre no local. A recarga comeca sozinha.'
          }
        />
      )}

      <View style={s.destaque}>
        <Text style={s.destaqueValor}>{num(ses.energy_kwh, 2)}</Text>
        <Text style={s.destaqueUnidade}>kWh entregues</Text>
      </View>

      <View style={s.grade}>
        <Campo rotulo="Potencia de pico" valor={`${num(ses.peak_power_kw, 1)} kW`} />
        <Campo rotulo="Duracao" valor={duration(ses.duration_s)} />
        <Campo rotulo="Energia solar" valor={`${num(ses.green_energy_kwh, 2)} kWh`} />
        <Campo rotulo="Ociosidade" valor={`${ses.idle_minutes} min`} />
      </View>

      <View style={s.bloco}>
        <Text style={s.blocoTitulo}>Custo</Text>
        {previa.data ? (
          <>
            {previa.data.lines.map((linha, i) => (
              <View key={i} style={s.linha}>
                <Text style={s.linhaRotulo}>{linha.description}</Text>
                <Text style={s.linhaValor}>{brl(linha.amount)}</Text>
              </View>
            ))}
            <View style={[s.linha, s.total]}>
              <Text style={s.totalRotulo}>Total</Text>
              <Text style={s.totalValor}>{brl(previa.data.total)}</Text>
            </View>
          </>
        ) : (
          <Text style={s.linhaRotulo}>
            {previa.error ? previa.error.detail : `Estimado: ${brl(ses.estimated_cost)}`}
          </Text>
        )}
        <Text style={s.nota}>
          Calculado pelo mesmo motor que emite a fatura, na janela tarifaria vigente.
        </Text>
      </View>

      {encerrar.error && <Aviso mensagem={encerrar.error.detail} />}

      <Botao
        titulo={naFila ? 'Sair da fila' : 'Encerrar recarga'}
        onPress={() => void encerrar.run()}
        pending={encerrar.pending}
      />
    </ScrollView>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: espaco.md, gap: espaco.md, paddingBottom: espaco.xl },
  vazio: {
    flex: 1,
    backgroundColor: cores.fundo,
    justifyContent: 'center',
    padding: espaco.lg,
    gap: espaco.md
  },
  cabecalho: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  codigo: { color: cores.texto, fontSize: 20, fontWeight: '800' },
  destaque: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.lg,
    paddingVertical: espaco.lg,
    alignItems: 'center',
    gap: espaco.xs
  },
  destaqueValor: { color: cores.texto, fontSize: 48, fontWeight: '800', letterSpacing: -1 },
  destaqueUnidade: { color: cores.textoFraco, fontSize: 13 },
  grade: { flexDirection: 'row', flexWrap: 'wrap', rowGap: espaco.md, columnGap: espaco.md },
  bloco: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: espaco.sm
  },
  blocoTitulo: { color: cores.texto, fontSize: 15, fontWeight: '700' },
  linha: { flexDirection: 'row', justifyContent: 'space-between', gap: espaco.md },
  linhaRotulo: { color: cores.textoFraco, fontSize: 13, flexShrink: 1 },
  linhaValor: { color: cores.texto, fontSize: 13, fontVariant: ['tabular-nums'] },
  total: { borderTopWidth: 1, borderTopColor: cores.borda, paddingTop: espaco.sm },
  totalRotulo: { color: cores.texto, fontSize: 15, fontWeight: '700' },
  totalValor: { color: cores.texto, fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  nota: { color: cores.textoFraco, fontSize: 11, lineHeight: 15 }
})
