import { useCallback, useRef, useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { useIsFocused } from '@react-navigation/native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { app, useAction, type ApiError, type PontoLido } from '@chargegrid/sdk'
import { Aviso, Botao, useRecuoInferior } from '../components'
import { codigoDoQr } from '../qr'
import { cores, espaco, raio } from '../theme'
import type { Props } from '../navigation'

export default function ScannerScreen({ navigation }: Props<'Escanear'>) {
  const [permissao, pedirPermissao] = useCameraPermissions()
  const [digitando, setDigitando] = useState(false)
  const [codigoManual, setCodigoManual] = useState('')
  const [naoReconhecido, setNaoReconhecido] = useState<string | null>(null)
  const [falhaDaCamera, setFalhaDaCamera] = useState(false)
  const recuo = useRecuoInferior()

  // A previa e' uma superficie nativa: se continuar montada quando a tela sai de
  // foco, ela volta preta na proxima visita. Desmontar junto com o foco resolve.
  const focada = useIsFocused()

  // A camera dispara varias leituras por segundo do mesmo QR. Sem a trava, a
  // primeira ja navega e as seguintes empilham telas iguais por cima.
  const lendo = useRef(false)

  const resolver = useAction((codigo: string) => app.chargePointByCode(codigo), {
    onSuccess: (ponto: PontoLido) => {
      lendo.current = false
      navigation.replace('Estacao', {
        siteId: ponto.site_id,
        nome: ponto.site_name,
        destaque: ponto.code
      })
    },
    onError: () => {
      lendo.current = false
    }
  })

  const aoLer = useCallback(
    ({ data }: { data: string }) => {
      if (lendo.current || resolver.pending) return
      const codigo = codigoDoQr(data)
      if (!codigo) {
        setNaoReconhecido(data.slice(0, 60))
        return
      }
      lendo.current = true
      setNaoReconhecido(null)
      void resolver.run(codigo)
    },
    [resolver]
  )

  function enviarManual() {
    const codigo = codigoDoQr(codigoManual) ?? codigoManual.trim().toUpperCase()
    if (codigo) void resolver.run(codigo)
  }

  const erro = resolver.error as ApiError | null
  const podeFilmar = permissao?.granted === true && !falhaDaCamera

  return (
    <ScrollView
      style={s.tela}
      contentContainerStyle={[s.conteudo, { paddingBottom: recuo + espaco.lg }]}
      keyboardShouldPersistTaps="handled"
    >
      {/* O visor tem altura fixa e nenhum filho nem irmao por cima. A previa da
          camera e' desenhada por uma superficie nativa que, no Android, ignora a
          ordem normal das views - qualquer mira ou texto sobreposto some ou
          apaga a tela inteira. Por isso a mira e a instrucao ficam abaixo. */}
      {podeFilmar ? (
        <View style={s.visor}>
          {focada && (
            <CameraView
              style={s.camera}
              facing="back"
              barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              onBarcodeScanned={resolver.pending ? undefined : aoLer}
              onMountError={() => setFalhaDaCamera(true)}
            />
          )}
        </View>
      ) : (
        <View style={[s.visor, s.visorVazio]}>
          <Text style={s.visorTitulo}>{tituloDoVisor(permissao?.canAskAgain, falhaDaCamera)}</Text>
          <Text style={s.visorTexto}>{textoDoVisor(permissao?.canAskAgain, falhaDaCamera)}</Text>
          {!falhaDaCamera && permissao?.canAskAgain !== false && (
            <Botao titulo="Permitir câmera" onPress={() => void pedirPermissao()} />
          )}
        </View>
      )}

      {podeFilmar && (
        <Text style={s.dica}>
          {resolver.pending ? 'Consultando o ponto...' : 'Enquadre o QR colado no carregador'}
        </Text>
      )}

      {erro && <Aviso mensagem={erro.detail} />}
      {naoReconhecido && !erro && (
        <Aviso
          tom="info"
          mensagem={`Este QR não é de um ponto ChargeGrid ("${naoReconhecido}"). Aponte para o adesivo do carregador.`}
        />
      )}

      {digitando ? (
        <View style={s.painel}>
          <Text style={s.rotulo}>Código impresso no carregador</Text>
          <TextInput
            style={s.input}
            value={codigoManual}
            onChangeText={setCodigoManual}
            autoCapitalize="characters"
            autoCorrect={false}
            placeholder="ex.: CP-01"
            placeholderTextColor={cores.textoFraco}
            onSubmitEditing={enviarManual}
            returnKeyType="go"
          />
          <Botao
            titulo="Buscar ponto"
            disabled={codigoManual.trim().length === 0}
            pending={resolver.pending}
            onPress={enviarManual}
          />
          {podeFilmar && (
            <Pressable onPress={() => setDigitando(false)} accessibilityRole="button">
              <Text style={s.alternar}>Voltar para a câmera</Text>
            </Pressable>
          )}
        </View>
      ) : (
        <Pressable onPress={() => setDigitando(true)} accessibilityRole="button">
          <Text style={s.alternar}>QR danificado? Digitar o código</Text>
        </Pressable>
      )}
    </ScrollView>
  )
}

function tituloDoVisor(podePerguntar: boolean | undefined, falhou: boolean) {
  if (falhou) return 'Câmera indisponível'
  return podePerguntar === false ? 'Câmera bloqueada' : 'Câmera desligada'
}

function textoDoVisor(podePerguntar: boolean | undefined, falhou: boolean) {
  if (falhou) return 'Não foi possível abrir a câmera deste aparelho. Digite o código impresso no carregador.'
  return podePerguntar === false
    ? 'Libere o acesso à câmera nas configurações do aparelho, ou digite o código impresso no carregador.'
    : 'Precisamos da câmera para ler o QR colado no carregador. Você também pode digitar o código.'
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: espaco.md, gap: espaco.sm },
  // Altura fixa em vez de flex: o visor precisa de um retangulo conhecido antes
  // de a superficie nativa medir, senao a previa nasce com altura zero (preta).
  //
  // Sem cantos arredondados, sem overflow e sem cor de fundo - de proposito. A
  // previa vem de um SurfaceView composto ABAIXO da janela do app, que so
  // aparece pelo furo transparente recortado no lugar dele. Arredondar a borda
  // manda o Android renderizar o pai num buffer a parte e o furo deixa de
  // existir; pintar um fundo opaco tapa o furo. Nos dois casos sobra preto.
  visor: { height: 340 },
  camera: { flex: 1 },
  visorVazio: {
    height: 'auto',
    borderRadius: raio.lg,
    backgroundColor: cores.superficie,
    borderWidth: 1,
    borderColor: cores.borda,
    borderStyle: 'dashed',
    padding: espaco.lg,
    gap: espaco.md,
    alignItems: 'center',
    justifyContent: 'center'
  },
  visorTitulo: { color: cores.texto, fontSize: 17, fontWeight: '700' },
  visorTexto: { color: cores.textoFraco, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  dica: { color: cores.textoFraco, fontSize: 13, textAlign: 'center', paddingVertical: espaco.xs },
  painel: { gap: espaco.sm },
  rotulo: { color: cores.textoFraco, fontSize: 12 },
  input: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    color: cores.texto,
    fontSize: 18,
    letterSpacing: 1,
    paddingHorizontal: espaco.md,
    paddingVertical: 14
  },
  alternar: {
    color: cores.textoFraco,
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: espaco.sm,
    textDecorationLine: 'underline'
  }
})
