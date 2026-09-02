/**
 * O que vem dentro do QR colado no carregador.
 *
 * Tres formatos precisam funcionar, porque nao controlamos quem gerou o
 * adesivo e o parque de carregadores vai ser misto:
 *
 *   CP-01                          codigo puro
 *   chargegrid://cp/CP-01          deeplink do app
 *   https://stig4-solutions.com/cp/CP-01  URL, que tambem abre no navegador
 *
 * A URL e' o formato recomendado: quem nao tem o app instalado cai numa
 * pagina em vez de num texto sem sentido.
 */

import { SITE_URL } from './api'

/** Formato dos codigos de ponto: duas a seis letras, hifen, digitos. */
const CODIGO = /^[A-Z]{2,6}-\d{1,6}$/i

export function codigoDoQr(conteudo: string): string | null {
  const texto = conteudo.trim()
  if (!texto) return null

  // Codigo puro.
  if (CODIGO.test(texto)) return texto.toUpperCase()

  // URL ou deeplink: o codigo e' o ultimo segmento do caminho.
  try {
    const semEsquema = texto.replace(/^[a-z][a-z0-9+.-]*:\/\//i, '')
    const caminho = semEsquema.split('?')[0].split('#')[0]
    const partes = caminho.split('/').filter(Boolean)
    const ultimo = partes[partes.length - 1]
    if (ultimo && CODIGO.test(ultimo)) return ultimo.toUpperCase()
  } catch {
    // Conteudo que nao parece URL: cai no retorno abaixo.
  }

  return null
}

/** O que gerar no adesivo de um ponto. Usado pelo painel ao imprimir o QR. */
/**
 * Conteudo a imprimir no adesivo.
 *
 * A base vem de `SITE_URL`, que sai de config/dominios.json - o mesmo arquivo
 * que define o endereco da API. Deixa-la fixa aqui faria o adesivo apontar
 * para um dominio antigo depois de qualquer troca.
 *
 * Sem base, devolve o CODIGO PURO - um dos tres formatos aceitos. E' melhor
 * que montar `/cp/CP-01`: aquilo ainda seria lido pelo app, mas nao abriria no
 * navegador, que e' a unica razao de preferir a URL ao codigo. E o adesivo ja
 * estaria impresso quando alguem notasse.
 */
export const conteudoDoQr = (codigo: string, base = SITE_URL) =>
  base ? `${base}/cp/${codigo.toUpperCase()}` : codigo.toUpperCase()
