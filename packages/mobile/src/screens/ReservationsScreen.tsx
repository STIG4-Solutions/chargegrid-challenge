import { useCallback } from 'react'
import { Alert, FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { app, num, useAction, useApi, type Agendamento } from '@chargegrid/sdk'
import { Aviso, Botao, Carregando, Etiqueta, Tela } from '../components'
import { quando, statusAgendamento } from '../format'
import { cores, espaco, raio } from '../theme'
import type { PropsAba } from '../navigation'

const COR = { verde: cores.verde, ambar: cores.ambar, fraco: cores.textoFraco } as const

export default function ReservationsScreen({ navigation }: PropsAba<'Agenda'>) {
  const agendamentos = useApi<Agendamento[]>(() => app.myReservations(), [])

  // Voltar de "novo agendamento" tem que mostrar o que acabou de ser criado.
  useFocusEffect(
    useCallback(() => {
      void agendamentos.refetch({ silent: true })
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
  )

  const cancelar = useAction((id: string) => app.cancelReservation(id), {
    onSuccess: () => void agendamentos.refetch({ silent: true })
  })

  function confirmarCancelamento(item: Agendamento) {
    Alert.alert(
      'Cancelar agendamento',
      `${item.code} em ${item.charge_point_code ?? 'ponto'} — ${quando(item.starts_at)}.`,
      [
        { text: 'Manter', style: 'cancel' },
        { text: 'Cancelar', style: 'destructive', onPress: () => void cancelar.run(item.id) }
      ]
    )
  }

  if (agendamentos.loading && !agendamentos.data) return <Carregando rotulo="Buscando agenda..." />

  const lista = agendamentos.data ?? []
  const ativos = lista.filter((a) => a.status === 'confirmed')

  return (
    <Tela>
      <View style={s.cabecalho}>
        <View>
          <Text style={s.titulo}>Minha agenda</Text>
          <Text style={s.subtitulo}>
            {ativos.length === 0
              ? 'Nenhuma reserva ativa'
              : `${ativos.length} reserva(s) confirmada(s)`}
          </Text>
        </View>
        <Botao titulo="Agendar" onPress={() => navigation.navigate('NovoAgendamento')} />
      </View>

      <FlatList
        data={lista}
        keyExtractor={(a) => a.id}
        contentContainerStyle={s.conteudo}
        refreshControl={
          <RefreshControl
            refreshing={agendamentos.loading}
            onRefresh={() => void agendamentos.refetch()}
            tintColor={cores.acento}
          />
        }
        ListHeaderComponent={
          <View style={s.avisos}>
            {agendamentos.error && <Aviso mensagem={agendamentos.error.detail} />}
            {cancelar.error && <Aviso mensagem={cancelar.error.detail} />}
          </View>
        }
        ListEmptyComponent={
          !agendamentos.error ? (
            <Aviso
              tom="info"
              mensagem="Você ainda não agendou nenhuma recarga. Agendar garante a vaga e reserva a potência no horário escolhido."
            />
          ) : null
        }
        renderItem={({ item }) => {
          const rotulo = statusAgendamento[item.status] ?? { label: item.status, cor: 'fraco' as const }
          const podeCancelar = item.status === 'confirmed'
          return (
            <View style={s.card}>
              <View style={s.cardTopo}>
                <View style={s.ident}>
                  <Text style={s.cardQuando}>{quando(item.starts_at)}</Text>
                  <Text style={s.cardOnde}>
                    {item.charge_point_code ?? '—'} · {item.site_name ?? 'estação'}
                  </Text>
                </View>
                <Etiqueta texto={rotulo.label} cor={COR[rotulo.cor]} />
              </View>
              <Text style={s.cardMeta}>
                {item.code} · reserva {num(item.reserved_kw, 1)} kW
                {item.target_kwh ? ` · alvo ${num(item.target_kwh, 0)} kWh` : ''}
              </Text>
              {podeCancelar && (
                <Botao
                  titulo="Cancelar"
                  variante="secundario"
                  pending={cancelar.pending}
                  onPress={() => confirmarCancelamento(item)}
                />
              )}
            </View>
          )
        }}
      />
    </Tela>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  cabecalho: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: espaco.md,
    paddingBottom: espaco.sm,
    gap: espaco.md
  },
  titulo: { color: cores.texto, fontSize: 20, fontWeight: '800' },
  subtitulo: { color: cores.textoFraco, fontSize: 12, marginTop: 2 },
  conteudo: { paddingHorizontal: espaco.md, paddingBottom: espaco.xl, gap: espaco.sm },
  avisos: { gap: espaco.sm },
  card: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: espaco.sm
  },
  cardTopo: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: espaco.sm },
  ident: { gap: 2, flexShrink: 1 },
  cardQuando: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  cardOnde: { color: cores.textoFraco, fontSize: 13 },
  cardMeta: { color: cores.textoFraco, fontSize: 12 }
})
