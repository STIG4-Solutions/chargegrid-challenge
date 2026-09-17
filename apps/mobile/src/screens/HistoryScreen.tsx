import { useState } from 'react'
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { app, brl, duration, num, useApi, type Fatura, type Sessao } from '@chargegrid/sdk'
import { Aviso, Carregando, Etiqueta, Tela } from '../components'
import { dataCurta, dataHora, statusFatura } from '../format'
import { BotaoRecibo } from '../BotaoRecibo'
import { cores, espaco, raio } from '../theme'

const COR = {
  verde: cores.verde,
  ambar: cores.ambar,
  vermelho: cores.acento,
  fraco: cores.textoFraco
} as const

type Guia = 'recargas' | 'faturas'

export default function HistoryScreen() {
  const [guia, setGuia] = useState<Guia>('recargas')
  const sessoes = useApi<Sessao[]>(() => app.mySessions(50), [])
  const faturas = useApi<Fatura[]>(() => app.myInvoices(50), [])

  const atual = guia === 'recargas' ? sessoes : faturas
  if (atual.loading && !atual.data) return <Carregando rotulo="Carregando histórico..." />

  const emAberto = (faturas.data ?? []).filter((f) => f.status === 'open')
  const totalEnergia = (sessoes.data ?? []).reduce((t, x) => t + x.energy_kwh, 0)
  const totalVerde = (sessoes.data ?? []).reduce((t, x) => t + x.green_energy_kwh, 0)

  return (
    <Tela>
      <View style={s.cabecalho}>
        <Text style={s.titulo}>Histórico</Text>
        <View style={s.guias}>
          {(['recargas', 'faturas'] as Guia[]).map((g) => (
            <Pressable
              key={g}
              onPress={() => setGuia(g)}
              style={[s.guia, guia === g && s.guiaAtiva]}
              accessibilityRole="tab"
              accessibilityState={{ selected: guia === g }}
            >
              <Text style={[s.guiaTexto, guia === g && s.guiaTextoAtivo]}>
                {g === 'recargas' ? 'Recargas' : 'Faturas'}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {guia === 'recargas' ? (
        <FlatList
          data={sessoes.data ?? []}
          keyExtractor={(x) => x.id}
          contentContainerStyle={s.conteudo}
          refreshControl={
            <RefreshControl
              refreshing={sessoes.loading}
              onRefresh={() => void sessoes.refetch()}
              tintColor={cores.acento}
            />
          }
          ListHeaderComponent={
            <View style={s.resumo}>
              {sessoes.error && <Aviso mensagem={sessoes.error.detail} />}
              {(sessoes.data ?? []).length > 0 && (
                <View style={s.resumoLinha}>
                  <Resumo rotulo="Recargas" valor={String((sessoes.data ?? []).length)} />
                  <Resumo rotulo="Energia" valor={`${num(totalEnergia, 1)} kWh`} />
                  <Resumo
                    rotulo="De origem solar"
                    valor={totalEnergia ? `${Math.round((totalVerde / totalEnergia) * 100)}%` : '-'}
                  />
                </View>
              )}
            </View>
          }
          ListEmptyComponent={
            !sessoes.error ? <Aviso tom="info" mensagem="Nenhuma recarga concluída ainda." /> : null
          }
          renderItem={({ item }) => (
            <View style={s.card}>
              <View style={s.cardTopo}>
                <Text style={s.cardTitulo}>{dataHora(item.started_at ?? item.authorized_at)}</Text>
                <Text style={s.cardValor}>{brl(item.estimated_cost)}</Text>
              </View>
              <Text style={s.cardMeta}>
                {item.code} · {num(item.energy_kwh, 2)} kWh · {duration(item.duration_s)}
                {item.idle_minutes > 0 ? ` · ${item.idle_minutes} min ociosos` : ''}
              </Text>
              {item.green_energy_kwh > 0 && (
                <Text style={s.verde}>
                  {num(item.green_energy_kwh, 2)} kWh vieram do sol e da bateria do site
                </Text>
              )}
            </View>
          )}
        />
      ) : (
        <FlatList
          data={faturas.data ?? []}
          keyExtractor={(x) => x.id}
          contentContainerStyle={s.conteudo}
          refreshControl={
            <RefreshControl
              refreshing={faturas.loading}
              onRefresh={() => void faturas.refetch()}
              tintColor={cores.acento}
            />
          }
          ListHeaderComponent={
            <View style={s.resumo}>
              {faturas.error && <Aviso mensagem={faturas.error.detail} />}
              {emAberto.length > 0 && (
                <Aviso
                  tom="info"
                  mensagem={`${emAberto.length} fatura(s) em aberto, somando ${brl(
                    emAberto.reduce((t, f) => t + f.total, 0)
                  )}.`}
                />
              )}
            </View>
          }
          ListEmptyComponent={
            !faturas.error ? <Aviso tom="info" mensagem="Nenhuma fatura emitida." /> : null
          }
          renderItem={({ item }) => {
            const rotulo = statusFatura[item.status] ?? {
              label: item.status,
              cor: 'fraco' as const
            }
            return (
              <View style={s.card}>
                <View style={s.cardTopo}>
                  <View style={s.ident}>
                    <Text style={s.cardTitulo}>{brl(item.total)}</Text>
                    <Text style={s.cardMeta}>
                      {item.code} · {dataCurta(item.issued_on)}
                    </Text>
                  </View>
                  <Etiqueta texto={rotulo.label} cor={COR[rotulo.cor]} />
                </View>
                {item.lines.map((linha, i) => (
                  <View key={i} style={s.linha}>
                    <Text style={s.linhaRotulo}>{linha.description}</Text>
                    <Text style={s.linhaValor}>{brl(linha.amount)}</Text>
                  </View>
                ))}
                <BotaoRecibo invoiceId={item.id} codigo={item.code} />
              </View>
            )
          }}
        />
      )}
    </Tela>
  )
}

function Resumo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <View style={s.resumoItem}>
      <Text style={s.resumoValor}>{valor}</Text>
      <Text style={s.resumoRotulo}>{rotulo}</Text>
    </View>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  cabecalho: { paddingHorizontal: espaco.md, paddingBottom: espaco.sm, gap: espaco.sm },
  titulo: { color: cores.texto, fontSize: 20, fontWeight: '800' },
  guias: { flexDirection: 'row', gap: espaco.sm },
  guia: {
    paddingVertical: 6,
    paddingHorizontal: espaco.md,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: cores.borda
  },
  guiaAtiva: { borderColor: cores.acento, backgroundColor: '#FF323A22' },
  guiaTexto: { color: cores.textoFraco, fontSize: 13 },
  guiaTextoAtivo: { color: cores.texto, fontWeight: '600' },
  conteudo: { paddingHorizontal: espaco.md, paddingBottom: espaco.xl, gap: espaco.sm },
  resumo: { gap: espaco.sm },
  resumoLinha: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md
  },
  resumoItem: { gap: 2, alignItems: 'center', flex: 1 },
  resumoValor: { color: cores.texto, fontSize: 18, fontWeight: '700' },
  resumoRotulo: { color: cores.textoFraco, fontSize: 11, textAlign: 'center' },
  card: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: espaco.xs
  },
  cardTopo: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: espaco.sm
  },
  ident: { gap: 2, flexShrink: 1 },
  cardTitulo: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  cardValor: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  cardMeta: { color: cores.textoFraco, fontSize: 12 },
  verde: { color: cores.verde, fontSize: 11, marginTop: 2 },
  linha: { flexDirection: 'row', justifyContent: 'space-between', gap: espaco.md, marginTop: 2 },
  linhaRotulo: { color: cores.textoFraco, fontSize: 12, flexShrink: 1 },
  linhaValor: { color: cores.textoFraco, fontSize: 12 }
})
