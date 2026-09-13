import { useState } from 'react'
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native'
import { auth, type ApiError } from '@chargegrid/sdk'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useAuth } from '../auth'
import { Aviso, Botao } from '../components'
import {
  CADASTRO_VAZIO,
  corpoDoCadastro,
  ofereceEntrar,
  problemaNoCadastro,
  recadoDoErro,
  type CamposDoCadastro
} from '../cadastro'
import { cores, espaco, raio } from '../theme'

/**
 * Criar conta pelo app.
 *
 * `POST /auth/register` existia desde sempre, testado por ninguém e sem tela: o
 * app só sabia fazer login, então virar cliente do ChargeGrid exigia que alguém
 * inserisse a conta no banco. Era promessa sem caminho — a mesma classe de
 * defeito de `patrocinador='frota'` e do `pushed_to_hardware`.
 *
 * A rota devolve o USUÁRIO, não um par de tokens. Por isso o cadastro termina
 * com um login automático: parar no 201 deixaria a pessoa cadastrada e de fora
 * ao mesmo tempo, tendo que digitar de novo o que acabou de digitar.
 */
export default function SignUpScreen({ aoVoltar }: { aoVoltar: () => void }) {
  const { login } = useAuth()
  const [campos, setCampos] = useState<CamposDoCadastro>(CADASTRO_VAZIO)
  const [erro, setErro] = useState<string | null>(null)
  const [comConta, setComConta] = useState(false)
  const [pending, setPending] = useState(false)

  const problema = problemaNoCadastro(campos)
  const bordas = useSafeAreaInsets()
  const campo = (chave: keyof CamposDoCadastro) => (texto: string) =>
    setCampos((atual) => ({ ...atual, [chave]: texto }))

  async function criar() {
    setErro(null)
    setComConta(false)
    setPending(true)
    try {
      await auth.register(corpoDoCadastro(campos))
      // Login logo em seguida, com a senha que ainda está em memória. Se ESTE
      // passo falhar a conta já existe, então mandar para o login é a saída
      // certa - repetir o cadastro daria 409.
      await login(campos.email.trim().toLowerCase(), campos.senha)
    } catch (err) {
      const falha = err as ApiError
      setErro(recadoDoErro(falha.status, falha.detail))
      setComConta(ofereceEntrar(falha.status))
    } finally {
      setPending(false)
    }
  }

  return (
    <KeyboardAvoidingView style={s.tela} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={[
          s.conteudo,
          { paddingTop: bordas.top + espaco.lg, paddingBottom: bordas.bottom + espaco.lg }
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <View style={s.marca}>
          <Text style={s.logo}>Criar conta</Text>
          <Text style={s.subtitulo}>Leva um minuto, e a recarga já fica no seu nome.</Text>
        </View>

        <View style={s.form}>
          <Text style={s.rotulo}>Nome completo</Text>
          <TextInput
            style={s.input}
            value={campos.nome}
            onChangeText={campo('nome')}
            autoCapitalize="words"
            textContentType="name"
            placeholder="Maria Souza"
            placeholderTextColor={cores.textoFraco}
          />

          <Text style={s.rotulo}>E-mail</Text>
          <TextInput
            style={s.input}
            value={campos.email}
            onChangeText={campo('email')}
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
            value={campos.senha}
            onChangeText={campo('senha')}
            secureTextEntry
            textContentType="newPassword"
            placeholder="pelo menos 8 caracteres"
            placeholderTextColor={cores.textoFraco}
          />

          <Text style={s.rotulo}>Telefone (opcional)</Text>
          <TextInput
            style={s.input}
            value={campos.telefone}
            onChangeText={campo('telefone')}
            keyboardType="phone-pad"
            textContentType="telephoneNumber"
            placeholder="(11) 99999-0000"
            placeholderTextColor={cores.textoFraco}
          />

          <Text style={s.rotulo}>CPF (opcional)</Text>
          <TextInput
            style={s.input}
            value={campos.documento}
            onChangeText={campo('documento')}
            keyboardType="number-pad"
            placeholder="somente números"
            placeholderTextColor={cores.textoFraco}
          />

          {/*
            A pendência só aparece depois que a pessoa começou a escrever: um
            formulário que abre já reclamando de campo vazio acusa antes de ter
            do que reclamar.
          */}
          {problema && campos.nome.length + campos.email.length + campos.senha.length > 0 && (
            <Text style={s.pendencia}>{problema}</Text>
          )}

          {erro && <Aviso mensagem={erro} />}
          {comConta && (
            <Pressable accessibilityRole="button" onPress={aoVoltar} hitSlop={8}>
              <Text style={s.link}>Ir para o login</Text>
            </Pressable>
          )}

          <Botao
            titulo="Criar conta"
            onPress={criar}
            disabled={Boolean(problema) || pending}
            pending={pending}
            style={s.enviar}
          />

          <Pressable accessibilityRole="button" onPress={aoVoltar} hitSlop={8}>
            <Text style={s.link}>Já tenho conta</Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { flexGrow: 1, justifyContent: 'center', padding: espaco.lg, gap: espaco.lg },
  marca: { alignItems: 'center', gap: espaco.xs },
  logo: { color: cores.texto, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  subtitulo: { color: cores.textoFraco, fontSize: 14, textAlign: 'center' },
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
  pendencia: { color: cores.textoFraco, fontSize: 12 },
  enviar: { marginTop: espaco.md },
  link: { color: cores.acento, fontSize: 14, fontWeight: '600', textAlign: 'center' }
})
