/**
 * Regras puras do contrato com a plataforma.
 *
 * A tela precisa dizer, ANTES de o operador clicar em rescindir, quanto isso vai
 * custar. Descobrir a multa depois da confirmação é a diferença entre uma
 * decisão e uma surpresa — e aqui a surpresa tem valor em reais.
 *
 * As mesmas contas existem no servidor, que continua sendo a autoridade. Estas
 * são para a tela poder mostrar o número enquanto o operador ainda está pensando.
 */

/**
 * Meses inteiros que faltam para o fim do prazo mínimo.
 *
 * NUNCA NEGATIVO, e quem garante é a saída antecipada — não um `Math.max` no
 * fim. Havia um, e o teste de mutação mostrou que era código morto: com a saída
 * antecipada, `meses` nunca chega a ser negativo.
 *
 * Sem a saída antecipada, um contrato vencido daria meses negativos, a multa
 * viraria crédito, e a tela ofereceria dinheiro a quem está saindo.
 */
export function mesesRestantes(hoje, minimoAte) {
  const fim = minimoAte instanceof Date ? minimoAte : new Date(minimoAte)
  const agora = hoje instanceof Date ? hoje : new Date(hoje)
  if (Number.isNaN(fim.getTime()) || Number.isNaN(agora.getTime())) return 0
  if (fim <= agora) return 0

  // Leitores UTC, e não os locais. A API devolve datas no formato `AAAA-MM-DD`,
  // que o JavaScript interpreta como meia-noite UTC; lidas com `getDate()` num
  // fuso a oeste, elas retrocedem um dia — e a conta perdia um mês inteiro de
  // multa. Foi o que o verificador pegou: doze meses viravam onze.
  let meses =
    (fim.getUTCFullYear() - agora.getUTCFullYear()) * 12 + (fim.getUTCMonth() - agora.getUTCMonth())
  if (fim.getUTCDate() < agora.getUTCDate()) meses -= 1
  return meses
}

/**
 * O que se cobra de quem sai antes do prazo.
 *
 * Percentual sobre as mensalidades que faltavam. Cem por cento seria cobrar o
 * contrato inteiro sem prestar o serviço; zero tornaria o prazo mínimo uma frase
 * sem efeito.
 */
export function multaPorRescisao(mensal, restantes, percentual) {
  const valor = Number(mensal ?? 0)
  const meses = Number(restantes ?? 0)
  const pct = Number(percentual ?? 0)
  if (!(meses > 0) || !(pct > 0) || !(valor > 0)) return 0
  return Math.round(valor * meses * pct) / 100
}

/**
 * Quanto do plano já está sendo usado, em pontos.
 *
 * Passar da franquia não é erro — é o gatilho de cobrança por ponto extra, e o
 * operador precisa ver isso chegando antes de aparecer na fatura.
 */
export function pontosExcedentes(pontosDoSite, inclusos) {
  return Math.max(0, Number(pontosDoSite ?? 0) - Number(inclusos ?? 0))
}

/**
 * Estimativa da próxima cobrança, com as três parcelas separadas.
 *
 * Somadas num número só, "R$ 480" não permite conferência. Separadas, o lojista
 * checa cada uma contra o próprio extrato — que é o que ele vai fazer de
 * qualquer jeito, com ou sem a tela ajudando.
 */
export function proximaCobranca(plano, pontosDoSite, faturamentoDoMes) {
  const assinatura = Number(plano?.preco_mensal_brl ?? 0)
  const extras = pontosExcedentes(pontosDoSite, plano?.pontos_inclusos)
  const pontos = extras * Number(plano?.preco_por_ponto_brl ?? 0)
  const transacao =
    (Number(faturamentoDoMes ?? 0) * Number(plano?.fee_percent_transacao ?? 0)) / 100
  const arredonda = (v) => Math.round(v * 100) / 100
  return {
    assinatura: arredonda(assinatura),
    pontos: arredonda(pontos),
    transacao: arredonda(transacao),
    pontos_excedentes: extras,
    total: arredonda(assinatura + pontos + transacao)
  }
}
