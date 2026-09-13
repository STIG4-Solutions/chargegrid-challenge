/**
 * Regras puras do cadastro.
 *
 * Fora do componente pelo mesmo motivo de `veiculo.ts` e `frota.ts`: é a parte
 * que decide **o que vai para o servidor**, e componente com hook não roda em
 * Node. Assim `npm run verify:mobile` as exercita sem simulador.
 */
import type { RegistroPublico } from '@chargegrid/sdk'

/** Pisos do servidor, em `RegistroPublicoIn`. Espelhados, não inventados. */
export const NOME_MINIMO = 2
export const SENHA_MINIMA = 8

export interface CamposDoCadastro {
  nome: string
  email: string
  senha: string
  telefone: string
  documento: string
}

export const CADASTRO_VAZIO: CamposDoCadastro = {
  nome: '',
  email: '',
  senha: '',
  telefone: '',
  documento: ''
}

/**
 * E-mail plausível — não validação de RFC.
 *
 * O servidor tem `EmailStr` e é ele quem decide. Aqui a pergunta é outra:
 * evitar que a pessoa toque em "Criar conta", espere a viagem de rede e receba
 * um 422 por ter esquecido o `@`. Ser mais rígido que o servidor seria pior que
 * ser mais frouxo: recusaria endereço que ele aceitaria.
 */
export function emailPlausivel(texto: string): boolean {
  const limpo = texto.trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(limpo)
}

/**
 * O que impede o cadastro de ser enviado. `null` quando pode.
 *
 * Devolve UMA mensagem — a primeira pendência na ordem em que os campos
 * aparecem na tela. Listar todos os erros de uma vez num formulário de cinco
 * campos vira parede de texto vermelho antes de a pessoa ter digitado o
 * segundo.
 */
export function problemaNoCadastro(campos: CamposDoCadastro): string | null {
  if (campos.nome.trim().length < NOME_MINIMO) return 'Escreva seu nome completo.'
  if (campos.nome.trim().length > 160) return 'Nome muito longo.'
  if (!emailPlausivel(campos.email)) return 'Confira o e-mail.'
  if (campos.senha.length < SENHA_MINIMA) {
    return `A senha precisa de pelo menos ${SENHA_MINIMA} caracteres.`
  }
  return null
}

/**
 * O corpo do POST.
 *
 * `telefone` e `documento` são opcionais no servidor, e vazio vira `null` em
 * vez de string vazia: o banco guarda ausência como NULL, e `''` seria um
 * telefone que existe e não tem dígitos — a mesma decisão tomada na placa do
 * veículo.
 *
 * A senha **não** é aparada. Espaço no meio ou na ponta é escolha de quem
 * digitou, e `trim` aqui faria a conta ser criada com uma senha diferente da
 * que a pessoa acha que escolheu — e o login seguinte falharia sem explicação.
 */
export function corpoDoCadastro(campos: CamposDoCadastro): RegistroPublico {
  const opcional = (v: string) => (v.trim() ? v.trim() : null)
  return {
    email: campos.email.trim().toLowerCase(),
    full_name: campos.nome.trim(),
    password: campos.senha,
    phone: opcional(campos.telefone),
    document: opcional(campos.documento)
  }
}

/**
 * A mensagem que a tela mostra quando o servidor recusa.
 *
 * O 409 é o caso comum e tem saída óbvia — a pessoa já tem conta —, então ele
 * não pode aparecer como erro genérico: quem já se cadastrou antes precisa ser
 * mandado para o login, e não deixado olhando "erro ao criar conta".
 */
export function recadoDoErro(status: number | undefined, detalhe: string | undefined): string {
  if (status === 409) return 'Já existe uma conta com este e-mail. Tente entrar.'
  return detalhe || 'Não foi possível criar a conta. Tente de novo.'
}

/** O 409 é o único que oferece ir para o login em vez de corrigir o formulário. */
export function ofereceEntrar(status: number | undefined): boolean {
  return status === 409
}
