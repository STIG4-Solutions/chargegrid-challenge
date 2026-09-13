/**
 * Regras puras da fila de reportes.
 *
 * Vivem fora do componente pelo mesmo motivo de `campanha.js` e `orcamento.js`:
 * são a parte que decide **o que vai para o servidor** e **o que o operador
 * lê**, e componente com hook não roda em Node. Assim `npm run verify:dashboard`
 * as exercita sem DOM.
 */

/**
 * O que cada categoria quer dizer em português.
 *
 * O backend guarda `cabo_danificado` porque lista fechada agrega — três pessoas
 * descrevendo o mesmo cabo com palavras diferentes viram um problema, não três.
 * Mas `cabo_danificado` na tela é nome de coluna, e imprimir nome de coluna num
 * painel operacional é o mesmo defeito que os `ROTULOS` do recibo corrigiram.
 */
export const CATEGORIAS = {
  nao_inicia: 'Não inicia a recarga',
  conector_travado: 'Conector travado',
  cabo_danificado: 'Cabo danificado',
  tela_apagada: 'Tela apagada',
  vaga_ocupada: 'Vaga ocupada',
  qr_ilegivel: 'QR ilegível',
  outro: 'Outro'
}

/**
 * Categoria traduzida, com o valor cru como último recurso.
 *
 * A API pode ganhar uma categoria antes do painel. Cair aqui apagaria a linha
 * inteira — e é justamente a linha nova, a que ninguém viu ainda, que mais
 * interessa aparecer.
 */
export function rotuloDaCategoria(categoria) {
  return CATEGORIAS[categoria] ?? categoria ?? '—'
}

/** Piso do campo no servidor (`ResolucaoIn.resolucao`, min_length=3). */
export const RESOLUCAO_MINIMA = 3

/**
 * O que impede este reporte de ser fechado.
 *
 * Espelha a validação do servidor de propósito: ele continua sendo a
 * autoridade, mas descobrir o erro depois de clicar é uma experiência
 * diferente de descobrir enquanto se digita.
 *
 * "ok" não explica nada ao próximo motorista que reportar o mesmo cabo, nem ao
 * relatório de manutenção — por isso o piso não é apenas "não vazio".
 */
export function problemaNaResolucao(texto) {
  const limpo = (texto ?? '').trim()
  if (!limpo) return 'Descreva o que foi feito.'
  if (limpo.length < RESOLUCAO_MINIMA) return `Pelo menos ${RESOLUCAO_MINIMA} caracteres.`
  return null
}

/**
 * Há quantos dias o reporte está aberto.
 *
 * Serve para ordenar a atenção do operador: um cabo reportado hoje e um
 * reportado há três semanas exigem coisas diferentes, e a data crua obriga cada
 * um a fazer essa conta de cabeça.
 */
export function diasEmAberto(reportadoEm, agora = new Date()) {
  const quando = new Date(reportadoEm)
  if (Number.isNaN(quando.getTime())) return null
  const dias = Math.floor((agora - quando) / 86400000)
  return dias < 0 ? 0 : dias
}

/** "hoje", "ontem", "há N dias" — o que se diria em voz alta. */
export function idadeEmPalavras(reportadoEm, agora = new Date()) {
  const dias = diasEmAberto(reportadoEm, agora)
  if (dias === null) return ''
  if (dias === 0) return 'hoje'
  if (dias === 1) return 'ontem'
  return `há ${dias} dias`
}
