import { useCallback } from 'react'
import { FlatList, Platform, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import Constants from 'expo-constants'
import MapView, { Marker, PROVIDER_DEFAULT } from 'react-native-maps'
import { app, brl, useApi, type Estacao, type SessaoDetalhada } from '@chargegrid/sdk'
import { Aviso, Botao, Carregando, Etiqueta, Tela } from '../components'
import { useAuth } from '../auth'
import { cores, espaco, raio } from '../theme'
import type { PropsAba } from '../navigation'

/**
 * O mapa no Android depende do Google Maps, que exige chave propria.
 *
 * Sem ela o `MapView` nao apenas fica cinza: no APK proprio o
 * `com.google.android.gms.maps.MapView.onCreate` levanta excecao e derruba o
 * app na abertura. Dentro do Expo Go isso nao acontece porque ele traz a
 * configuracao dele — por isso o problema so' aparece no build standalone.
 *
 * Entao o mapa so' e' montado quando ha chave. Sem chave, a lista de estacoes
 * logo abaixo continua entregando o essencial.
 *
 * O sinal vem de `extra.mapaConfigurado`, um booleano posto pelo app.config.js -
 * e nao da propria chave, que e' podada do manifesto publico que o Constants le.
 */
const MAPA_DISPONIVEL =
  Platform.OS === 'ios' || Constants.expoConfig?.extra?.mapaConfigurado === true

// Centro do mapa quando ainda nao ha estacao carregada (Sao Paulo).
const REGIAO_PADRAO = {
  latitude: -23.5685,
  longitude: -46.6322,
  latitudeDelta: 0.06,
  longitudeDelta: 0.06
}

export default function MapScreen({ navigation }: PropsAba<'Mapa'>) {
  const { user } = useAuth()

  const estacoes = useApi<Estacao[]>(() => app.stations(), [], { pollMs: 30000 })
  // A sessao ativa manda o motorista direto para o acompanhamento.
  const ativa = useApi<SessaoDetalhada | null>(() => app.activeSession(), [], { pollMs: 15000 })

  const recarregar = useCallback(() => {
    void estacoes.refetch()
    void ativa.refetch()
  }, [estacoes, ativa])

  const comCoordenada = (estacoes.data ?? []).filter(
    (e): e is Estacao & { latitude: number; longitude: number } =>
      e.latitude != null && e.longitude != null
  )
  const primeira = comCoordenada[0]

  if (estacoes.loading && !estacoes.data) return <Carregando rotulo="Buscando estacoes..." />

  return (
    <Tela>
      <View style={s.cabecalho}>
        <View style={s.saudacao}>
          <Text style={s.ola}>Ola, {user?.full_name?.split(' ')[0] ?? 'motorista'}</Text>
          <Text style={s.carteira}>Carteira {brl(user?.wallet_balance ?? 0)}</Text>
        </View>
        <Botao titulo="Ler QR" onPress={() => navigation.navigate('Escanear')} />
      </View>

      {ativa.data && (
        <Pressable style={s.faixaAtiva} onPress={() => navigation.navigate('Sessao')}>
          <View style={s.pulso} />
          <Text style={s.faixaTexto}>Recarga em andamento — toque para acompanhar</Text>
        </Pressable>
      )}

      {MAPA_DISPONIVEL ? (
        <MapView
          style={s.mapa}
          provider={PROVIDER_DEFAULT}
          initialRegion={
            primeira
              ? { ...REGIAO_PADRAO, latitude: primeira.latitude, longitude: primeira.longitude }
              : REGIAO_PADRAO
          }
        >
          {comCoordenada.map((e) => (
            <Marker
              key={e.site_id}
              coordinate={{ latitude: e.latitude, longitude: e.longitude }}
              title={e.name}
              description={`${e.available_points} de ${e.total_points} livres`}
              pinColor={e.available_points > 0 ? cores.verde : cores.acento}
              onCalloutPress={() =>
                navigation.navigate('Estacao', { siteId: e.site_id, nome: e.name })
              }
            />
          ))}
        </MapView>
      ) : (
        <View style={[s.mapa, s.mapaAusente]}>
          <Text style={s.mapaAusenteTitulo}>Mapa indisponível</Text>
          <Text style={s.mapaAusenteTexto}>
            Falta a chave do Google Maps em app.json ({'android.config.googleMaps.apiKey'}). As
            estações estão listadas abaixo.
          </Text>
        </View>
      )}

      <FlatList
        style={s.lista}
        data={estacoes.data ?? []}
        keyExtractor={(e) => e.site_id}
        contentContainerStyle={s.listaConteudo}
        refreshControl={
          <RefreshControl
            refreshing={estacoes.loading}
            onRefresh={recarregar}
            tintColor={cores.acento}
          />
        }
        ListHeaderComponent={estacoes.error ? <Aviso mensagem={estacoes.error.detail} /> : null}
        ListEmptyComponent={
          !estacoes.error ? (
            <Aviso tom="info" mensagem="Nenhuma estacao por perto no momento." />
          ) : null
        }
        renderItem={({ item }) => {
          const livre = item.available_points > 0
          return (
            <Pressable
              style={s.card}
              onPress={() =>
                navigation.navigate('Estacao', { siteId: item.site_id, nome: item.name })
              }
            >
              <View style={s.cardTopo}>
                <Text style={s.cardNome}>{item.name}</Text>
                <Etiqueta
                  texto={livre ? `${item.available_points} livre(s)` : 'Ocupada'}
                  cor={livre ? cores.verde : cores.ambar}
                />
              </View>
              {item.address && <Text style={s.cardEndereco}>{item.address}</Text>}
              <Text style={s.cardMeta}>
                {item.connectors.join(' · ')} · ate {item.max_kw} kW
                {item.price_per_kwh != null ? ` · ${brl(item.price_per_kwh)}/kWh` : ''}
                {item.distance_km != null ? ` · ${item.distance_km.toFixed(1)} km` : ''}
              </Text>
            </Pressable>
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
  saudacao: { gap: 2 },
  ola: { color: cores.texto, fontSize: 18, fontWeight: '700' },
  carteira: { color: cores.textoFraco, fontSize: 12 },
  faixaAtiva: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.sm,
    marginHorizontal: espaco.md,
    marginBottom: espaco.sm,
    padding: espaco.md,
    borderRadius: raio.md,
    backgroundColor: '#2ECC7122',
    borderWidth: 1,
    borderColor: '#2ECC7155'
  },
  pulso: { width: 8, height: 8, borderRadius: 4, backgroundColor: cores.verde },
  faixaTexto: { color: cores.verde, fontSize: 13, fontWeight: '600' },
  mapa: { height: 220, marginHorizontal: espaco.md, borderRadius: raio.lg },
  mapaAusente: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: espaco.lg,
    gap: espaco.xs
  },
  mapaAusenteTitulo: { color: cores.textoFraco, fontSize: 15, fontWeight: '700' },
  mapaAusenteTexto: { color: cores.textoFraco, fontSize: 12, textAlign: 'center', lineHeight: 17 },
  lista: { flex: 1, marginTop: espaco.md },
  listaConteudo: { paddingHorizontal: espaco.md, paddingBottom: espaco.xl, gap: espaco.sm },
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
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: espaco.sm
  },
  cardNome: { color: cores.texto, fontSize: 16, fontWeight: '700', flexShrink: 1 },
  cardEndereco: { color: cores.textoFraco, fontSize: 12 },
  cardMeta: { color: cores.textoFraco, fontSize: 12, marginTop: 2 }
})
