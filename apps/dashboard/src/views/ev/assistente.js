// Logica do widget do assistente, sem React: o reducer da conversa, o
// Markdown que a resposta usa e as sugestoes por aba. Fica em modulo puro para
// o verify:dashboard cobrir sem navegador - e' aqui que mora o que decide o
// que o operador le.

// ------------------------------------------------------------------ conversa

export function estadoInicial() {
  return { conversaId: null, mensagens: [], enviando: false, aviso: null }
}

let sequencia = 0
const idLocal = () => `local-${++sequencia}`

// Atualiza a ULTIMA mensagem do assistente - a que esta sendo gerada.
function naResposta(estado, mudar) {
  const mensagens = [...estado.mensagens]
  for (let i = mensagens.length - 1; i >= 0; i--) {
    if (mensagens[i].papel === 'assistant') {
      mensagens[i] = { ...mensagens[i], ...mudar(mensagens[i]) }
      break
    }
  }
  return { ...estado, mensagens }
}

/**
 * Um reducer so' para duas origens: as acoes da tela e os eventos do fluxo.
 *
 * Os eventos chegam do SDK com a mesma forma `{ tipo, ... }` das acoes, entao
 * a tela despacha o que recebe sem traduzir. Evento desconhecido nao muda
 * nada: um servidor mais novo pode mandar um tipo que este painel nao conhece.
 */
export function reduzir(estado, acao) {
  switch (acao.tipo) {
    case 'enviar':
      return {
        ...estado,
        enviando: true,
        aviso: null,
        mensagens: [
          ...estado.mensagens,
          { id: idLocal(), papel: 'user', texto: acao.texto, estado: 'pronta' },
          { id: idLocal(), papel: 'assistant', texto: '', estado: 'gerando', consulta: null }
        ]
      }
    case 'conversa':
      return { ...estado, conversaId: acao.id }
    case 'meta':
      return { ...estado, conversaId: acao.conversa_id }
    case 'delta':
      return naResposta(estado, (m) => ({ texto: m.texto + acao.texto }))
    case 'ferramenta':
      return naResposta(estado, () => ({
        consulta: acao.estado === 'inicio' ? acao.rotulo : null
      }))
    case 'bloqueado':
      // O texto parcial e' justamente o que foi barrado: some, e fica o aviso.
      return {
        ...naResposta(estado, () => ({
          texto: acao.mensagem,
          estado: 'bloqueada',
          consulta: null
        })),
        enviando: false
      }
    case 'erro':
      return {
        ...naResposta(estado, (m) => ({
          texto: m.texto ? `${m.texto}\n\n${acao.mensagem}` : acao.mensagem,
          estado: 'erro',
          consulta: null
        })),
        enviando: false
      }
    case 'fim':
      return {
        ...naResposta(estado, () => ({ id: acao.mensagem_id, estado: 'pronta', consulta: null })),
        enviando: false
      }
    case 'parado':
      return {
        ...naResposta(estado, (m) => ({
          estado: 'interrompida',
          consulta: null,
          texto: m.texto || 'Resposta interrompida.'
        })),
        enviando: false
      }
    case 'falhou': {
      // Erro ANTES do fluxo abrir (429, 422, 409...). A pergunta nao foi
      // respondida - e, no 409, a conversa pertence a outra praca: a proxima
      // pergunta precisa abrir uma nova.
      const trocouDePraca = acao.status === 409
      const base = naResposta(estado, () => ({
        texto: acao.mensagem,
        estado: 'erro',
        consulta: null
      }))
      return {
        ...base,
        enviando: false,
        conversaId: trocouDePraca ? null : base.conversaId,
        aviso: trocouDePraca ? 'A praça mudou. A próxima pergunta abre uma conversa nova.' : null
      }
    }
    case 'carregar':
      return {
        ...estadoInicial(),
        conversaId: acao.id,
        mensagens: acao.mensagens.map((m) => ({
          id: m.id,
          papel: m.papel,
          texto: m.conteudo || (m.papel === 'assistant' ? 'Resposta interrompida.' : ''),
          estado: m.bloqueio ? 'bloqueada' : 'pronta',
          consulta: null
        }))
      }
    case 'nova':
      return { ...estadoInicial(), aviso: acao.aviso ?? null }
    default:
      return estado
  }
}

/** Por que a pergunta nao pode ir, ou null. */
export function problemaNaPergunta(texto, limite) {
  const limpo = (texto || '').trim()
  if (!limpo) return 'Escreva uma pergunta.'
  if (limpo.length > limite) return `A pergunta passou do limite de ${limite} caracteres.`
  return null
}

// ---------------------------------------------------------------- sugestoes

