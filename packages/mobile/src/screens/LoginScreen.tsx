import { useState } from 'react'
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native'
import type { ApiError } from '@chargegrid/sdk'
import { useAuth } from '../auth'
import { Aviso, Botao } from '../components'
import { API_URL } from '../api'
import { cores, espaco, raio } from '../theme'

// Atalho opcional de login em desenvolvimento. Sem credencial no codigo: os
// valores vem de EXPO_PUBLIC_DEMO_* e, se nao existirem, o campo abre vazio.
const emailDemo = process.env.EXPO_PUBLIC_DEMO_DRIVER_EMAIL
const senhaDemo = process.env.EXPO_PUBLIC_DEMO_DRIVER_PASSWORD
const DEMO = __DEV__ && emailDemo && senhaDemo ? { email: emailDemo, senha: senhaDemo } : null

export default function LoginScreen() {
  const { login, error: erroDaSessao, limparErro } = useAuth()
  const [email, setEmail] = useState(DEMO?.email ?? '')
  const [senha, setSenha] = useState(DEMO?.senha ?? '')
  const [erro, setErro] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function entrar() {
    setErro(null)
    limparErro()
    setPending(true)
    try {
      await login(email.trim(), senha)
    } catch (err) {
      const falha = err as ApiError
      setErro(falha.detail ?? (err as Error).message ?? 'Nao foi possivel entrar.')
    } finally {
      setPending(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={s.tela}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={s.conteudo} keyboardShouldPersistTaps="handled">
        <View style={s.marca}>
          <Text style={s.logo}>ChargeGrid</Text>
          <Text style={s.subtitulo}>Recarregue onde voce estaciona</Text>
        </View>

        <View style={s.form}>
          <Text style={s.rotulo}>E-mail</Text>
          <TextInput
            style={s.input}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            placeholder="voce@email.com"
            placeholderTextColor={cores.textoFraco}
          />

          <Text style={s.rotulo}>Senha</Text>
          <TextInput
            style={s.input}
            value={senha}
            onChangeText={setSenha}
            secureTextEntry
            textContentType="password"
            placeholder="••••••••"
            placeholderTextColor={cores.textoFraco}
            onSubmitEditing={entrar}
            returnKeyType="go"
          />

          {(erro || erroDaSessao) && <Aviso mensagem={erro ?? erroDaSessao ?? ''} />}

          <Botao titulo="Entrar" onPress={entrar} pending={pending} style={s.entrar} />
        </View>

        <Text style={s.rodape}>API: {API_URL}</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { flexGrow: 1, justifyContent: 'center', padding: espaco.lg, gap: espaco.xl },
  marca: { alignItems: 'center', gap: espaco.xs },
  logo: { color: cores.texto, fontSize: 32, fontWeight: '800', letterSpacing: -0.5 },
  subtitulo: { color: cores.textoFraco, fontSize: 14 },
  form: { gap: espaco.sm },
  rotulo: { color: cores.textoFraco, fontSize: 12, marginTop: espaco.sm },
  input: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    color: cores.texto,
    fontSize: 16,
    paddingHorizontal: espaco.md,
    paddingVertical: 14
  },
  entrar: { marginTop: espaco.md },
  rodape: { color: cores.textoFraco, fontSize: 11, textAlign: 'center' }
})
