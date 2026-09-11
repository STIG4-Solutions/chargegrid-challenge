import { useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import {
  app,
  brl,
  num,
  useAction,
  useApi,
  type ApiError,
  type ExtratoDaCarteira,
  type Veiculo
} from '@chargegrid/sdk'
import { Aviso, Botao, Carregando, Tela } from '../components'
import { useAuth } from '../auth'
import { API_URL } from '../api'
import { cores, espaco, raio } from '../theme'

const VALORES = [20, 50, 100]

// Tipados aqui porque as rotas devolvem `Record<string, unknown>`: elas nao
// tem schema Pydantic nomeado, e o SDK reflete isso. Mesmo padrao de FleetScreen.
interface Plano {
  codigo: string
  nome: string
  preco_mensal_brl: number
  desconto_pct: number
  kwh_inclusos: number
  isenta_taxa_de_conexao: boolean
}

interface Assinatura {
  assinante: boolean
  renova?: boolean
  estado?: string
  plano: Plano
  kwh_restantes: number | null
  periodo_ate: string
}

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

  const assinatura = useApi<Assinatura>(() => app.subscription() as unknown as Promise<Assinatura>, [])
  const planos = useApi<Plano[]>(() => app.plans() as unknown as Promise<Plano[]>, [])
  const assinar = useAction((codigo: string) => app.subscribe(codigo), {
    onSuccess: () => {
      void assinatura.refetch({ silent: true })
      void recarregarPerfil()
    }
  })
  const cancelar = useAction(() => app.unsubscribe(), {
    onSuccess: () => void assinatura.refetch({ silent: true })
  })
  const [confirmandoCancelamento, setConfirmandoCancelamento] = useState(false)

  const [valor, setValor] = useState(50)
  const extrato = useApi<ExtratoDaCarteira>(() => app.walletStatement(20), [])
  const recarregar = useAction((quanto: number) => app.topUpWallet(quanto), {
    onSuccess: () => {
      void recarregarPerfil()
      // O extrato tambem mudou: sem isto o saldo no topo sobe e a lista abaixo
      // continua mostrando o movimento anterior como o ultimo.
      void extrato.refetch({ silent: true })
    }
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

        {/*
          O extrato. Ate aqui o motorista so' via o saldo - e com o cashback das
          campanhas ele passou a mudar sozinho. Um numero que muda sem
          explicacao vira chamado de suporte, ou desconfianca.
        */}
        {extrato.data && extrato.data.movimentos.length > 0 && (
          <View style={s.extrato}>
            <Text style={s.extratoTitulo}>Últimos movimentos</Text>
            {extrato.data.movimentos.map((m) => (
              <View key={m.id} style={s.movimento}>
                <View style={s.movimentoTexto}>
                  <Text style={s.movimentoRotulo} numberOfLines={1}>
                    {m.rotulo}
                  </Text>
                  <Text style={s.movimentoData}>
                    {new Date(m.data).toLocaleDateString('pt-BR')}
                  </Text>
                </View>
                {/* O sinal e' a informacao: verde entra, vermelho sai. */}
                <Text style={[s.movimentoValor, m.valor < 0 ? s.saida : s.entrada]}>
                  {m.valor < 0 ? '−' : '+'}
                  {brl(Math.abs(m.valor))}
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>

      <View style={s.bloco}>
        <Text style={s.blocoTitulo}>Plano de recarga</Text>
        {assinatura.data?.assinante ? (
          <>
            <Text style={s.planoNome}>{assinatura.data.plano.nome}</Text>
            <Text style={s.planoLinha}>
              {assinatura.data.plano.desconto_pct > 0
                ? `${assinatura.data.plano.desconto_pct}% de desconto em toda recarga`
                : 'sem desconto percentual'}
              {assinatura.data.plano.kwh_inclusos > 0 &&
                ` · ${assinatura.data.plano.kwh_inclusos} kWh inclusos por mês`}
            </Text>
            {assinatura.data.kwh_restantes != null && (
              <Text style={s.planoLinha}>
                Restam {assinatura.data.kwh_restantes.toFixed(1)} kWh da franquia deste mês.
              </Text>
            )}
            {/* Cancelada dentro do mês pago ainda dá desconto. Dizer só
                "cancelada" faria o motorista achar que perdeu o que pagou. */}
            <Text style={s.planoLinha}>
              {assinatura.data.renova
                ? `Renova em ${assinatura.data.periodo_ate}.`
                : `Cancelado — o benefício vale até ${assinatura.data.periodo_ate}.`}
            </Text>
            {assinatura.data.renova &&
              (confirmandoCancelamento ? (
                <View style={s.confirmacao}>
                  <Text style={s.planoLinha}>
                    Cancelar a renovação? O plano continua valendo até{' '}
                    {assinatura.data.periodo_ate}.
                  </Text>
                  <View style={s.linhaDeBotoes}>
                    <Botao
                      titulo="Sim, cancelar"
                      variante="secundario"
                      pending={cancelar.pending}
                      onPress={() => void cancelar.run()}
                      style={s.meioBotao}
                    />
                    <Botao
                      titulo="Manter"
                      onPress={() => setConfirmandoCancelamento(false)}
                      style={s.meioBotao}
                    />
                  </View>
                </View>
              ) : (
                <Botao
                  titulo="Cancelar renovação"
                  variante="secundario"
                  onPress={() => setConfirmandoCancelamento(true)}
                />
              ))}
          </>
        ) : (
          <>
            <Text style={s.planoLinha}>
              Assine e economize em toda recarga. A mensalidade sai da sua carteira.
            </Text>
            {(planos.data ?? []).map((plano) => (
              <View key={plano.codigo} style={s.cartaoDoPlano}>
                <Text style={s.planoNome}>{plano.nome}</Text>
                <Text style={s.planoLinha}>
                  {brl(plano.preco_mensal_brl)}/mês
                  {plano.desconto_pct > 0 && ` · ${plano.desconto_pct}% de desconto`}
                  {plano.kwh_inclusos > 0 && ` · ${plano.kwh_inclusos} kWh inclusos`}
                  {plano.isenta_taxa_de_conexao && ' · sem taxa de conexão'}
                </Text>
                <Botao
                  titulo={`Assinar ${plano.nome}`}
                  pending={assinar.pending}
                  onPress={() => void assinar.run(plano.codigo)}
                />
              </View>
            ))}
            {(planos.data ?? []).length === 0 && (
              <Text style={s.planoLinha}>Nenhum plano disponível no momento.</Text>
            )}
          </>
        )}
        {assinar.error && <Aviso mensagem={assinar.error.detail} />}
        {cancelar.error && <Aviso mensagem={cancelar.error.detail} />}
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
  planoNome: { color: cores.texto, fontSize: 15, fontWeight: '600', marginTop: espaco.sm },
  planoLinha: { color: cores.textoFraco, fontSize: 13, marginTop: 2, lineHeight: 18 },
  cartaoDoPlano: {
    marginTop: espaco.sm,
    padding: espaco.sm,
    borderRadius: raio.sm,
    borderWidth: 1,
    borderColor: cores.borda,
    gap: espaco.xs
  },
  confirmacao: { marginTop: espaco.sm, gap: espaco.sm },
  linhaDeBotoes: { flexDirection: 'row', gap: espaco.sm },
  meioBotao: { flex: 1 },
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
  extrato: { gap: espaco.xs, marginTop: espaco.sm },
  extratoTitulo: { color: cores.textoFraco, fontSize: 11, fontWeight: '700', letterSpacing: 0.6 },
  movimento: { flexDirection: 'row', alignItems: 'center', gap: espaco.sm },
  movimentoTexto: { flex: 1 },
  movimentoRotulo: { color: cores.texto, fontSize: 13 },
  movimentoData: { color: cores.textoFraco, fontSize: 11 },
  movimentoValor: { fontSize: 13, fontWeight: '700', fontVariant: ['tabular-nums'] },
  entrada: { color: cores.verde },
  saida: { color: cores.texto },
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
