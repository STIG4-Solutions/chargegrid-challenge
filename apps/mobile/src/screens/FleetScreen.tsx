import { useState } from 'react'
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { app, brl, num, useApi } from '@chargegrid/sdk'
import { Aviso, Carregando, Tela, useRecuoInferior } from '../components'
import CentroDeCusto from '../CentroDeCusto'
import { cores, espaco, raio } from '../theme'

/**
 * Relatório mensal da frota, por centro de custo.
 *
 * É o que transforma o app de conveniência em ferramenta contratada: quem
 * dirige não é quem paga, e quem paga precisa saber quanto cada área gastou
 * sem somar recibo a mão no fim do mês.
 *
 * A tela é só do gestor. Um motorista comum recebe 403 da API — ele veria o
 * gasto de todos os colegas.
 */
interface Centro {
  centro_de_custo: string
  sessoes: number
  energia_kwh: number
  total_brl: number
  veiculos: number
  motoristas: number
  custo_medio_por_sessao_brl: number
  custo_por_kwh_brl: number
}

interface Relatorio {
  mes: string
  disponivel: boolean
  motivo?: string
  centros: Centro[]
  total_brl?: number
  energia_kwh?: number
  sessoes?: number
  em_aberto_brl?: number
  veiculos?: number
  motoristas?: number
  sem_centro_brl?: number
}

const MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]

/** Últimos seis meses, do mais recente para o mais antigo. */
function ultimosMeses(quantos = 6): { valor: string; rotulo: string }[] {
  const hoje = new Date()
  return Array.from({ length: quantos }, (_, i) => {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1)
    const mes = String(d.getMonth() + 1).padStart(2, '0')
    return {
      valor: `${d.getFullYear()}-${mes}`,
      rotulo: `${MESES[d.getMonth()]} ${d.getFullYear()}`
    }
  })
}

export default function FleetScreen() {
  const recuo = useRecuoInferior()
  const meses = ultimosMeses()
  const [mes, setMes] = useState(meses[0].valor)
  const relatorio = useApi<Relatorio>(
    () => app.fleetReport(mes) as unknown as Promise<Relatorio>,
    [mes]
  )

  const d = relatorio.data
  const rotuloDoMes = meses.find((m) => m.valor === mes)?.rotulo ?? mes

  if (relatorio.loading && !d) return <Carregando rotulo="Carregando relatório..." />

  return (
    <Tela>
      <FlatList
        data={d?.centros ?? []}
        keyExtractor={(c) => c.centro_de_custo}
        contentContainerStyle={[s.conteudo, { paddingBottom: recuo + espaco.xl }]}
        refreshControl={
          <RefreshControl
            refreshing={relatorio.loading}
            onRefresh={() => void relatorio.refetch()}
            tintColor={cores.acento}
          />
        }
        ListHeaderComponent={
          <View style={s.topo}>
            <Text style={s.titulo}>Frota</Text>
            <Text style={s.subtitulo}>Gasto por centro de custo, fechado pela fatura.</Text>

            <View style={s.meses}>
              {meses.map((m) => (
                <Text
                  key={m.valor}
                  onPress={() => setMes(m.valor)}
                  style={[s.chip, m.valor === mes && s.chipAtivo]}
                >
                  {m.rotulo.split(' ')[0].slice(0, 3)}
                </Text>
              ))}
            </View>

            {relatorio.error && <Aviso mensagem={relatorio.error.detail} />}

            {d && !d.disponivel && (
              <Aviso tom="info" mensagem={`Relatório indisponível: ${d.motivo ?? '—'}`} />
            )}

            {d?.disponivel && (
              <>
                <View style={s.resumo}>
                  <Bloco rotulo="Total" valor={brl(d.total_brl ?? 0)} nota={rotuloDoMes} />
                  <Bloco
                    rotulo="Energia"
                    valor={`${num(d.energia_kwh ?? 0, 0)} kWh`}
                    nota={`${d.sessoes ?? 0} recargas`}
                  />
                  <Bloco
                    rotulo="Frota"
                    valor={`${d.veiculos ?? 0}`}
                    nota={`${d.motoristas ?? 0} motoristas`}
                  />
                </View>

                {(d.em_aberto_brl ?? 0) > 0 && (
                  <Aviso
                    tom="info"
                    mensagem={`${brl(d.em_aberto_brl ?? 0)} ainda em aberto neste período.`}
                  />
                )}

                {(d.sem_centro_brl ?? 0) > 0 && (
                  <Aviso
                    mensagem={`${brl(d.sem_centro_brl ?? 0)} sem centro de custo. Cadastre a área dos carros abaixo para o rateio fechar.`}
                  />
                )}
              </>
            )}

            {/*
              Logo abaixo do aviso que cobra a área, e nao em aba separada: o
              aviso mandava cadastrar e nao dizia onde. Ler a cobranca e agir
              sao o mesmo gesto.
            */}
            <CentroDeCusto aoAtribuir={() => void relatorio.refetch()} />
          </View>
        }
        ListEmptyComponent={
          d?.disponivel ? (
            <Aviso tom="info" mensagem="Nenhuma recarga faturada neste mês." />
          ) : null
        }
        renderItem={({ item }) => (
          <View style={s.card}>
            <View style={s.cardTopo}>
              <Text style={s.cardNome}>{item.centro_de_custo}</Text>
              <Text style={s.cardTotal}>{brl(item.total_brl)}</Text>
            </View>
            <Text style={s.cardMeta}>
              {item.sessoes} recarga(s) · {num(item.energia_kwh, 1)} kWh ·{' '}
              {item.veiculos} carro(s)
            </Text>
            <View style={s.metricas}>
              <Text style={s.metrica}>
                {brl(item.custo_medio_por_sessao_brl)} por recarga
              </Text>
              <Text style={s.metrica}>
                {brl(item.custo_por_kwh_brl)} por kWh
              </Text>
            </View>
          </View>
        )}
      />
    </Tela>
  )
}

