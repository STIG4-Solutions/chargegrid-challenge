/**
 * Regras puras da tela de contas.
 *
 * Fora do componente pelo mesmo motivo de `campanha.js` e `contrato.js`: é a
 * parte que decide **o que vai para o servidor**, e componente com hook não
 * roda em Node. Assim `npm run verify:dashboard` as exercita sem navegador.
 */

/** Limites do servidor, em `ContaNovaIn`. Espelhados, não inventados. */
export const NOME_MINIMO = 2
export const NOME_MAXIMO = 160
export const SENHA_MINIMA = 8

export const PAPEIS = {
  operator: 'Operador',
  admin: 'Administrador'
}

/**
 * O que cada papel enxerga, em uma linha.
 *
 * Fica ao lado do seletor porque é a única diferença que importa entre os dois
 * e a que decide a escolha: "Papel: Operador | Administrador" sozinho não diz a
 * ninguém qual dos dois a pessoa que vai trabalhar no caixa precisa ser.
 */
export const ALCANCE_DO_PAPEL = {
  operator: 'Enxerga e opera só a praça escolhida.',
  admin: 'Enxerga a rede inteira e pode criar contas.'
}

export function alcanceDoPapel(papel) {
  return ALCANCE_DO_PAPEL[papel] ?? null
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
  // `operator` por padrão porque é a conta que se cria às dezenas; admin é
  // exceção. Deixar em branco só obrigaria a escolher o óbvio toda vez.
  papel: 'operator',
  siteId: ''
}

/**
 * Rótulo, nome curto e dica de cada campo.
 *
 * Aqui, e não no JSX, por dois motivos. A dica da senha cita o piso do servidor
 * — escrita à mão no componente, continuaria dizendo "8" no dia em que
 * `SENHA_MINIMA` virasse 10, e dica que mente é pior que dica nenhuma. E o
 * resumo do botão ("Ainda falta: e-mail e praça") precisa chamar os campos
 * pelos mesmos nomes dos rótulos, senão a tela nomeia a mesma coisa de dois
 * jeitos na mesma linha.
 *
 * São DICAS FIXAS, e não `placeholder`: placeholder some justamente quando a
 * pessoa começa a digitar, que é quando a regra ainda importa, e leitor de tela
 * costuma anunciá-lo como se fosse valor preenchido.
 */
export const CAMPOS_DA_CONTA = {
  nome: {
    rotulo: 'Nome completo',
    curto: 'nome',
    dica: 'É assim que a pessoa aparece no rastro de auditoria.'
  },
  email: {
    rotulo: 'E-mail de acesso',
    curto: 'e-mail',
    dica: 'É com ele que a pessoa entra no painel.'
  },
  senha: {
    rotulo: 'Senha inicial',
    curto: 'senha',
    // O fato operacional mais caro desta tela: não existe "trocar senha no
    // primeiro acesso" no servidor. Quem cria a conta precisa entregar esta
    // senha à pessoa, e ela vale até alguém trocar de propósito.
    dica: `Mínimo ${SENHA_MINIMA} caracteres. Combine com a pessoa: não há troca no primeiro acesso.`
  },
  papel: {
    rotulo: 'Papel',
    curto: 'papel',
    // A dica do papel é o alcance dele, e ele muda com a escolha.
    dica: null
  },
  siteId: {
    rotulo: 'Praça',
    curto: 'praça',
    dica: 'O estabelecimento onde ficam os carregadores.'
  }
}

/**
 * A ordem em que os campos são cobrados.
 *
 * `papel` não entra: ele nasce preenchido e nunca fica pendente.
 */
export const ORDEM_DOS_CAMPOS = ['nome', 'email', 'senha', 'siteId']

/** E-mail plausível. Quem decide de verdade é o `EmailStr` do servidor. */
export function emailPlausivel(texto) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((texto ?? '').trim())
}

/**
 * O que impede a conta de ser criada, campo a campo. `null` no campo que está
 * bom.
 *
 * Um mapa, e não a primeira pendência, porque uma mensagem por vez faz a pessoa
 * descobrir os problemas em fila: corrige o nome e aparece o e-mail, corrige o
 * e-mail e aparece a senha. Pior, a mensagem única fica solta abaixo da linha e
 * não diz a QUAL dos cinco campos ela se refere.
 *
 * **Operador sem praça é recusado aqui e no servidor**, e não é validação de
 * formulário: `get_scoped_site_id` devolve o *primeiro site cadastrado* para
 * quem não tem `site_id`. Um operador criado sem praça não ficaria sem acesso —
 * ficaria com acesso à praça de outra pessoa, sem nada na tela dele indicando
 * isso. É a regra menos óbvia desta tela e a mais cara de errar.
 */
