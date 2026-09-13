import { useState } from 'react'
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { app, useApi, type MeuReporte } from '@chargegrid/sdk'
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
  // A folha encosta na base da tela, que no Android e' onde ficam os botoes de
  // navegacao. Sem o recuo, "Cancelar" nasce debaixo deles: visivel, mas o
  // toque vai para o sistema.
  //
  // O `Modal` do RN monta fora da hierarquia do app, entao o inset pode vir
  // zerado dependendo da versao — o piso de 16 garante respiro mesmo assim.
  const bordas = useSafeAreaInsets()
  const recuo = Math.max(bordas.bottom, 16)

  // O que ELE ja reportou neste ponto, com o desfecho.
  //
  // Sem isto o ciclo nao fechava: o motorista mandava o problema e nunca ficava
  // sabendo se alguem olhou. A API respondia `resolvido` desde sempre e nenhuma
  // tela chamava - `myReports` existia no SDK sem consumidor.
  const meus = useApi<MeuReporte[]>(() => app.myReports(chargePointId), [chargePointId])

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
      // A confirmação abaixo some ao remontar a tela; a lista não. Recarregar
      // aqui faz o reporte recém-enviado aparecer já como "em análise".
      void meus.refetch({ silent: true })
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
      {(meus.data ?? []).length > 0 && (
        <View style={s.historico}>
          <Text style={s.historicoTitulo}>O que você reportou aqui</Text>
          {(meus.data ?? []).map((r) => (
            <View key={r.id} style={s.linha}>
              <View style={{ flex: 1 }}>
                <Text style={s.linhaTitulo}>
                  {CATEGORIAS.find((c) => c.valor === r.categoria)?.rotulo ?? r.categoria}
                </Text>
                {/*
                  A resolução do estabelecimento aparece inteira. É a única
                  coisa que diferencia "alguém olhou" de "sumiram com isto" —
                  e foi ela que o painel passou a exigir para fechar.
                */}
                {r.resolvido && r.resolucao ? (
                  <Text style={s.linhaResolucao}>{r.resolucao}</Text>
                ) : (
                  <Text style={s.linhaEspera}>Em análise pelo estabelecimento</Text>
                )}
              </View>
              <Text style={r.resolvido ? s.selo : s.seloEspera}>
                {r.resolvido ? 'Resolvido' : 'Aberto'}
              </Text>
            </View>
          ))}
        </View>
      )}

      <Botao
        titulo="Reportar problema"
        variante="secundario"
        onPress={() => setAberto(true)}
      />

      <Modal
        visible={aberto}
        animationType="slide"
        transparent
        onRequestClose={fechar}
        // No Android a folha desenha por baixo da barra de navegação; sem isto
        // o inset de baixo volta zero e o recuo não teria de onde sair.
        statusBarTranslucent
        navigationBarTranslucent
      >
        <KeyboardAvoidingView
          style={s.fundo}
          // O campo de detalhes fica no fim da folha. Sem isto o teclado o
          // cobre justamente quando o motorista vai escrever o que viu.
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          {/* Tocar fora fecha, como toda folha inferior. */}
          <Pressable style={s.saida} onPress={fechar} accessibilityLabel="Fechar" />
          <View style={[s.folha, { paddingBottom: recuo }]}>
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
        </KeyboardAvoidingView>
      </Modal>
    </View>
  )
}

const s = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  // Área acima da folha: fecha ao toque e garante que ela nunca ocupe a tela
  // inteira, mesmo com muitas categorias.
  saida: { flex: 1, minHeight: 64 },
  folha: {
    backgroundColor: cores.fundo,
    borderTopLeftRadius: raio.md,
    borderTopRightRadius: raio.md,
    paddingHorizontal: espaco.md,
    paddingTop: espaco.md,
    gap: espaco.sm
    // Sem `maxHeight`: quem limita agora é o `flex: 1` da área de saída acima,
    // que sempre reserva espaço. Com a porcentagem, numa tela baixa a folha
    // ficava com 85% e as ações saíam por baixo — o mesmo efeito que o recuo
    // ausente causava, por outro caminho.
  },
  titulo: { color: cores.texto, fontSize: 18, fontWeight: '700' },
  subtitulo: { color: cores.textoFraco, fontSize: 13, lineHeight: 18 },
  lista: { flexShrink: 1, marginVertical: espaco.xs },
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
  historico: { gap: espaco.xs, marginBottom: espaco.sm },
  historicoTitulo: {
    color: cores.textoFraco,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.6
  },
  linha: { flexDirection: 'row', alignItems: 'center', gap: espaco.sm },
  linhaTitulo: { color: cores.texto, fontSize: 13 },
  linhaResolucao: { color: cores.verde, fontSize: 12 },
  linhaEspera: { color: cores.textoFraco, fontSize: 12 },
  selo: { color: cores.verde, fontSize: 11, fontWeight: '700' },
  seloEspera: { color: cores.ambar, fontSize: 11, fontWeight: '700' },
  confirmadoTitulo: { color: cores.verde, fontSize: 15, fontWeight: '700' },
  confirmadoTexto: { color: cores.texto, fontSize: 13, lineHeight: 19 }
})
