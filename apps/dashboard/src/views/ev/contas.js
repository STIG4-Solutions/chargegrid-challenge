/**
 * Regras puras da tela de contas.
 *
 * Fora do componente pelo mesmo motivo de `campanha.js` e `contrato.js`: é a
 * parte que decide **o que vai para o servidor**, e componente com hook não
 * roda em Node. Assim `npm run verify:dashboard` as exercita sem navegador.
 */

/** Pisos do servidor, em `ContaNovaIn`. Espelhados, não inventados. */
export const NOME_MINIMO = 2
export const SENHA_MINIMA = 8

export const PAPEIS = {
  operator: 'Operador',
  admin: 'Administrador'
}

/**
 * O papel em português, com o valor cru como último recurso.
 *
 * A API pode ganhar um papel antes do painel. Cair aqui apagaria a linha
 * inteira — e é justamente a linha nova que mais interessa aparecer.
 */
export function rotuloDoPapel(papel) {
  return PAPEIS[papel] ?? papel ?? '—'
}

export const CONTA_VAZIA = {
  nome: '',
  email: '',
  senha: '',
  papel: 'operator',
  siteId: ''
}

/** E-mail plausível. Quem decide de verdade é o `EmailStr` do servidor. */
export function emailPlausivel(texto) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((texto ?? '').trim())
}

/**
 * O que impede a conta de ser criada. `null` quando pode.
 *
 * **Operador sem praça é recusado aqui e no servidor**, e não é validação de
 * formulário: `get_scoped_site_id` devolve o *primeiro site cadastrado* para
 * quem não tem `site_id`. Um operador criado sem praça não ficaria sem acesso —
 * ficaria com acesso à praça de outra pessoa, sem nada na tela dele indicando
 * isso. É a regra menos óbvia desta tela e a mais cara de errar.
 */
export function problemaNaConta(campos) {
  if ((campos.nome ?? '').trim().length < NOME_MINIMO) return 'Escreva o nome completo.'
  if (!emailPlausivel(campos.email)) return 'Confira o e-mail.'
  if ((campos.senha ?? '').length < SENHA_MINIMA) {
    return `A senha inicial precisa de pelo menos ${SENHA_MINIMA} caracteres.`
  }
  if (campos.papel === 'operator' && !campos.siteId) {
    return 'Operador precisa de uma praça: sem ela, o acesso cai na primeira da rede.'
  }
  return null
}

/**
 * O corpo do POST.
 *
 * `site_id` vira `null` para admin mesmo que o formulário tenha um selecionado:
 * admin é global, e mandar a praça faria parecer que ele está restrito a ela —
 * ali o campo é só a praça que abre por padrão.
 */
export function corpoDaConta(campos) {
  return {
    full_name: campos.nome.trim(),
    email: campos.email.trim().toLowerCase(),
    password: campos.senha,
    role: campos.papel,
    site_id: campos.papel === 'operator' ? campos.siteId : null
  }
}

/**
 * Dá para desligar esta conta?
 *
 * O servidor recusa desligar a própria conta com 409. Espelhar aqui não é
 * desconfiança dele: é a diferença entre o botão nascer apagado e a pessoa
 * descobrir depois do clique.
 */
export function podeDesligar(conta, meuId) {
  return Boolean(conta?.is_active) && conta?.id !== meuId
}

/**
 * Como a linha se descreve quando não tem praça.
 *
 * Admin sem praça é o normal — ele enxerga a rede inteira. Escrever "—" ali
 * sugeriria dado faltando, e alguém iria "corrigir".
 */
export function pracaDaConta(conta) {
  if (conta?.site_nome) return conta.site_nome
  return conta?.role === 'admin' ? 'toda a rede' : '—'
}

/** "nunca entrou" é a informação que esta tela existe para dar. */
export function ultimoAcesso(iso) {
  if (!iso) return 'nunca entrou'
  const quando = new Date(iso)
  if (Number.isNaN(quando.getTime())) return 'nunca entrou'
  return quando.toLocaleDateString('pt-BR')
}
