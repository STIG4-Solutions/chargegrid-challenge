import { useState } from 'react'
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { app } from '@chargegrid/sdk'
import { Aviso, Botao } from './components'
import { cores, espaco, raio } from './theme'

/**
 * Reportar um problema no ponto.
 *
 * Fecha o ciclo com a manutenção preditiva do painel. O registrador cobre o
 * que o equipamento sabe de si — sobretemperatura, falha de trava, perda de
 * comunicação. Não cobre cabo cortado, tela apagada nem vaga tomada por um
 * carro a combustão: nesses casos o ponto reporta "disponível" com toda a
 * sinceridade, e quem vê é a pessoa que chegou ali.
 *
 * As categorias são fechadas de propósito. Campo livre sozinho vira
 * depoimento, e depoimento não agrega: três pessoas descrevendo o mesmo cabo
 * rompido com palavras diferentes viram três problemas num relatório que
 * deveria mostrar um. O texto existe, mas como complemento.
 */
const CATEGORIAS: { valor: string; rotulo: string; dica: string }[] = [
  { valor: 'nao_inicia', rotulo: 'Não inicia a recarga', dica: 'Pluguei e nada acontece' },
  { valor: 'conector_travado', rotulo: 'Conector travado', dica: 'Não solta do carro' },
  { valor: 'cabo_danificado', rotulo: 'Cabo danificado', dica: 'Cabo cortado ou fio à mostra' },
  { valor: 'tela_apagada', rotulo: 'Tela apagada', dica: 'Carregador sem energia' },
  { valor: 'vaga_ocupada', rotulo: 'Vaga ocupada', dica: 'Carro que não está carregando' },
  { valor: 'qr_ilegivel', rotulo: 'QR ilegível', dica: 'Adesivo rasgado ou sujo' },
  { valor: 'outro', rotulo: 'Outro', dica: 'Descreva abaixo' }
]

export function ReportarProblema({
  chargePointId,
  codigo,
  sessionId
}: {
  chargePointId: string
  codigo: string
  sessionId?: string
}) {
  const [aberto, setAberto] = useState(false)
  const [categoria, setCategoria] = useState<string | null>(null)
  const [descricao, setDescricao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)

  function fechar() {
    setAberto(false)
    setCategoria(null)
    setDescricao('')
    setErro(null)
  }

  async function enviar() {
    if (!categoria) return
    setErro(null)
    setEnviando(true)
    try {
      await app.reportProblem(chargePointId, {
        categoria,
        descricao: descricao.trim() || undefined,
        session_id: sessionId
      })
      setEnviado(true)
      fechar()
    } catch (e) {
      setErro((e as { detail?: string })?.detail || 'Não foi possível enviar. Tente de novo.')
    } finally {
      setEnviando(false)
    }
  }

  if (enviado) {
    return (
      <View style={s.confirmado}>
        <Text style={s.confirmadoTitulo}>Problema reportado</Text>
        <Text style={s.confirmadoTexto}>
          A equipe do estabelecimento foi avisada. Obrigado — reportes como o seu são o que faz
          um defeito ser corrigido antes de pegar a próxima pessoa.
        </Text>
      </View>
    )
  }

  return (
    <View>
      <Botao
        titulo="Reportar problema"
        variante="secundario"
        onPress={() => setAberto(true)}
      />

      <Modal visible={aberto} animationType="slide" transparent onRequestClose={fechar}>
        <View style={s.fundo}>
          <View style={s.folha}>
            <Text style={s.titulo}>O que houve no {codigo}?</Text>
            <Text style={s.subtitulo}>
              O carregador só reporta o que tem sensor. O resto depende de quem esteve aqui.
            </Text>

            <ScrollView style={s.lista} keyboardShouldPersistTaps="handled">
              {CATEGORIAS.map((c) => {
                const ativa = c.valor === categoria
                return (
                  <Pressable
                    key={c.valor}
                    accessibilityRole="button"
                    accessibilityState={{ selected: ativa }}
                    onPress={() => setCategoria(c.valor)}
                    style={[s.opcao, ativa && s.opcaoAtiva]}
                  >
                    <Text style={[s.opcaoRotulo, ativa && s.opcaoRotuloAtivo]}>{c.rotulo}</Text>
                    <Text style={s.opcaoDica}>{c.dica}</Text>
                  </Pressable>
                )
              })}

              <Text style={s.rotuloCampo}>Detalhes (opcional)</Text>
              <TextInput
                value={descricao}
                onChangeText={setDescricao}
                placeholder="O que você viu, em poucas palavras"
                placeholderTextColor={cores.textoFraco}
                multiline
                maxLength={1000}
                style={s.campo}
              />
            </ScrollView>

            {erro && <Aviso mensagem={erro} />}

            <View style={s.acoes}>
              <Botao
                titulo={enviando ? 'Enviando...' : 'Enviar'}
                disabled={!categoria}
                pending={enviando}
                onPress={() => void enviar()}
              />
              <Botao titulo="Cancelar" variante="secundario" onPress={fechar} />
            </View>
          </View>
        </View>
      </Modal>
    </View>
  )
}

const s = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  folha: {
    backgroundColor: cores.fundo,
    borderTopLeftRadius: raio.md,
    borderTopRightRadius: raio.md,
    padding: espaco.md,
    gap: espaco.sm,
    maxHeight: '85%'
  },
  titulo: { color: cores.texto, fontSize: 18, fontWeight: '700' },
  subtitulo: { color: cores.textoFraco, fontSize: 13, lineHeight: 18 },
  lista: { marginVertical: espaco.xs },
  opcao: {
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: raio.sm,
    padding: espaco.sm,
    marginBottom: espaco.xs,
    backgroundColor: cores.superficie
  },
  opcaoAtiva: { borderColor: cores.acento, backgroundColor: cores.superficieAlta },
  opcaoRotulo: { color: cores.texto, fontSize: 15, fontWeight: '600' },
  opcaoRotuloAtivo: { color: cores.acento },
  opcaoDica: { color: cores.textoFraco, fontSize: 12, marginTop: 2 },
  rotuloCampo: {
    color: cores.textoFraco,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
    marginTop: espaco.sm,
    marginBottom: 4
  },
  campo: {
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: raio.sm,
    backgroundColor: cores.superficieAlta,
    color: cores.texto,
    padding: espaco.sm,
    minHeight: 80,
    textAlignVertical: 'top'
  },
  acoes: { gap: espaco.xs },
  confirmado: {
    borderWidth: 1,
    borderColor: cores.verde,
    borderRadius: raio.md,
    padding: espaco.md,
    backgroundColor: cores.superficieAlta,
    gap: 4
  },
  confirmadoTitulo: { color: cores.verde, fontSize: 15, fontWeight: '700' },
  confirmadoTexto: { color: cores.texto, fontSize: 13, lineHeight: 19 }
})