const SUGESTOES = {
  '/ev/power': ['Quanto cada ponto pode puxar agora?', 'Por que algum ponto está fora do rateio?'],
  '/ev/sessions': ['Quantas sessões estão ativas e na fila?', 'Como foi a energia de hoje?'],
  '/ev/tariff': [
    'Qual foi a receita líquida dos últimos 30 dias?',
    'Quais são as janelas da tarifa?'
  ],
  '/ev/demand': [
    'Vou estourar a demanda contratada nas próximas horas?',
    'Quanto o rateio poupou de multa no mês?'
  ],
  '/ev/utilization': ['Qual ponto se paga e qual fica ocioso?'],
  '/ev/priority': ['Quem tem prioridade às 23h?'],
  '/ev/campaigns': ['Como estão as campanhas ativas?'],
  '/ev/contract': ['Tenho cobrança em atraso com a plataforma?']
}

const GERAIS = [
  'Como está a praça agora?',
  'Algum ponto precisa de manutenção?',
  'Qual a previsão de energia do próximo mês?'
]

/** Ate' tres perguntas, as da aba aberta primeiro. */
export function sugestoesDaAba(aba) {
  const daAba = SUGESTOES[aba] ?? []
  return [...new Set([...daAba, ...GERAIS])].slice(0, 3)
}

// ----------------------------------------------------------------- markdown
//
// Subconjunto do que o modelo escreve: paragrafo, titulo, lista, tabela,
// bloco de codigo, **forte**, *enfase* e `codigo`. Sai uma arvore de dados, e
// nao HTML: a tela monta elementos React a partir dela, entao nenhum texto da
// resposta vira marcacao - um "<img onerror>" na resposta aparece como texto.

/** Texto de uma linha -> partes { t: 'texto' | 'forte' | 'enfase' | 'codigo', v }. */
export function partesEmLinha(texto) {
  const partes = []
  // `_enfase_` so' entre nao-letras: sem isso `valor_total_kw` viraria
  // "valor" + *total* + "kw", e nome de campo aparece em resposta de operacao.
  const padrao =
    /(`[^`]+`|\*\*[^*]+\*\*|(?<![\w])__[^_]+__(?![\w])|\*[^*\s][^*]*\*|(?<![\w])_[^_\s][^_]*_(?![\w]))/g
  let ultimo = 0
  for (const m of texto.matchAll(padrao)) {
    if (m.index > ultimo) partes.push({ t: 'texto', v: texto.slice(ultimo, m.index) })
    const bruto = m[0]
    if (bruto.startsWith('`')) partes.push({ t: 'codigo', v: bruto.slice(1, -1) })
    else if (bruto.startsWith('**') || bruto.startsWith('__'))
      partes.push({ t: 'forte', v: bruto.slice(2, -2) })
    else partes.push({ t: 'enfase', v: bruto.slice(1, -1) })
    ultimo = m.index + bruto.length
  }
  if (ultimo < texto.length) partes.push({ t: 'texto', v: texto.slice(ultimo) })
  return partes
}

const celulas = (linha) =>
  linha
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => partesEmLinha(c.trim()))

const ehSeparadorDeTabela = (linha) =>
  /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(linha)

/** Texto Markdown -> blocos. Tolera texto pela metade (a resposta chega aos pedacos). */
export function blocosMarkdown(texto) {
  const linhas = (texto || '').replace(/\r\n?/g, '\n').split('\n')
  const blocos = []
  let paragrafo = []

  const fecharParagrafo = () => {
    if (paragrafo.length) blocos.push({ tipo: 'p', linhas: paragrafo.map(partesEmLinha) })
    paragrafo = []
  }

  for (let i = 0; i < linhas.length; i++) {
    const linha = linhas[i]

    if (/^\s*```/.test(linha)) {
      fecharParagrafo()
      const codigo = []
      i++
      while (i < linhas.length && !/^\s*```/.test(linhas[i])) codigo.push(linhas[i++])
      blocos.push({ tipo: 'codigo', texto: codigo.join('\n') })
      continue
    }

    const titulo = /^(#{1,4})\s+(.*)$/.exec(linha)
    if (titulo) {
      fecharParagrafo()
      blocos.push({ tipo: 'titulo', nivel: titulo[1].length, partes: partesEmLinha(titulo[2]) })
      continue
    }

    if (linha.includes('|') && i + 1 < linhas.length && ehSeparadorDeTabela(linhas[i + 1])) {
      fecharParagrafo()
      const cabecalho = celulas(linha)
      const corpo = []
      i += 2
      while (i < linhas.length && linhas[i].includes('|') && linhas[i].trim()) {
        corpo.push(celulas(linhas[i++]))
      }
      i--
      blocos.push({ tipo: 'tabela', cabecalho, linhas: corpo })
      continue
    }

    const item = /^\s*([-*•]|\d+[.)])\s+(.*)$/.exec(linha)
    if (item) {
      fecharParagrafo()
      const ordenada = /\d/.test(item[1])
      const anterior = blocos[blocos.length - 1]
      const tipo = ordenada ? 'ol' : 'ul'
      if (anterior?.tipo === tipo) anterior.itens.push(partesEmLinha(item[2]))
      else blocos.push({ tipo, itens: [partesEmLinha(item[2])] })
      continue
    }

    if (!linha.trim()) {
      fecharParagrafo()
      continue
    }
    paragrafo.push(linha)
  }
  fecharParagrafo()
  return blocos
}