function Bloco({ rotulo, valor, nota }: { rotulo: string; valor: string; nota: string }) {
  return (
    <View style={s.bloco}>
      <Text style={s.blocoRotulo}>{rotulo}</Text>
      <Text style={s.blocoValor}>{valor}</Text>
      <Text style={s.blocoNota}>{nota}</Text>
    </View>
  )
}

const s = StyleSheet.create({
  conteudo: { padding: espaco.md, gap: espaco.sm },
  topo: { gap: espaco.sm, marginBottom: espaco.sm },
  titulo: { color: cores.texto, fontSize: 22, fontWeight: '700' },
  subtitulo: { color: cores.textoFraco, fontSize: 13 },
  meses: { flexDirection: 'row', flexWrap: 'wrap', gap: espaco.xs },
  chip: {
    color: cores.textoFraco,
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: raio.sm,
    paddingVertical: 5,
    paddingHorizontal: espaco.sm,
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'capitalize',
    overflow: 'hidden'
  },
  chipAtivo: { color: cores.texto, borderColor: cores.acento, backgroundColor: cores.superficie },
  resumo: { flexDirection: 'row', gap: espaco.sm },
  bloco: {
    flex: 1,
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.sm,
    gap: 2
  },
  blocoRotulo: {
    color: cores.textoFraco,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase'
  },
  blocoValor: { color: cores.texto, fontSize: 17, fontWeight: '700' },
  blocoNota: { color: cores.textoFraco, fontSize: 11 },
  card: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: 4
  },
  cardTopo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: espaco.sm },
  cardNome: { color: cores.texto, fontSize: 16, fontWeight: '700', flexShrink: 1 },
  cardTotal: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  cardMeta: { color: cores.textoFraco, fontSize: 12 },
  metricas: { flexDirection: 'row', gap: espaco.md, marginTop: 2 },
  metrica: { color: cores.textoFraco, fontSize: 12 }
})
