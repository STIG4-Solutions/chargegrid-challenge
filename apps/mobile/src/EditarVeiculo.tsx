import { useState } from 'react'
import { StyleSheet, Text, TextInput, View } from 'react-native'
import { app, useAction, type Veiculo } from '@chargegrid/sdk'
import { camposIniciais, corpoDaEdicao, problemaNaEdicao, type CamposDoVeiculo } from './veiculo'
import { Aviso, Botao } from './components'
import { cores, espaco, raio } from './theme'

/**
 * Correção do cadastro do carro.
 *
 * O perfil tinha adicionar e remover, e nada entre os dois: uma placa digitada
 * errada só se corrigia apagando o carro e cadastrando de novo — o que apaga o
 * vínculo do histórico junto (`DELETE /app/vehicles/{id}` é ON DELETE SET NULL,
 * e as sessões passadas ficam órfãs de carro). `PATCH /app/vehicles/{id}`
 * existia desde sempre, com a docstring dizendo exatamente este caso — "placa
 * digitada errada, bateria trocada" — e nenhuma tela chamava.
 */

export default function EditarVeiculo({
  veiculo,
  aoSalvar,
  aoFechar
}: {
  veiculo: Veiculo
  aoSalvar: () => void
  aoFechar: () => void
}) {
  const [campos, setCampos] = useState<CamposDoVeiculo>(() => camposIniciais(veiculo))
  const corpo = corpoDaEdicao(veiculo, campos)
  const problema = problemaNaEdicao(campos)
  const nadaMudou = Object.keys(corpo).length === 0

  const salvar = useAction(() => app.updateVehicle(veiculo.id, corpo), {
    onSuccess: () => aoSalvar()
  })

  const campo = (chave: keyof CamposDoVeiculo) => (texto: string) =>
    setCampos((atual) => ({ ...atual, [chave]: texto }))

  return (
    <View style={s.editor}>
      <TextInput
        style={s.input}
        value={campos.modelo}
        onChangeText={campo('modelo')}
        placeholder="Modelo"
        placeholderTextColor={cores.textoFraco}
        maxLength={80}
      />
      <View style={s.linha}>
        <TextInput
          style={[s.input, s.meio]}
          value={campos.placa}
          onChangeText={campo('placa')}
          autoCapitalize="characters"
          placeholder="Placa"
          placeholderTextColor={cores.textoFraco}
        />
        <TextInput
          style={[s.input, s.meio]}
          value={campos.bateria}
          onChangeText={campo('bateria')}
          keyboardType="decimal-pad"
          placeholder="Bateria (kWh)"
          placeholderTextColor={cores.textoFraco}
        />
      </View>

      {problema && <Text style={s.problema}>{problema}</Text>}
      {salvar.error && <Aviso mensagem={salvar.error.detail} />}

      <View style={s.acoes}>
        <Botao
          titulo={salvar.pending ? 'Salvando...' : 'Salvar'}
          disabled={Boolean(problema) || nadaMudou || salvar.pending}
          pending={salvar.pending}
          onPress={() => void salvar.run()}
        />
        <Botao
          titulo="Cancelar"
          variante="secundario"
          disabled={salvar.pending}
          onPress={aoFechar}
        />
      </View>
    </View>
  )
}

const s = StyleSheet.create({
  editor: { gap: espaco.sm, marginTop: espaco.sm },
  input: {
    color: cores.texto,
    backgroundColor: cores.fundo,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.sm,
    paddingHorizontal: espaco.sm,
    paddingVertical: espaco.sm,
    fontSize: 14
  },
  linha: { flexDirection: 'row', gap: espaco.sm },
  meio: { flex: 1 },
  acoes: { flexDirection: 'row', gap: espaco.sm },
  problema: { color: cores.textoFraco, fontSize: 12 }
})