export function problemasDaConta(campos) {
  const nome = (campos?.nome ?? '').trim()
  const senha = campos?.senha ?? ''

  let problemaNoNome = null
  if (nome.length < NOME_MINIMO) problemaNoNome = 'Escreva o nome completo.'
  // O teto também é do servidor. Sem ele aqui, o nome comprido só é recusado
  // depois do POST, com um 422 que fala de `full_name` e não de "Nome".
  else if (nome.length > NOME_MAXIMO) problemaNoNome = `No máximo ${NOME_MAXIMO} caracteres.`

  return {
    nome: problemaNoNome,
    email: emailPlausivel(campos?.email) ? null : 'Confira o e-mail: falta o @ ou o domínio.',
    senha:
      senha.length < SENHA_MINIMA
        ? `A senha inicial precisa de pelo menos ${SENHA_MINIMA} caracteres.`
        : null,
    siteId:
      campos?.papel === 'operator' && !campos?.siteId
        ? 'Escolha a praça: sem ela, o acesso cai na primeira da rede.'
        : null
  }
}

/**
 * A primeira pendência do formulário. `null` quando pode criar.
 *
 * Continua existindo porque é o jeito mais curto de perguntar "dá para enviar?"
 * — e porque derivá-la do mapa garante que as duas respostas nunca divirjam.
 */
export function problemaNaConta(campos) {
  const problemas = problemasDaConta(campos)
  for (const chave of ORDEM_DOS_CAMPOS) {
    if (problemas[chave]) return problemas[chave]
  }
  return null
}

/**
 * Por que o botão está apagado, numa frase. `null` quando ele está aceso.
 *
 * Botão desabilitado sem motivo visível é beco sem saída: a pessoa clica, nada
 * acontece, e ela não tem como saber se falta preencher algo ou se a tela
 * quebrou. Este resumo fica ao lado dele e lista TODAS as pendências de uma vez
 * — inclusive as dos campos em que ela ainda não mexeu, que é justamente o que
 * a mensagem por campo (que só aparece depois do primeiro contato) não mostra.
 *
 * "Ainda falta" e não "Falta preencher" porque a pendência nem sempre é campo
 * vazio: e-mail com erro de digitação está preenchido e continua pendente.
 */
export function resumoDoQueFalta(campos) {
  const problemas = problemasDaConta(campos)
  const pendentes = ORDEM_DOS_CAMPOS.filter((chave) => problemas[chave]).map(
    (chave) => CAMPOS_DA_CONTA[chave].curto
  )
  if (!pendentes.length) return null
  if (pendentes.length === 1) return `Ainda falta: ${pendentes[0]}.`
  return `Ainda falta: ${pendentes.slice(0, -1).join(', ')} e ${pendentes[pendentes.length - 1]}.`
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
 * A recusa do servidor em linguagem de quem administra a rede.
 *
 * O `detail` cru descreve o que o servidor achou, não o que a pessoa faz a
 * respeito. O 409 é o caso comum desta tela e o único que ela resolve sozinha:
 * e-mail repetido quase sempre é conta que já existe e foi DESLIGADA, e está na
 * lista logo abaixo a um clique de religar — criar outra no lugar deixaria duas
 * contas para a mesma pessoa, uma delas com o rastro de auditoria antigo preso.
 *
 * O 404 ganha texto próprio porque tem ação clara e ela não é "tente de novo":
 * a praça sumiu do banco desde que a página carregou, e tentar outra vez daria
 * o mesmo erro — só recarregar renova a lista.
 *
 * O 422 NÃO é traduzido de propósito. O único 422 previsível desta rota é
 * operador sem praça, e esse o formulário já barra; o que sobra são recusas de
 * campo que o servidor descreve melhor do que qualquer texto escrito aqui às
 * cegas. Inventar uma frase genérica no lugar do `detail` esconderia a única
 * pista de um caso que, se chegar, é bug do formulário.
 */
export function mensagemDoErro(erro) {
  if (!erro) return null
  if (erro.status === 409) {
    return 'Já existe uma conta com este e-mail. Procure por ele na lista abaixo: se estiver desligada, religar devolve o acesso sem duplicar a pessoa.'
  }
  if (erro.status === 404) {
    return 'A praça escolhida não existe mais. Recarregue a página para atualizar a lista de praças.'
  }
  return erro.detail || 'Não deu para criar a conta agora.'
}

/**
 * O que dizer depois de criar.
 *
 * Hoje o formulário fecha e a lista recarrega — e recarregar uma lista de vinte
 * linhas não é aviso de sucesso nenhum: a linha nova entra em ordem alfabética,
 * no meio, e some do olhar. Pior, a pessoa acabou de definir uma senha que só
 * ela conhece e que ninguém vai pedir para trocar. A confirmação repete o
 * e-mail e lembra disso, que é o que ainda falta fazer fora da tela.
 */
export function mensagemDeSucesso(campos) {
  const corpo = corpoDaConta(campos)
  const papel = rotuloDoPapel(corpo.role).toLowerCase()
  return `Conta de ${papel} criada para ${corpo.full_name}. Entregue o acesso: ${corpo.email} e a senha inicial que você definiu — o sistema não vai pedir troca no primeiro acesso.`
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
