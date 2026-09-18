/**
 * Regras puras da aba de Analytics.
 *
 * O que estas funções decidem é **o que o gráfico afirma**. Uma série desenhada
 * sem cuidado afirma coisas que o dado não sustenta, e a tela fica convincente
 * justamente quando está errada.
 *
 * Ficam aqui, fora do `.jsx`, porque são decisão e não desenho — mesma divisão
 * de `previsao.js` e `contrato.js`, e pelo mesmo motivo: o que decide número na
 * tela precisa ser exercitável sem montar componente.
 */

/**
 * A tendência entre a primeira e a segunda metade da janela.
 *
 * É a leitura executiva que o total esconde: dois meses com a mesma receita são
 * negócios diferentes se um sobe e o outro cai.
 *
 * Divide ao meio em vez de comparar com o período anterior porque só há UMA
 * janela na mão — pedir a anterior dobraria a chamada para responder à mesma
 * pergunta. Com menos de quatro dias devolve `null`: duas amostras de um dia
 * cada não são tendência, são ruído, e uma seta para cima sobre ruído é pior
 * que seta nenhuma.
 */
export function tendencia(serie, campo) {
  if (!Array.isArray(serie) || serie.length < 4) return null
  const meio = Math.floor(serie.length / 2)
  const soma = (lista) => lista.reduce((t, d) => t + Number(d?.[campo] ?? 0), 0)
  const antes = soma(serie.slice(0, meio))
  const depois = soma(serie.slice(meio))
  if (!(antes > 0)) return null
  return ((depois - antes) / antes) * 100
}

/**
 * O topo do eixo Y.
 *
 * Nunca zero: com série toda zerada, dividir por ela produz `Infinity` e as
 * barras somem ou estouram o desenho. O `1` é um teto arbitrário para uma
 * série vazia — e como todos os valores são zero, o resultado é um gráfico
 * chapado no fundo, que é a verdade daquele dado.
 */
export function topoDaEscala(serie, campos) {
  const chaves = Array.isArray(campos) ? campos : [campos]
  let topo = 0
  for (const dia of serie ?? []) {
    for (const chave of chaves) {
      const valor = Number(dia?.[chave] ?? 0)
      if (Number.isFinite(valor) && valor > topo) topo = valor
    }
  }
  return topo > 0 ? topo : 1
}

/**
 * Quantos rótulos cabem no eixo X sem virar borrão.
 *
 * Trinta datas lado a lado num card viram uma faixa cinza ilegível. Mostra-se
 * uma a cada N, com N crescendo com o tamanho da série, e o ÚLTIMO dia sempre
 * entra: é o que a pessoa procura primeiro.
 */
export function rotulosDoEixo(serie, quantos = 6) {
  const total = serie?.length ?? 0
  if (total === 0) return []
  const passo = Math.max(1, Math.ceil(total / quantos))
  const indices = new Set()
  for (let i = 0; i < total; i += passo) indices.add(i)
  indices.add(total - 1)
  return [...indices].sort((a, b) => a - b)
}

/**
 * A fatia de cada ponto no total, para a barra empilhada.
 *
 * Percentual e não valor absoluto porque a pergunta é de concentração: um ponto
 * que responde por 60% da receita é um risco de operação, independentemente de
 * quanto isso é em reais.
 */
export function participacao(pontos, campo = 'receita_brl') {
  const lista = Array.isArray(pontos) ? pontos : []
  const total = lista.reduce((t, p) => t + Number(p?.[campo] ?? 0), 0)
  if (!(total > 0)) return []
  return lista
    .map((p) => ({
      code: p.code,
      valor: Number(p?.[campo] ?? 0),
      pct: (Number(p?.[campo] ?? 0) / total) * 100
    }))
    .sort((a, b) => b.valor - a.valor)
}

/**
 * Formatação de dinheiro e energia, num lugar só.
 *
 * Espalhar `toLocaleString` pelos componentes é como as mesmas grandezas
 * acabam com casas decimais diferentes em cards vizinhos — e aí o leitor
 * acha que são medidas diferentes.
 */
export function comoReais(valor) {
  const n = Number(valor ?? 0)
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function comoKwh(valor) {
  const n = Number(valor ?? 0)
  return `${n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} kWh`
}

/**
 * O dia no formato curto do eixo, no fuso do próprio dado.
 *
 * `new Date('2026-09-18')` é interpretado como UTC e, em fuso negativo, volta
 * um dia — o eixo inteiro sairia deslocado. O `T12:00:00` evita isso sem
 * depender de biblioteca de fuso no navegador.
 */
export function diaCurto(iso) {
  if (!iso) return ''
  return new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit'
  })
}
