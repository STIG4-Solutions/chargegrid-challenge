import { useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { app, brl, num, useAction, useApi, type ApiError, type Veiculo } from '@chargegrid/sdk'
import { Aviso, Botao, Carregando, Tela } from '../components'
import { useAuth } from '../auth'
import { API_URL } from '../api'
import { cores, espaco, raio } from '../theme'

const VALORES = [20, 50, 100]

export default function ProfileScreen() {
  const { user, logout, recarregarPerfil } = useAuth()
  const veiculos = useApi<Veiculo[]>(() => app.myVehicles(), [])
  const [confirmando, setConfirmando] = useState<string | null>(null)
  const remover = useAction((id: string) => app.removeVehicle(id), {
    onSuccess: () => {
      setConfirmando(null)
      void veiculos.refetch({ silent: true })
    }
  })

  const [valor, setValor] = useState(50)
  const recarregar = useAction((quanto: number) => app.topUpWallet(quanto), {
    onSuccess: () => void recarregarPerfil()
  })

  const [modelo, setModelo] = useState('')
  const [placa, setPlaca] = useState('')
  const [bateria, setBateria] = useState('')
  const adicionar = useAction(
    () =>
      app.addVehicle({
        model: modelo.trim(),
        plate: placa.trim() || null,
        battery_kwh: bateria ? Number(bateria.replace(',', '.')) : null
      }),
    {
      onSuccess: () => {
        setModelo('')
        setPlaca('')
        setBateria('')
        void veiculos.refetch({ silent: true })
      }
    }
  )

  if (veiculos.loading && !veiculos.data) return <Carregando rotulo="Carregando perfil..." />

  return (
    <Tela>
      <ScrollView contentContainerStyle={s.conteudo}>
      <View style={s.identidade}>
        <Text style={s.nome}>{user?.full_name ?? 'Motorista'}</Text>
        <Text style={s.email}>{user?.email}</Text>
      </View>

      <View style={s.bloco}>
        <Text style={s.blocoTitulo}>Carteira</Text>
        <Text style={s.saldo}>{brl(user?.wallet_balance ?? 0)}</Text>
        <Text style={s.nota}>
          Saldo pré-pago usado nas recargas. Na integração real o crédito só entra depois que o
          provedor de pagamento confirma.
        </Text>
        <View style={s.chips}>
          {VALORES.map((v) => (
            <Botao
              key={v}
              titulo={brl(v)}
              variante={v === valor ? 'primario' : 'secundario'}
              onPress={() => setValor(v)}
              style={s.chip}
            />
          ))}
        </View>
        {recarregar.error && <Aviso mensagem={recarregar.error.detail} />}
        <Botao
          titulo={`Adicionar ${brl(valor)}`}
          pending={recarregar.pending}
          onPress={() => void recarregar.run(valor)}
        />
      </View>

      <View style={s.bloco}>
        <Text style={s.blocoTitulo}>Meus veículos</Text>
        {(veiculos.data ?? []).length === 0 && (
          <Text style={s.nota}>Nenhum veículo cadastrado.</Text>
        )}
        {(veiculos.data ?? []).map((v) => (
          <View key={v.id} style={s.veiculo}>
            <View style={s.veiculoTexto}>
              <Text style={s.veiculoModelo}>{v.model}</Text>
              <Text style={s.veiculoMeta}>
                {v.plate ? `${v.plate} · ` : ''}
                {v.battery_kwh ? `${num(v.battery_kwh, 0)} kWh` : 'bateria não informada'}
                {v.max_ac_kw ? ` · até ${num(v.max_ac_kw, 1)} kW AC` : ''}
              </Text>
            </View>
            {/* Duas etapas em vez de um alerta do sistema: um modal nativo trava
                a ponte e a sessao de automacao para com ele. */}
            <Pressable
              onPress={() => (confirmando === v.id ? remover.run(v.id) : setConfirmando(v.id))}
              disabled={remover.pending}
              accessibilityRole="button"
              hitSlop={8}
            >
              <Text style={confirmando === v.id ? s.removerConfirma : s.remover}>
                {confirmando === v.id ? 'Confirmar' : 'Remover'}
              </Text>
            </Pressable>
          </View>
        ))}
        {remover.error && <Aviso mensagem={(remover.error as ApiError).detail} />}

        <Text style={[s.blocoTitulo, s.subtitulo]}>Adicionar veículo</Text>
        <TextInput
          style={s.input}
          value={modelo}
          onChangeText={setModelo}
          placeholder="Modelo (ex.: Nissan Leaf)"
          placeholderTextColor={cores.textoFraco}
        />
        <View style={s.linha}>
          <TextInput
            style={[s.input, s.meio]}
            value={placa}
            onChangeText={setPlaca}
            autoCapitalize="characters"
            placeholder="Placa"
            placeholderTextColor={cores.textoFraco}
          />
          <TextInput
            style={[s.input, s.meio]}
            value={bateria}
            onChangeText={setBateria}
            keyboardType="numeric"
            placeholder="Bateria (kWh)"
            placeholderTextColor={cores.textoFraco}
          />
        </View>
        {adicionar.error && <Aviso mensagem={adicionar.error.detail} />}
        <Botao
          titulo="Adicionar"
          variante="secundario"
          disabled={modelo.trim().length === 0}
          pending={adicionar.pending}
          onPress={() => void adicionar.run()}
        />
      </View>

      <View style={s.bloco}>
        <Text style={s.nota}>API: {API_URL}</Text>
        <Botao titulo="Sair" variante="secundario" onPress={() => void logout()} />
      </View>
      </ScrollView>
    </Tela>
  )
}

const s = StyleSheet.create({
  tela: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: espaco.md, gap: espaco.md, paddingBottom: espaco.xl },
  identidade: { gap: 2 },
  nome: { color: cores.texto, fontSize: 22, fontWeight: '800' },
  email: { color: cores.textoFraco, fontSize: 13 },
  bloco: {
    backgroundColor: cores.superficie,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.md,
    padding: espaco.md,
    gap: espaco.sm
  },
  blocoTitulo: { color: cores.texto, fontSize: 15, fontWeight: '700' },
  subtitulo: { marginTop: espaco.sm },
  saldo: { color: cores.texto, fontSize: 32, fontWeight: '800', letterSpacing: -0.5 },
  nota: { color: cores.textoFraco, fontSize: 11, lineHeight: 15 },
  chips: { flexDirection: 'row', gap: espaco.sm },
  chip: { flex: 1, paddingHorizontal: espaco.sm },
  veiculo: {
    borderTopWidth: 1,
    borderTopColor: cores.borda,
    paddingTop: espaco.sm,
    gap: 2
  },
  veiculoTexto: { flex: 1 },
  veiculoModelo: { color: cores.texto, fontSize: 15, fontWeight: '600' },
  remover: { color: cores.textoFraco, fontSize: 13 },
  removerConfirma: { color: cores.acento, fontSize: 13, fontWeight: '700' },
  veiculoMeta: { color: cores.textoFraco, fontSize: 12 },
  input: {
    backgroundColor: cores.superficieAlta,
    borderColor: cores.borda,
    borderWidth: 1,
    borderRadius: raio.sm,
    color: cores.texto,
    fontSize: 15,
    paddingHorizontal: espaco.md,
    paddingVertical: 12
  },
  linha: { flexDirection: 'row', gap: espaco.sm },
  meio: { flex: 1 }
})
