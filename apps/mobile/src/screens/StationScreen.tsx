import { useLayoutEffect } from 'react'
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native'
import {
  app,
  meta,
  chargePointStatus,
  useAction,
  useApi,
  type PontoDaEstacao,
  type SessaoDetalhada
} from '@chargegrid/sdk'
import { Aviso, Botao, Carregando, Etiqueta , useRecuoInferior } from '../components'
import { cores, espaco, raio } from '../theme'
import type { Props } from '../navigation'

/** O ponto lido no QR vai para o topo: o motorista escaneou aquele, nao a lista. */
function ordenar(pontos: PontoDaEstacao[], destaque?: string): PontoDaEstacao[] {
  if (!destaque) return pontos
  return [...pontos].sort((a, b) =>
    a.code === destaque ? -1 : b.code === destaque ? 1 : 0
  )
}

export default function StationScreen({ route, navigation }: Props<'Estacao'>) {
  const recuo = useRecuoInferior()
  const { siteId, nome, destaque } = route.params

  useLayoutEffect(() => {
    navigation.setOptions({ title: nome })
  }, [navigation, nome])

  const pontos = useApi<PontoDaEstacao[]>(
    () => app.stationChargePoints(siteId),
    [siteId],
    { pollMs: 10000 }
  )
  const ativa = useApi<SessaoDetalhada | null>(() => app.activeSession(), [])

  // Iniciar leva direto ao acompanhamento: a partir daqui quem manda e o
  // servidor — se nao houver potencia livre, a sessao entra na fila e a tela
  // de sessao mostra isso.
  const iniciar = useAction(
    (chargePointId: string) => app.startSession({ charge_point_id: chargePointId }),
    { onSuccess: () => navigation.navigate('Sessao') }
  )

  if (pontos.loading && !pontos.data) return <Carregando rotulo="Carregando vagas..." />

  const jaTemSessao = ativa.data != null

  return (
    <View style={s.tela}>
      <FlatList
        data={ordenar(pontos.data ?? [], destaque)}
        keyExtractor={(p) => p.id}
        contentContainerStyle={[s.conteudo, { paddingBottom: recuo + espaco.xl }]}
        refreshControl={
          <RefreshControl
            refreshing={pontos.loading}
            onRefresh={() => void pontos.refetch()}
            tintColor={cores.acento}
          />
        }
        ListHeaderComponent={
          <View style={s.topo}>
            {pontos.error && <Aviso mensagem={pontos.error.detail} />}
            {iniciar.error && <Aviso mensagem={iniciar.error.detail} />}
            {jaTemSessao && (
              <Aviso
                tom="info"
                mensagem="Voce ja tem uma recarga em andamento. Encerre antes de iniciar outra."
              />
            )}
          </View>
        }
        ListEmptyComponent={
          !pontos.error ? (
            <Aviso tom="info" mensagem="Esta estacao nao tem vagas habilitadas." />
          ) : null
        }
        renderItem={({ item }) => {
          const rotulo = meta(chargePointStatus, item.status)
          const lido = destaque != null && item.code === destaque
          return (
            <View style={[s.card, lido && s.cardLido]}>
              {lido && <Text style={s.marcaLido}>Ponto que você escaneou</Text>}
              <View style={s.cardTopo}>
                <View style={s.cardIdent}>
                  <Text style={s.cardNome}>{item.name}</Text>
                  <Text style={s.cardMeta}>
                    {item.code} · {item.connector} · {item.rated_kw} kW
                  </Text>
                </View>
                <Etiqueta texto={rotulo.label} cor={corDoStatus(item.status)} />
              </View>
              <Botao
                titulo={item.available ? 'Iniciar recarga' : 'Indisponivel'}
                variante={item.available ? 'primario' : 'secundario'}
                disabled={!item.available || jaTemSessao}
                pending={iniciar.pending}
                onPress={() => void iniciar.run(item.id)}
              />
            </View>
          )
        }}
      />
    </View>
  )
}

function corDoStatus(status: string): string {
  if (status === 'available') return cores.verde
  if (status === 'charging' || status === 'preparing') return cores.azul
  if (status === 'offline' || status === 'faulted') return cores.acento
  return cores.ambar
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: espaco.md, gap: espaco.sm, paddingBottom: espaco.xl },
  topo: { gap: espaco.sm, marginBottom: espaco.sm },
  cardLido: { borderColor: cores.acento },
  marcaLido: {
    color: cores.acento,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase'
  },
  card: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: espaco.md
  },
  cardTopo: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: espaco.sm },
  cardIdent: { gap: 2, flexShrink: 1 },
  cardNome: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  cardMeta: { color: cores.textoFraco, fontSize: 12 }
})
