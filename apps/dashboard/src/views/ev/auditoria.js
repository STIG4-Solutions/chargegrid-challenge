/**
 * Regras puras da trilha de auditoria.
 *
 * Fora do componente pelo mesmo motivo de `manutencao.js` e `campanha.js`: é o
 * que decide **o que o operador lê**, e componente com hook não roda em Node.
 */

/**
 * O que cada ação quer dizer.
 *
 * O servidor guarda `carteira.ajustada` — legível para quem escreveu o código,
 * nome de evento para quem está auditando. Mesma razão dos `ROTULOS` do recibo
 * e das categorias de reporte.
 */
export const ACOES = {
  'carteira.ajustada': 'Saldo corrigido à mão',
  'fatura.estornada': 'Fatura estornada',
  'cobranca_da_plataforma.baixada': 'Cobrança da plataforma baixada',
  'contrato.criado': 'Plano da plataforma contratado',
  'contrato.rescindido': 'Plano da plataforma rescindido',
  'campanha.criada': 'Campanha criada',
  'campanha.encerrada': 'Campanha encerrada',
  'metodo_de_pagamento.alterado': 'Método de pagamento alterado'
}

/** Ação traduzida, com o valor cru como último recurso. */
export function rotuloDaAcao(acao) {
  return ACOES[acao] ?? acao ?? '—'
}

/**
 * As mudanças de uma linha, em pares legíveis.
 *
 * `antes` e `depois` são JSON livre — cada ação guarda o que faz sentido para
 * ela. Em vez de imprimir o objeto, casa as chaves dos dois lados: o que
 * interessa a quem audita é o que **mudou**, não o retrato de cada lado.
 *
 * Chave que só existe num dos lados também aparece: criar uma campanha não tem
 * "antes", e é exatamente isso que a linha deve mostrar.
 */
export function mudancas(antes, depois) {
  const a = antes ?? {}
  const d = depois ?? {}
  return [...new Set([...Object.keys(a), ...Object.keys(d)])]
    .map((campo) => ({ campo, de: a[campo], para: d[campo] }))
    .filter(({ de, para }) => JSON.stringify(de) !== JSON.stringify(para))
}

/**
 * Um valor do JSON como texto.
 *
 * `***` chega assim do servidor e passa direto — mascarar de novo esconderia
 * que houve mascaramento, e quem audita precisa ver que ali existia um segredo.
 */
export function comoTexto(valor) {
  if (valor === null || valor === undefined) return '—'
  if (typeof valor === 'object') return JSON.stringify(valor)
  return String(valor)
}

/**
 * Quem enxerga o quê na navegação e nos botões de dinheiro.
 *
 * Aqui e não dentro do componente porque é decisão, não desenho — e decisão de
 * visibilidade que ninguém consegue exercitar é a que passa despercebida. Foi o
 * caso: o teste de mutação abriu a aba de auditoria e o botão de estorno para
 * operador sem quebrar nada, porque nada os olhava.
 *
 * A tela esconder não é a segurança: o servidor recusa as duas para operador.
 * Esconder evita um botão que promete o que a API não faz — e "estornar" é a
 * última coisa que deveria parecer disponível por engano.
 */
export function abasDaSecao(modulos, { rede, isAdmin }) {
  return [
    ...modulos,
    ...(rede ? [{ to: '/ev/portfolio', label: 'Visão de Rede' }] : []),
    ...(isAdmin
      ? [
          { to: '/ev/users', label: 'Contas' },
          { to: '/ev/audit', label: 'Auditoria' }
        ]
      : [])
  ]
}

/**
 * Dá para estornar esta fatura?
 *
 * Só admin, e só fatura paga. Estornar uma fatura em aberto devolveria dinheiro
 * que nunca entrou; estornar como operador seria devolver do caixa da rede.
 */
export function podeEstornar(invoice, isAdmin) {
  return Boolean(isAdmin) && invoice?.status === 'paid'
}
