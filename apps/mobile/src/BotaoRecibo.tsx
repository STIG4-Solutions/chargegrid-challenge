import { useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'
import * as Print from 'expo-print'
import * as Sharing from 'expo-sharing'
import { app } from '@chargegrid/sdk'
import { Botao } from './components'
import { cores, espaco } from './theme'

/**
 * Gera o recibo em PDF e abre o menu de compartilhamento.
 *
 * A fatura já tinha tudo — linhas por tipo, preço unitário, a tarifa aplicada
 * no momento do consumo. Faltava o documento: o papel que o motorista anexa à
 * prestação de contas da empresa ou manda para o contador.
 *
 * O HTML vem do servidor, não daqui. Montar o recibo no app faria os números
 * dependerem da versão instalada: dois motoristas com builds diferentes
 * gerariam documentos diferentes para a mesma fatura.
 */
export function BotaoRecibo({ invoiceId, codigo }: { invoiceId: string; codigo: string }) {
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function gerar() {
    setErro(null)
    setOcupado(true)
    try {
      const html = await app.receiptHtml(invoiceId)
      const { uri } = await Print.printToFileAsync({ html })

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, {
          mimeType: 'application/pdf',
          dialogTitle: `Recibo ${codigo}`,
          UTI: 'com.adobe.pdf'
        })
      } else {
        // Sem app de compartilhamento (raro, mas acontece em aparelho
        // corporativo travado): imprimir é a saída que sempre existe, e o
        // diálogo do sistema oferece "salvar como PDF".
        await Print.printAsync({ html })
      }
    } catch {
      // Mensagem em vez de silêncio: aqui o motorista PEDIU o documento, então
      // ele precisa saber que não saiu — diferente do push, que é um extra.
      setErro('Não foi possível gerar o recibo. Tente de novo.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <View style={s.bloco}>
      <Botao
        titulo={ocupado ? 'Gerando...' : 'Baixar recibo'}
        variante="secundario"
        pending={ocupado}
        onPress={() => void gerar()}
      />
      {erro && <Text style={s.erro}>{erro}</Text>}
    </View>
  )
}

const s = StyleSheet.create({
  bloco: { marginTop: espaco.sm, gap: 4 },
  erro: { color: cores.acento, fontSize: 12 }
})
