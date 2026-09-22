/**
 * Regras puras do ajuste manual de saldo.
 *
 * O ajuste é o **único** lançamento do razão em que alguém escolhe o número: não
 * há fatura, recarga nem missão por trás. Por isso a tela exige o mesmo que o
 * servidor exige, e não menos — não para "validar antes" (o servidor recusa de
 * qualquer jeito), mas porque um 422 depois de clicar não diz à pessoa o que
 * fazer, e aqui dá para dizer enquanto ela digita.
 *
 * Os pisos espelham `wallet_service.ajustar`. Se um dos lados mudar, o outro
 * passa a mentir — e o sintoma é um botão habilitado que sempre falha.
 */

/** O que o servidor aceita em `motivo` (`MOTIVO_MAX`, e o CHECK no banco). */
export const MOTIVO_MAXIMO = 200

/**
 * Por que este ajuste não pode ser enviado — ou `null` se pode.
 *
 * Uma razão por vez, e a mais básica primeiro: listar três problemas de um
 * campo que a pessoa ainda nem terminou de preencher é ruído.
 */
export function problemaNoAjuste({ valor, motivo }) {
  const numero = Number(valor)
  if (valor === '' || valor == null || !Number.isFinite(numero)) {
    return 'Informe o valor do ajuste.'
  }
  // Zero é recusado pelo servidor e pelo CHECK `sinal_da_origem`: ajuste de
  // nada não corrige nada, e ainda sujaria o extrato com uma linha sem efeito.
  if (numero === 0) {
    return 'Ajuste de zero não corrige nada.'
  }
  const texto = (motivo ?? '').trim()
  if (!texto) {
    return 'O motivo é obrigatório — é o que explica o dinheiro depois.'
  }
  if (texto.length > MOTIVO_MAXIMO) {
    return `O motivo passa de ${MOTIVO_MAXIMO} caracteres.`
  }
  return null
}

/**
 * O saldo ficaria negativo?
 *
 * A carteira é pré-paga: o servidor recusa o débito que deixaria saldo devedor.
 * Antecipar aqui evita o caso mais provável de erro — tirar mais do que há.
 *
 * Devolve `null` quando o saldo atual é desconhecido: avisar sobre um limite
 * que não se conhece seria inventar.
 */
export function deixariaNegativo({ valor, saldoAtual }) {
  const numero = Number(valor)
  const saldo = Number(saldoAtual)
  if (!Number.isFinite(numero) || !Number.isFinite(saldo)) return null
  return saldo + numero < 0
}

/**
 * O corpo que vai para a API.
 *
 * `valor` como número, não como texto: o SDK o formata com duas casas, e mandar
 * "10,50" (vírgula, do teclado brasileiro) produziria um 422 sobre um valor que
 * a pessoa digitou corretamente.
 */
export function corpoDoAjuste({ valor, motivo }) {
  return { valor: Number(String(valor).replace(',', '.')), motivo: (motivo ?? '').trim() }
}

/**
 * O que dizer depois de dar certo.
 *
 * Nomeia o sentido em palavras, e não só o sinal: "-50" e "+50" diferem por um
 * caractere fácil de não ver, e a frase é a última chance de perceber que o
 * lançamento saiu invertido.
 */
export function mensagemDoAjuste({ valor, saldoNovo }) {
  const numero = Number(valor)
  const sentido = numero < 0 ? 'Debitado' : 'Creditado'
  const quantia = Math.abs(numero).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  })
  const saldo = Number(saldoNovo).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  })
  return `${sentido} ${quantia}. Novo saldo: ${saldo}.`
}
