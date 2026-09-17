import { useState } from 'react'
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { app, useAction, useApi, type VeiculoDaFrota } from '@chargegrid/sdk'
import { CENTRO_MAXIMO, centrosEmUso, problemaNoCentro, semArea } from './frota'
import { Aviso, Botao } from './components'
import { cores, espaco, raio } from './theme'

/**
 * Atribuição de centro de custo aos carros da frota.
 *
 * Existe porque a tela da frota já mandava fazer isto e não dizia onde: o aviso
 * "R$ X sem centro de custo. Cadastre a área dos carros para o rateio fechar."
 * aparecia, e não havia tela nenhuma que cadastrasse. `PUT
 * /app/fleet/vehicles/{id}/cost-center` existia, testado, desde a 0013 — sem
 * caminho até ele.
 *
 * O relatório lê o centro de custo ATUAL do veículo (`fleet_service:110`), e
 * não uma cópia congelada na sessão. Por isso atribuir reclassifica o mês
 * inteiro de uma vez, e por isso salvar aqui recarrega o relatório junto: o
 * aviso encolhe na hora, que é a confirmação de que a atribuição valeu.
 */

export default function CentroDeCusto({ aoAtribuir }: { aoAtribuir?: () => void }) {
  const veiculos = useApi<VeiculoDaFrota[]>(() => app.fleetVehicles(), [])
  const [editando, setEditando] = useState<string | null>(null)
  const [texto, setTexto] = useState('')

  const lista = veiculos.data ?? []
  // Sem `useMemo`: `lista` e' um array novo a cada render (`data ?? []`),
  // entao a dependencia nunca seria igual e a memoria nao memorizaria nada.
  const sugestoes = centrosEmUso(lista)
  const pendentes = semArea(lista)

  const salvar = useAction((id: string, centro: string | null) => app.setCostCenter(id, centro), {
    onSuccess: () => {
      setEditando(null)
      setTexto('')
      void veiculos.refetch()
      // O relatório agrupa pelo centro ATUAL do carro: sem recarregá-lo, o
      // aviso de "sem centro de custo" continuaria cobrando o que acabou de
      // ser resolvido.
      aoAtribuir?.()
    }
  })

  if (!veiculos.loading && lista.length === 0) return null

  return (
    <View style={s.secao}>
      <View style={s.cabecalho}>
        <Text style={s.titulo}>Carros da frota</Text>
        {pendentes > 0 && <Text style={s.contador}>{pendentes} sem área</Text>}
      </View>
      <Text style={s.ajuda}>
        A área do carro vale para o mês inteiro, inclusive para as recargas já faturadas.
      </Text>

      {veiculos.error && <Aviso mensagem={veiculos.error.detail} />}
      {salvar.error && <Aviso mensagem={salvar.error.detail} />}

      {lista.map((v) => {
        const aberto = editando === v.id
        const problema = problemaNoCentro(texto)
        return (
          <View key={v.id} style={[s.carro, aberto && s.carroAberto]}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ expanded: aberto }}
              onPress={() => {
                setEditando(aberto ? null : v.id)
                setTexto(v.centro_de_custo ?? '')
                salvar.clearError()
              }}
              style={s.linha}
            >
              <View style={s.identidade}>
                <Text style={s.modelo}>{v.modelo}</Text>
                <Text style={s.meta}>{[v.placa, v.motorista].filter(Boolean).join(' · ')}</Text>
              </View>
              <Text style={[s.area, !v.centro_de_custo && s.areaVazia]}>
                {v.centro_de_custo ?? 'sem área'}
              </Text>
            </Pressable>

            {aberto && (
              <View style={s.editor}>
                {sugestoes.length > 0 && (
                  <View style={s.sugestoes}>
                    {sugestoes.map((nome) => (
                      <Text
                        key={nome}
                        accessibilityRole="button"
                        onPress={() => setTexto(nome)}
                        style={[s.chip, texto.trim() === nome && s.chipAtivo]}
                      >
                        {nome}
                      </Text>
                    ))}
                  </View>
                )}
                <TextInput
                  value={texto}
                  onChangeText={setTexto}
                  placeholder="Nome da área"
                  placeholderTextColor={cores.textoFraco}
                  maxLength={CENTRO_MAXIMO}
                  autoCapitalize="words"
                  style={s.campo}
                />
                <View style={s.acoes}>
                  <Botao
                    titulo={salvar.pending ? 'Salvando...' : 'Salvar'}
                    disabled={Boolean(problema) || salvar.pending}
                    pending={salvar.pending}
                    onPress={() => void salvar.run(v.id, texto.trim())}
                  />
                  <Botao
                    titulo="Sem área"
                    variante="secundario"
                    disabled={salvar.pending || !v.centro_de_custo}
                    onPress={() => void salvar.run(v.id, null)}
                  />
                </View>
                {problema && texto.length > 0 && <Text style={s.problema}>{problema}</Text>}
              </View>
            )}
          </View>
        )
      })}
    </View>
  )
}

const s = StyleSheet.create({
  secao: { gap: espaco.xs, marginTop: espaco.md },
  cabecalho: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: espaco.sm
  },
  titulo: { color: cores.texto, fontSize: 16, fontWeight: '700' },
  contador: { color: cores.textoFraco, fontSize: 12, fontWeight: '600' },
  ajuda: { color: cores.textoFraco, fontSize: 12, marginBottom: espaco.xs },
  carro: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    paddingHorizontal: espaco.md,
    paddingVertical: espaco.sm
  },
  carroAberto: { borderColor: cores.acento },
  linha: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: espaco.sm
  },
  identidade: { flexShrink: 1, gap: 2 },
  modelo: { color: cores.texto, fontSize: 14, fontWeight: '600' },
  meta: { color: cores.textoFraco, fontSize: 12 },
  area: { color: cores.texto, fontSize: 13, fontWeight: '600' },
  areaVazia: { color: cores.textoFraco, fontStyle: 'italic', fontWeight: '400' },
  editor: { gap: espaco.sm, marginTop: espaco.sm },
  sugestoes: { flexDirection: 'row', flexWrap: 'wrap', gap: espaco.xs },
  chip: {
    color: cores.textoFraco,
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: raio.sm,
    paddingVertical: 4,
    paddingHorizontal: espaco.sm,
    fontSize: 12,
    fontWeight: '600',
    overflow: 'hidden'
  },
  chipAtivo: { color: cores.texto, borderColor: cores.acento },
  campo: {
    color: cores.texto,
    backgroundColor: cores.fundo,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.sm,
    paddingHorizontal: espaco.sm,
    paddingVertical: espaco.sm,
    fontSize: 14
  },
  acoes: { flexDirection: 'row', gap: espaco.sm },
  problema: { color: cores.textoFraco, fontSize: 12 }
})
