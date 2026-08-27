import { useMemo, useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import {
  app,
  num,
  useAction,
  useApi,
  type Estacao,
  type PontoDaEstacao,
  type Veiculo
} from '@chargegrid/sdk'
import { Aviso, Botao, Carregando , useRecuoInferior } from '../components'
import { quando } from '../format'
import { cores, espaco, raio } from '../theme'
import type { Props } from '../navigation'

// Horários oferecidos: próximas 12 meias-horas cheias. Um seletor de data
// nativo seria mais flexível, mas para agendar uma recarga o motorista quer
// escolher rápido — não navegar num calendário.
function proximosHorarios(qtd = 12): Date[] {
  const agora = new Date()
  const base = new Date(agora)
  base.setSeconds(0, 0)
  base.setMinutes(agora.getMinutes() < 30 ? 30 : 60)
  return Array.from({ length: qtd }, (_, i) => new Date(base.getTime() + i * 30 * 60_000))
}

const DURACOES = [30, 60, 90, 120]

export default function NewReservationScreen({ navigation }: Props<'NovoAgendamento'>) {
  const recuo = useRecuoInferior()
  const estacoes = useApi<Estacao[]>(() => app.stations(), [])
  const veiculos = useApi<Veiculo[]>(() => app.myVehicles(), [])

  const [siteId, setSiteId] = useState<string | null>(null)
  const siteEscolhido = siteId ?? estacoes.data?.[0]?.site_id ?? null

  const pontos = useApi<PontoDaEstacao[]>(
    () => app.stationChargePoints(siteEscolhido as string),
    [siteEscolhido],
    { enabled: Boolean(siteEscolhido) }
  )

  const [pontoId, setPontoId] = useState<string | null>(null)
  const [veiculoId, setVeiculoId] = useState<string | null>(null)
  const [inicio, setInicio] = useState<Date>(() => proximosHorarios(1)[0])
  const [duracao, setDuracao] = useState(60)
  const [alvo, setAlvo] = useState('')

  const horarios = useMemo(() => proximosHorarios(), [])
  const ponto = pontos.data?.find((p) => p.id === pontoId) ?? pontos.data?.[0] ?? null
  const veiculo = veiculos.data?.find((v) => v.id === veiculoId) ?? veiculos.data?.[0] ?? null

  const agendar = useAction(
    () =>
      app.createReservation({
        charge_point_id: ponto?.id,
        vehicle_id: veiculo?.id ?? null,
        starts_at: inicio.toISOString(),
        ends_at: new Date(inicio.getTime() + duracao * 60_000).toISOString(),
        target_kwh: alvo ? Number(alvo.replace(',', '.')) : null
      }),
    { onSuccess: () => navigation.goBack() }
  )

  if (estacoes.loading && !estacoes.data) return <Carregando rotulo="Carregando estações..." />

  return (
    <ScrollView style={s.tela} contentContainerStyle={[s.conteudo, { paddingBottom: recuo + espaco.xl }]}>
      {estacoes.error && <Aviso mensagem={estacoes.error.detail} />}

      <Secao titulo="Estação">
        <Chips
          itens={(estacoes.data ?? []).map((e) => ({ id: e.site_id, rotulo: e.name }))}
          escolhido={siteEscolhido}
          aoEscolher={(id) => {
            setSiteId(id)
            setPontoId(null)
          }}
        />
      </Secao>

      <Secao titulo="Vaga">
        {pontos.loading && !pontos.data ? (
          <Text style={s.aguardando}>Carregando vagas...</Text>
        ) : (
          <Chips
            itens={(pontos.data ?? []).map((p) => ({
              id: p.id,
              rotulo: `${p.code} · ${p.connector} · ${num(p.rated_kw, 0)} kW`
            }))}
            escolhido={ponto?.id ?? null}
            aoEscolher={setPontoId}
          />
        )}
        <Text style={s.nota}>
          Agendar reserva a potência da vaga no orçamento do site durante a janela — por isso ela
          fica indisponível para outros motoristas nesse período.
        </Text>
      </Secao>

      {(veiculos.data ?? []).length > 0 && (
        <Secao titulo="Veículo">
          <Chips
            itens={(veiculos.data ?? []).map((v) => ({ id: v.id, rotulo: v.model }))}
            escolhido={veiculo?.id ?? null}
            aoEscolher={setVeiculoId}
          />
        </Secao>
      )}

      <Secao titulo="Início">
        <Chips
          itens={horarios.map((h) => ({ id: h.toISOString(), rotulo: quando(h.toISOString()) }))}
          escolhido={inicio.toISOString()}
          aoEscolher={(iso) => setInicio(new Date(iso))}
        />
      </Secao>

      <Secao titulo="Duração">
        <Chips
          itens={DURACOES.map((d) => ({ id: String(d), rotulo: `${d} min` }))}
          escolhido={String(duracao)}
          aoEscolher={(d) => setDuracao(Number(d))}
        />
      </Secao>

      <Secao titulo="Energia desejada (opcional)">
        <TextInput
          style={s.input}
          value={alvo}
          onChangeText={setAlvo}
          keyboardType="numeric"
          placeholder="ex.: 25"
          placeholderTextColor={cores.textoFraco}
        />
        <Text style={s.nota}>Em kWh. A recarga encerra ao atingir esse valor.</Text>
      </Secao>

      {agendar.error && <Aviso mensagem={agendar.error.detail} />}

      <Botao
        titulo={ponto ? `Agendar ${ponto.code} · ${quando(inicio.toISOString())}` : 'Escolha uma vaga'}
        disabled={!ponto}
        pending={agendar.pending}
        onPress={() => void agendar.run()}
      />
    </ScrollView>
  )
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <View style={s.secao}>
      <Text style={s.secaoTitulo}>{titulo}</Text>
      {children}
    </View>
  )
}

function Chips({
  itens,
  escolhido,
  aoEscolher
}: {
  itens: Array<{ id: string; rotulo: string }>
  escolhido: string | null
  aoEscolher: (id: string) => void
}) {
  return (
    <View style={s.chips}>
      {itens.map((item) => {
        const ativo = item.id === escolhido
        return (
          <Pressable
            key={item.id}
            onPress={() => aoEscolher(item.id)}
            style={[s.chip, ativo && s.chipAtivo]}
            accessibilityRole="button"
            accessibilityState={{ selected: ativo }}
          >
            <Text style={[s.chipTexto, ativo && s.chipTextoAtivo]}>{item.rotulo}</Text>
          </Pressable>
        )
      })}
    </View>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: espaco.md, gap: espaco.lg, paddingBottom: espaco.xl },
  secao: { gap: espaco.sm },
  secaoTitulo: { color: cores.texto, fontSize: 14, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: espaco.sm },
  chip: {
    borderWidth: 1,
    borderColor: cores.borda,
    backgroundColor: cores.superficie,
    borderRadius: 999,
    paddingHorizontal: espaco.md,
    paddingVertical: 8
  },
  chipAtivo: { borderColor: cores.acento, backgroundColor: '#FF323A22' },
  chipTexto: { color: cores.textoFraco, fontSize: 13 },
  chipTextoAtivo: { color: cores.texto, fontWeight: '600' },
  input: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    color: cores.texto,
    fontSize: 16,
    paddingHorizontal: espaco.md,
    paddingVertical: 12
  },
  nota: { color: cores.textoFraco, fontSize: 11, lineHeight: 15 },
  aguardando: { color: cores.textoFraco, fontSize: 13 }
})
