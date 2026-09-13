import { useState } from 'react'
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { cores, espaco, raio } from './theme'

/**
 * Teto opcional da recarga: energia, tempo ou valor.
 *
 * O servidor já para sozinho ao atingir qualquer um deles — a ingestão de
 * telemetria encerra a sessão no primeiro que bater. O que faltava era a tela:
 * o motorista não tinha como pedir "carregue até R$ 50" e ia embora sem saber
 * quanto ia gastar.
 *
 * Um só por vez, de propósito. Combinar tetos é possível no servidor, mas na
 * tela cria a pergunta "qual deles vale?" sem dar a resposta — e a resposta é
 * "o primeiro que chegar", que ninguém consegue prever de antemão.
 */
export type TipoDeLimite = 'nenhum' | 'kwh' | 'minutos' | 'reais'

export interface Limite {
  tipo: TipoDeLimite
  valor: string
}

export const SEM_LIMITE: Limite = { tipo: 'nenhum', valor: '' }

const OPCOES: { tipo: TipoDeLimite; rotulo: string; sufixo: string; exemplo: string }[] = [
  { tipo: 'nenhum', rotulo: 'Sem limite', sufixo: '', exemplo: '' },
  { tipo: 'kwh', rotulo: 'Energia', sufixo: 'kWh', exemplo: '30' },
  { tipo: 'minutos', rotulo: 'Tempo', sufixo: 'min', exemplo: '45' },
  { tipo: 'reais', rotulo: 'Valor', sufixo: 'R$', exemplo: '50' }
]

/** Converte o que o motorista digitou nos parâmetros que a API espera. */
export function comoParametros(limite: Limite): {
  limit_kwh?: number
  limit_minutes?: number
  limit_amount?: number
} {
  const n = Number(limite.valor.replace(',', '.'))
  if (!Number.isFinite(n) || n <= 0) return {}
  if (limite.tipo === 'kwh') return { limit_kwh: n }
  if (limite.tipo === 'minutos') return { limit_minutes: Math.round(n) }
  if (limite.tipo === 'reais') return { limit_amount: n }
  return {}
}

/** Mensagem de erro, ou null se o que está digitado serve. */
export function validar(limite: Limite): string | null {
  if (limite.tipo === 'nenhum') return null
  const bruto = limite.valor.trim()
  if (bruto === '') return 'Informe o valor do limite'
  const n = Number(bruto.replace(',', '.'))
  if (!Number.isFinite(n) || n <= 0) return 'O limite precisa ser maior que zero'
  // O servidor recusa acima de 24 h. Barrar aqui evita a viagem e o 422.
  if (limite.tipo === 'minutos' && n > 24 * 60) return 'O tempo máximo é 24 horas'
  if (limite.tipo === 'kwh' && n > 200) return 'A energia máxima é 200 kWh'
  return null
}

export function LimiteDaRecarga({
  limite,
  onChange
}: {
  limite: Limite
  onChange: (l: Limite) => void
}) {
  const [tocado, setTocado] = useState(false)
  const opcao = OPCOES.find((o) => o.tipo === limite.tipo) ?? OPCOES[0]
  const erro = tocado ? validar(limite) : null

  return (
    <View style={s.bloco}>
      <Text style={s.titulo}>Parar automaticamente em</Text>

      <View style={s.linha}>
        {OPCOES.map((o) => {
          const ativa = o.tipo === limite.tipo
          return (
            <Pressable
              key={o.tipo}
              accessibilityRole="button"
              accessibilityState={{ selected: ativa }}
              onPress={() => {
                setTocado(false)
                onChange({ tipo: o.tipo, valor: o.tipo === 'nenhum' ? '' : limite.valor })
              }}
              style={[s.chip, ativa && s.chipAtivo]}
            >
              <Text style={[s.chipTexto, ativa && s.chipTextoAtivo]}>{o.rotulo}</Text>
            </Pressable>
          )
        })}
      </View>

      {limite.tipo !== 'nenhum' && (
        <View>
          <View style={s.campo}>
            <TextInput
              value={limite.valor}
              onChangeText={(v) => onChange({ ...limite, valor: v })}
              onBlur={() => setTocado(true)}
              placeholder={opcao.exemplo}
              placeholderTextColor={cores.textoFraco}
              keyboardType="decimal-pad"
              style={s.entrada}
              accessibilityLabel={`Limite em ${opcao.rotulo}`}
            />
            <Text style={s.sufixo}>{opcao.sufixo}</Text>
          </View>
          {erro ? (
            <Text style={s.erro}>{erro}</Text>
          ) : (
            <Text style={s.nota}>
              A recarga para sozinha ao atingir. Você pode encerrar antes quando quiser.
            </Text>
          )}
        </View>
      )}
    </View>
  )
}

const s = StyleSheet.create({
  bloco: { gap: espaco.sm },
  titulo: {
    color: cores.textoFraco,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase'
  },
  linha: { flexDirection: 'row', flexWrap: 'wrap', gap: espaco.xs },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: espaco.sm,
    borderRadius: raio.sm,
    borderWidth: 1,
    borderColor: cores.borda,
    backgroundColor: cores.superficieAlta
  },
  chipAtivo: { borderColor: cores.acento, backgroundColor: cores.superficie },
  chipTexto: { color: cores.textoFraco, fontSize: 13, fontWeight: '600' },
  chipTextoAtivo: { color: cores.texto },
  campo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.xs,
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: raio.sm,
    paddingHorizontal: espaco.sm,
    backgroundColor: cores.superficieAlta
  },
  entrada: { flex: 1, color: cores.texto, fontSize: 16, paddingVertical: 10 },
  sufixo: { color: cores.textoFraco, fontSize: 14, fontWeight: '600' },
  nota: { color: cores.textoFraco, fontSize: 12, marginTop: 4 },
  erro: { color: cores.acento, fontSize: 12, marginTop: 4 }
})
