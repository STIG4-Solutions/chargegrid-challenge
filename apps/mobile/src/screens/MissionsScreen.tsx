import { useCallback } from 'react'
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { app, useApi } from '@chargegrid/sdk'
import type { Missao, Recompensa } from '@chargegrid/sdk'

import { Carregando, Etiqueta, Tela, useRecuoInferior } from '../components'
import { cores, espaco, raio } from '../theme'

// Como cada métrica se lê em português, com a unidade. Sem isto a tela diria
// "3 de 5 energia_verde_kwh", que é o nome da coluna e não da coisa.
const UNIDADES: Record<string, (valor: number) => string> = {
  sessoes: (v) => (v === 1 ? '1 recarga' : `${v} recargas`),
  energia_kwh: (v) => `${v.toFixed(1)} kWh`,
  energia_verde_kwh: (v) => `${v.toFixed(1)} kWh solares`,
  valor_brl: (v) => `R$ ${v.toFixed(2).replace('.', ',')}`,
  dias_distintos: (v) => (v === 1 ? '1 dia' : `${v} dias`),
  sessoes_fora_de_ponta: (v) => (v === 1 ? '1 recarga' : `${v} recargas`)
}

const JANELAS: Record<string, string> = {
  campanha: 'até o fim da campanha',
  mensal: 'este mês',
  semanal: 'esta semana'
}

function medida(metrica: string, valor: number): string {
  const formata = UNIDADES[metrica]
  return formata ? formata(valor) : String(valor)
}

function Barra({ progresso, alvo, concluida }: { progresso: number; alvo: number; concluida: boolean }) {
  const pct = alvo > 0 ? Math.min(100, (progresso / alvo) * 100) : 0
  return (
    <View style={s.trilho}>
      <View
        style={[
          s.preenchido,
          { width: `${pct}%`, backgroundColor: concluida ? cores.verde : cores.acento }
        ]}
      />
    </View>
  )
}

function CartaoDeMissao({ missao }: { missao: Missao }) {
  const restante = Math.max(0, missao.alvo - missao.progresso)
  return (
    <View style={[s.cartao, missao.concluida && s.cartaoConcluido]}>
      <View style={s.cabecalho}>
        <Text style={s.titulo}>{missao.titulo}</Text>
        <Etiqueta
          texto={missao.concluida ? 'Concluída' : missao.recompensa}
          cor={missao.concluida ? cores.verde : cores.acento}
        />
      </View>

      {missao.descricao ? <Text style={s.descricao}>{missao.descricao}</Text> : null}

      <Barra progresso={missao.progresso} alvo={missao.alvo} concluida={missao.concluida} />

      <View style={s.rodape}>
        <Text style={s.numeros}>
          {medida(missao.metrica, missao.progresso)} de {medida(missao.metrica, missao.alvo)}
        </Text>
        <Text style={s.janela}>
          {missao.concluida ? `${missao.recompensa} a caminho` : `faltam ${medida(missao.metrica, restante)}`}
        </Text>
      </View>

      <Text style={s.campanha}>
        {missao.campanha} · {JANELAS[missao.janela] ?? missao.janela}
      </Text>
    </View>
  )
}

export default function MissionsScreen() {
  const missoes = useApi<Missao[]>(() => app.missions(), [])
  const recompensas = useApi<Recompensa[]>(() => app.rewards(), [])
  const recuo = useRecuoInferior()

  const recarregar = useCallback(() => {
    missoes.refetch()
    recompensas.refetch()
  }, [missoes, recompensas])

  const creditado = (recompensas.data ?? [])
    .filter((r) => r.estado === 'creditada')
    .reduce((soma, r) => soma + r.valor_brl, 0)

  if (missoes.loading && !missoes.data) return <Carregando rotulo="Buscando missões…" />

  const lista = missoes.data ?? []

  return (
    <Tela>
      <FlatList
        data={lista}
        keyExtractor={(m) => m.id}
        renderItem={({ item }) => <CartaoDeMissao missao={item} />}
        contentContainerStyle={[s.conteudo, { paddingBottom: recuo + espaco.xl }]}
        refreshControl={
          <RefreshControl
            refreshing={missoes.loading}
            onRefresh={recarregar}
            tintColor={cores.acento}
          />
        }
        ListHeaderComponent={
          <View>
            <Text style={s.pagina}>Missões</Text>
            <View style={s.resumo}>
              <View style={s.bloco}>
                <Text style={s.rotulo}>Já recebido</Text>
                <Text style={s.valor}>R$ {creditado.toFixed(2).replace('.', ',')}</Text>
                <Text style={s.nota}>na sua carteira</Text>
              </View>
              <View style={s.bloco}>
                <Text style={s.rotulo}>Em aberto</Text>
                <Text style={s.valor}>{lista.filter((m) => !m.concluida).length}</Text>
                <Text style={s.nota}>missões a cumprir</Text>
              </View>
            </View>
          </View>
        }
        ListEmptyComponent={
          // Vazio não é erro: pode simplesmente não haver campanha vigente. Dizer
          // isso é melhor que uma tela em branco, que se lê como falha do app.
          <View style={s.vazio}>
            <Text style={s.vazioTitulo}>Nenhuma missão agora</Text>
            <Text style={s.vazioTexto}>
              Os eletropostos criam campanhas de tempos em tempos. Quando houver uma valendo, ela
              aparece aqui — e o que você já recarregou passa a contar.
            </Text>
          </View>
        }
      />
    </Tela>
  )
}

const s = StyleSheet.create({
  conteudo: { padding: espaco.md, gap: espaco.md },
  pagina: { color: cores.texto, fontSize: 24, fontWeight: '700', marginBottom: espaco.md },
  resumo: { flexDirection: 'row', gap: espaco.sm, marginBottom: espaco.sm },
  bloco: {
    flex: 1,
    backgroundColor: cores.superficie,
    borderRadius: raio.md,
    borderWidth: 1,
    borderColor: cores.borda,
    padding: espaco.md
  },
  rotulo: { color: cores.textoFraco, fontSize: 12 },
  valor: { color: cores.texto, fontSize: 22, fontWeight: '700', marginTop: 2 },
  nota: { color: cores.textoFraco, fontSize: 11, marginTop: 2 },

  cartao: {
    backgroundColor: cores.superficie,
    borderRadius: raio.md,
    borderWidth: 1,
    borderColor: cores.borda,
    padding: espaco.md,
    gap: espaco.sm
  },
  cartaoConcluido: { borderColor: cores.verde },
  cabecalho: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: espaco.sm },
  titulo: { color: cores.texto, fontSize: 16, fontWeight: '600', flexShrink: 1 },
  descricao: { color: cores.textoFraco, fontSize: 13 },

  trilho: { height: 8, borderRadius: 999, backgroundColor: cores.superficieAlta, overflow: 'hidden' },
  preenchido: { height: 8, borderRadius: 999 },

  rodape: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  numeros: { color: cores.texto, fontSize: 13, fontWeight: '600' },
  janela: { color: cores.textoFraco, fontSize: 12 },
  campanha: { color: cores.textoFraco, fontSize: 11 },

  vazio: { padding: espaco.lg, alignItems: 'center', gap: espaco.sm },
  vazioTitulo: { color: cores.texto, fontSize: 16, fontWeight: '600' },
  vazioTexto: { color: cores.textoFraco, fontSize: 13, textAlign: 'center', lineHeight: 19 }
})
