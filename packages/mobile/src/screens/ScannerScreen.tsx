import { useCallback, useRef, useState } from 'react'
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { app, useAction, type ApiError, type PontoLido } from '@chargegrid/sdk'
import { Aviso, Botao } from '../components'
import { codigoDoQr } from '../qr'
import { cores, espaco, raio } from '../theme'
import type { Props } from '../navigation'

export default function ScannerScreen({ navigation }: Props<'Escanear'>) {
  const [permissao, pedirPermissao] = useCameraPermissions()
  const [digitando, setDigitando] = useState(false)
  const [codigoManual, setCodigoManual] = useState('')
  const [naoReconhecido, setNaoReconhecido] = useState<string | null>(null)

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

  // ------------------------------------------------------------- sem camera

  const cameraIndisponivel = permissao?.granted !== true

  return (
    <View style={s.tela}>
      {cameraIndisponivel ? (
        <View style={[s.visor, s.visorVazio]}>
          <Text style={s.visorTitulo}>
            {permissao?.canAskAgain === false ? 'Câmera bloqueada' : 'Câmera desligada'}
          </Text>
          <Text style={s.visorTexto}>
            {permissao?.canAskAgain === false
              ? 'Libere o acesso à câmera nas configurações do aparelho, ou digite o código impresso no carregador.'
              : 'Precisamos da câmera para ler o QR colado no carregador. Você também pode digitar o código.'}
          </Text>
          {permissao?.canAskAgain !== false && (
            <Botao titulo="Permitir câmera" onPress={() => void pedirPermissao()} />
          )}
        </View>
      ) : (
        <View style={s.visor}>
          <CameraView
            style={StyleSheet.absoluteFill}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
            onBarcodeScanned={resolver.pending ? undefined : aoLer}
          />
          {/* A sobreposicao e' irma da camera, nao filha: o CameraView avisa que
              nao suporta children. Mas a previa e' uma superficie nativa que
              desenha por cima de irmaos comuns - por isso o elevation, que no
              Android eleva a view acima dela. */}
          <View style={s.sobreposicao} pointerEvents="none">
            <View style={s.mira} />
            <Text style={s.dica}>
              {resolver.pending ? 'Consultando...' : 'Aponte para o QR do carregador'}
            </Text>
          </View>
        </View>
      )}

      <View style={s.painel}>
        {erro && <Aviso mensagem={erro.detail} />}
        {naoReconhecido && !erro && (
          <Aviso
            tom="info"
            mensagem={`Este QR não é de um ponto ChargeGrid ("${naoReconhecido}"). Aponte para o adesivo do carregador.`}
          />
        )}

        {digitando ? (
          <>
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
            {!cameraIndisponivel && (
              <Pressable onPress={() => setDigitando(false)} accessibilityRole="button">
                <Text style={s.alternar}>Voltar para a câmera</Text>
              </Pressable>
            )}
          </>
        ) : (
          <Pressable onPress={() => setDigitando(true)} accessibilityRole="button">
            <Text style={s.alternar}>
              QR danificado? Digitar o código
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  visor: {
    flex: 1,
    margin: espaco.md,
    borderRadius: raio.lg,
    overflow: 'hidden',
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center'
  },
  visorVazio: {
    backgroundColor: cores.superficie,
    borderWidth: 1,
    borderColor: cores.borda,
    borderStyle: 'dashed',
    padding: espaco.lg,
    gap: espaco.md
  },
  visorTitulo: { color: cores.texto, fontSize: 17, fontWeight: '700' },
  visorTexto: { color: cores.textoFraco, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  sobreposicao: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
    gap: espaco.lg,
    elevation: 8,
    zIndex: 8
  },
  mira: {
    width: 220,
    height: 220,
    borderWidth: 3,
    borderColor: cores.acento,
    borderRadius: raio.lg
  },
  dica: {
    color: '#FFF',
    fontSize: 13,
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: espaco.md,
    paddingVertical: 6,
    borderRadius: 999,
    overflow: 'hidden'
  },
  painel: { padding: espaco.md, gap: espaco.sm },
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
