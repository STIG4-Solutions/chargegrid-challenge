/**
 * Regras puras do formulário de campanha.
 *
 * Vivem fora do componente pelo mesmo motivo de `orcamento.js`: são a parte que
 * decide o que vai para o servidor, e componente com hook não roda em Node.
 * Assim `npm run verify:dashboard` as exercita sem DOM, sem React e sem
 * dependência nova.
 *
 * O que elas protegem é o dinheiro do estabelecimento. Uma campanha mal formada
 * ou é recusada pelo servidor com uma mensagem que ninguém entende, ou — pior —
 * é aceita e passa a gastar orçamento de um jeito que quem a criou não previu.
 */

/** Tipos de benefício que dependem de missão cumprida. */
export function ehCashback(tipo) {
  return typeof tipo === 'string' && tipo.startsWith('cashback')
}

/**
 * O que impede esta campanha de ser salva.
 *
 * Devolve uma lista de mensagens em português, vazia quando está tudo certo.
 * Espelha as validações do servidor de propósito: o servidor continua sendo a
 * autoridade, mas descobrir o erro depois de preencher trinta campos e clicar
 * em salvar é uma experiência diferente de descobrir enquanto se digita.
 */
export function problemasDaCampanha(rascunho) {
  const erros = []
  const nome = (rascunho.nome ?? '').trim()
  if (!nome) erros.push('Dê um nome à campanha.')

  const inicio = rascunho.starts_at ? new Date(rascunho.starts_at) : null
  const fim = rascunho.ends_at ? new Date(rascunho.ends_at) : null
  if (!inicio || Number.isNaN(inicio.getTime())) erros.push('Informe a data de início.')
  if (!fim || Number.isNaN(fim.getTime())) erros.push('Informe a data de término.')
  if (inicio && fim && !Number.isNaN(inicio.getTime()) && !Number.isNaN(fim.getTime())) {
    if (fim <= inicio) erros.push('O término precisa ser depois do início.')
  }

  const valor = Number(rascunho.beneficio_valor ?? 0)
  if (!(valor > 0)) erros.push('O benefício precisa ser maior que zero.')
  if (rascunho.beneficio_tipo?.endsWith('_pct') && valor > 100) {
    erros.push('Um percentual não pode passar de 100%.')
  }

  const orcamento = Number(rascunho.orcamento_brl ?? 0)
  const teto = rascunho.teto_por_recompensa == null ? null : Number(rascunho.teto_por_recompensa)
  if (orcamento < 0) erros.push('O orçamento não pode ser negativo.')
  if (teto != null && teto > 0 && orcamento > 0 && teto > orcamento) {
    erros.push('O teto por recompensa não pode passar do orçamento.')
  }

  const missoes = rascunho.missoes ?? []
  // Missão só faz sentido com cashback: desconto age na própria fatura, na hora.
  // As duas juntas produzem uma campanha cujas missões nunca premiam ninguém.
  if (ehCashback(rascunho.beneficio_tipo) && missoes.length === 0) {
    erros.push('Cashback exige pelo menos uma missão — é ela que o motorista cumpre.')
  }
  if (!ehCashback(rascunho.beneficio_tipo) && missoes.length > 0) {
    erros.push('Desconto é aplicado direto na fatura; missões não se aplicam.')
  }

  const codigos = missoes.map((m) => (m.codigo ?? '').trim()).filter(Boolean)
  if (codigos.length !== missoes.length) erros.push('Toda missão precisa de um código.')
  if (new Set(codigos).size !== codigos.length) erros.push('Há missões com o mesmo código.')
  if (missoes.some((m) => !(Number(m.alvo ?? 0) > 0))) {
    erros.push('O alvo de cada missão precisa ser maior que zero.')
  }

  return erros
}

/**
 * Quanto do orçamento já foi comprometido, de 0 a 100.
 *
 * Sem orçamento definido devolve 0, e não 100: campanha sem teto é campanha sem
 * teto, não campanha esgotada — pintar a barra cheia diria o oposto do que é.
 */
export function consumoDoOrcamento(campanha) {
  const orcamento = Number(campanha?.orcamento_brl ?? 0)
  const consumido = Number(campanha?.consumido_brl ?? 0)
  if (!(orcamento > 0)) return 0
  return Math.max(0, Math.min(100, (consumido / orcamento) * 100))
}

/**
 * Em que fase da vida a campanha está, para o rótulo da tela.
 *
 * `ativa` é intenção; o período é fato. Uma campanha marcada ativa cujo prazo
 * passou não age mais sobre nenhuma recarga, e mostrá-la como "ativa" faria o
 * operador esperar um efeito que não vem.
 */
export function situacaoDaCampanha(campanha, agora = new Date()) {
  if (!campanha?.ativa) return 'encerrada'
  const inicio = new Date(campanha.starts_at)
  const fim = new Date(campanha.ends_at)
  if (agora < inicio) return 'agendada'
  if (agora > fim) return 'expirada'
  return 'vigente'
}

/**
 * Só os campos que este operador tocou.
 *
 * Mesmo contrato de `alteracoesDoOrcamento`, e pelo mesmo motivo: enviar o
 * rascunho inteiro reverteria em silêncio o que outra pessoa mudou nesse
 * meio-tempo. Aqui isso vale dinheiro — o orçamento é editável.
 */
export function alteracoesDaCampanha(rascunho, base, chaves) {
  const mudou = (a, b) => {
    if (typeof a === 'boolean' || typeof b === 'boolean') return a !== b
    if (a == null && b == null) return false
    if (typeof a === 'string' || typeof b === 'string') {
      const na = Number(a)
      const nb = Number(b)
      if (Number.isNaN(na) || Number.isNaN(nb)) return String(a ?? '') !== String(b ?? '')
      return na !== nb
    }
    return Number(a ?? 0) !== Number(b ?? 0)
  }
  return Object.fromEntries(
    chaves.filter((campo) => mudou(rascunho[campo], base[campo])).map((campo) => [campo, rascunho[campo]])
  )
}
