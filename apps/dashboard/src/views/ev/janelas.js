/**
 * Regras puras da previsão por janela: hora, dia, semana, mês e ano.
 *
 * O que estas funções decidem é **o que a curva afirma sobre si mesma**. Cinco
 * janelas não vêm da mesma origem, e desenhar as cinco iguais diria ao operador
 * que valem o mesmo — ele contrata demanda por isso.
 *
 * A medição que sustenta a diferença está em `medir_janelas.py`: a folga entre a
 * melhor régua sem modelo e o ruído irredutível é de −0,05 ponto na janela de
 * hora e +3,38 no mês. Onde a folga é zero, nenhum modelo pode ganhar — e o
 * número honesto ali não é um ponto, é uma faixa.
 *
 * Ficam fora do `.jsx` pela mesma razão de `previsao.js` e `analytics.js`: o que
 * decide número na tela precisa ser exercitável sem montar componente.
 */

/** As janelas na ordem do mais fino para o mais grosso, com o que cada uma responde. */
export const JANELAS_DE_PREVISAO = [
  { chave: 'hora', rotulo: 'Hora', pergunta: 'A curva das próximas horas' },
  { chave: 'dia', rotulo: 'Dia', pergunta: 'Quanto por dia, nos próximos' },
  { chave: 'semana', rotulo: 'Semana', pergunta: 'Quanto por semana' },
  { chave: 'mes', rotulo: 'Mês', pergunta: 'Quanto por mês' },
  { chave: 'ano', rotulo: 'Ano', pergunta: 'Quanto por ano' }
]

/**
 * De onde veio o número, em português, e se é modelo.
 *
 * Existe porque `fonte` é a única coisa que separa uma previsão de uma média
 * móvel na tela. Quatro das cinco janelas são servidas por régua — não por falta
 * de modelo, mas porque ali a régua já está no piso do que o dado permite, e
 * apresentar média como previsão é o defeito que esta coluna existe para impedir.
 *
 * Fonte desconhecida não vira "modelo" por omissão: vira o próprio código, e o
 * cartão a trata como não-modelo. Um valor novo no banco tem de aparecer errado
 * na tela em vez de ser promovido a previsão sem ninguém decidir.
 */
export function rotuloDaFonte(fonte) {
  const conhecidas = {
    modelo: { texto: 'modelo de previsão', eModelo: true },
    media_movel: { texto: 'média móvel de 28 dias', eModelo: false },
    media_dow: { texto: 'média por dia da semana', eModelo: false },
    perfil_hora: { texto: 'perfil de hora e dia da semana', eModelo: false },
    tendencia: { texto: 'extrapolação de tendência', eModelo: false }
  }
  if (fonte == null) return { texto: 'origem não declarada', eModelo: false }
  return conhecidas[fonte] ?? { texto: String(fonte), eModelo: false }
}

/**
 * Esta série traz faixa p10–p90?
 *
 * Só quando TODOS os buckets a trazem. Uma faixa que aparece em metade da curva
 * e desaparece na outra metade sugere que a incerteza acabou no meio do caminho —
 * e o que aconteceu foi só falta de dado para estimá-la.
 */
export function temFaixaNaSerie(buckets) {
  const lista = Array.isArray(buckets) ? buckets : []
  if (!lista.length) return false
  return lista.every((b) => b?.kwh_p10 != null && b?.kwh_p90 != null)
}

/**
 * O topo do eixo Y, considerando o p90 quando existe.
 *
 * Escalar pelo previsto faria a faixa superior estourar para fora do desenho, e
 * uma banda cortada na borda mente sobre o quanto o número pode variar.
 *
 * Nunca zero, pelo mesmo motivo de `topoDaEscala`: dividir por zero apaga o
 * gráfico inteiro.
 */
export function topoDaSerie(buckets) {
  let topo = 0
  for (const b of buckets ?? []) {
    for (const chave of ['kwh_previsto', 'kwh_p90']) {
      const valor = Number(b?.[chave] ?? 0)
      if (Number.isFinite(valor) && valor > topo) topo = valor
    }
  }
  return topo > 0 ? topo : 1
}

/**
 * O rótulo de um bucket no eixo, no formato que a janela pede.
 *
 * Cada janela precisa de coisa diferente: a hora sem a hora é inútil, e o ano
 * com dia e mês é ruído. `diaCurto` de `analytics.js` não serve aqui porque
 * resolve só o caso diário — e porque aquele recebe data pura (`2026-09-24`)
 * enquanto estes buckets chegam com fuso.
 *
 * O `fuso` NÃO é opcional por capricho. A resposta carrega o instante em UTC, e
 * sem fuso explícito o navegador o converte para o de quem olha — o que desloca a
 * curva do dia para qualquer pessoa fora do fuso da praça. Uma versão anterior
 * disto usava o relógio do navegador e chamava o deslocamento de "inerente"; o CI
 * provou que não é aceitável, ao rodar em UTC e ver o pico das 17h como 20h. É a
 * curva do dia que dá sentido à janela horária, então o deslocamento não é
 * cosmético: é a feature errada.
 *
 * `timezone` vem da resposta da API, que o declara junto dos buckets.
 */
export function rotuloDoBucket(iso, janela, fuso = 'UTC') {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const formatar = (opcoes) =>
    new Intl.DateTimeFormat('pt-BR', { timeZone: fuso, ...opcoes }).format(d)

  if (janela === 'hora') {
    const dia = formatar({ day: '2-digit', month: '2-digit' })
    // `hour12: false` e não o padrão: em pt-BR o padrão já é 24h, mas o `hourCycle`
    // varia entre motores, e "10h" virando "10 AM" quebraria o eixo em silêncio.
    const hora = formatar({ hour: 'numeric', hour12: false })
    return `${dia} ${hora}h`
  }
  if (janela === 'ano') return formatar({ year: 'numeric' })
  if (janela === 'mes') return formatar({ month: 'short', year: '2-digit' }).replace('.', '')
  const curto = formatar({ day: '2-digit', month: '2-digit' })
  return janela === 'semana' ? `sem ${curto}` : curto
}

/**
 * O total da série, em kWh e em reais.
 *
 * Reais pode não existir: a previsão da REDE é gravada sem faturamento, porque
 * somar praças com tarifas diferentes produziria um preço médio que não existe em
 * contrato nenhum. Devolve `null` nesse caso, e não zero — zero afirmaria que a
 * rede não fatura.
 */
export function totaisDaSerie(buckets) {
  const lista = Array.isArray(buckets) ? buckets : []
  let kwh = 0
  let brl = 0
  let temReais = false
  for (const b of lista) {
    kwh += Number(b?.kwh_previsto ?? 0)
    if (b?.faturamento_previsto_brl != null) {
      brl += Number(b.faturamento_previsto_brl)
      temReais = true
    }
  }
  return { kwh, brl: temReais ? brl : null }
}
