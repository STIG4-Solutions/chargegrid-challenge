/**
 * Regras puras do editor de orçamento.
 *
 * Vivem fora do componente por um motivo prático: são a parte que decide o que
 * vai para o servidor, e componente com hook não roda em Node. Aqui elas
 * recebem objetos e devolvem objetos, então `npm run verify:dashboard` as
 * exercita sem DOM, sem React e sem dependência nova.
 *
 * O que estas funções protegem é a edição concorrente. O editor congela o
 * rascunho no instante em que abre, mas `settings` continua chegando do
 * polling: se outra pessoa mudar um campo nesse meio-tempo, enviar o rascunho
 * inteiro reverte a mudança dela em silêncio — inclusive num campo que quem
 * salvou nunca tocou. Com `reserved_kw` isso derruba a proteção das cargas do
 * prédio, e o site passa a distribuir potência que não tem.
 */

/**
 * Compara dois valores do orçamento.
 *
 * Booleano compara direto; o resto vira número, porque o input devolve string
 * e `'75' !== 75` marcaria como alterado um campo que ninguém tocou — o que
 * traria de volta, por outro caminho, o problema que este módulo resolve.
 */
function mudou(a, b) {
  if (typeof a === 'boolean' || typeof b === 'boolean') return a !== b
  return Number(a ?? 0) !== Number(b ?? 0)
}

/**
 * O que ESTE operador alterou, comparado ao que ele viu ao abrir.
 *
 * É o corpo do PATCH. Campo ausente daqui não viaja, então não sobrescreve.
 */
export function alteracoesDoOrcamento(rascunho, base, chaves) {
  return Object.fromEntries(
    chaves.filter((campo) => mudou(rascunho[campo], base[campo])).map((campo) => [campo, rascunho[campo]])
  )
}

/**
 * Campos que mudaram no servidor desde a abertura e que este operador NÃO
 * tocou.
 *
 * O diff já os preserva; isto existe só para avisar. Quem está com o painel
 * aberto precisa saber que a tela mostrava outro número quando ele começou —
 * senão salva achando que o estado é o que ele leu cinco minutos atrás.
 */
export function mudouPorBaixo(atual, base, chaves, alteracoes) {
  return chaves.filter(
    (campo) => !(campo in alteracoes) && mudou(atual[campo], base[campo])
  )
}
