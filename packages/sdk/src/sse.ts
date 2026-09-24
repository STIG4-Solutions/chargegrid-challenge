/**
 * Leitura de `text/event-stream` sobre `fetch`.
 *
 * `EventSource` seria o caminho natural e não serve: ele só faz GET, e não
 * aceita cabeçalho — o Bearer teria de ir na URL, que fica em log de proxy.
 *
 * O parser é separado da leitura de rede porque a parte difícil é a borda dos
 * pedaços: a rede entrega bytes onde quiser, e um evento pode chegar partido
 * no meio de uma linha, ou no meio de um caractere acentuado.
 */

export interface EventoSse {
  evento: string
  dados: string
}

/** Devolve uma função que recebe texto e devolve os eventos que se completaram. */
export function criarLeitorSse(): (pedaco: string) => EventoSse[] {
  let pendente = ''

  return (pedaco: string) => {
    pendente += pedaco.replace(/\r\n?/g, '\n')
    const prontos: EventoSse[] = []
    let fim = pendente.indexOf('\n\n')
    while (fim !== -1) {
      const bloco = pendente.slice(0, fim)
      pendente = pendente.slice(fim + 2)
      const evento = interpretar(bloco)
      if (evento) prontos.push(evento)
      fim = pendente.indexOf('\n\n')
    }
    return prontos
  }
}

function interpretar(bloco: string): EventoSse | null {
  let evento = 'message'
  const dados: string[] = []
  for (const linha of bloco.split('\n')) {
    // Linha começando com ':' é comentário (keep-alive), e fica de fora.
    if (!linha || linha.startsWith(':')) continue
    const doisPontos = linha.indexOf(':')
    const campo = doisPontos === -1 ? linha : linha.slice(0, doisPontos)
    let valor = doisPontos === -1 ? '' : linha.slice(doisPontos + 1)
    if (valor.startsWith(' ')) valor = valor.slice(1)
    if (campo === 'event') evento = valor
    else if (campo === 'data') dados.push(valor)
  }
  return dados.length ? { evento, dados: dados.join('\n') } : null
}

/** Eventos de um corpo em fluxo, na ordem em que chegam. */
export async function* lerSse(corpo: ReadableStream<Uint8Array>): AsyncGenerator<EventoSse> {
  const leitor = corpo.getReader()
  // `stream: true` segura o byte que sobrou de um caractere partido até o
  // próximo pedaço, em vez de trocá-lo por '�'.
  const decodificador = new TextDecoder()
  const ler = criarLeitorSse()
  try {
    while (true) {
      const { done, value } = await leitor.read()
      if (done) break
      for (const evento of ler(decodificador.decode(value, { stream: true }))) yield evento
    }
    for (const evento of ler(decodificador.decode() + '\n\n')) yield evento
  } finally {
    // Quem parou de ler no meio (break, return) não quer o resto: cancelar
    // fecha a conexão, e o servidor para de gerar a resposta. Depois do fim
    // normal, cancelar não faz nada.
    leitor.cancel().catch(() => {})
  }
}
