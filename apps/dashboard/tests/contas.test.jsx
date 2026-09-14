/**
 * A tela de contas de operação.
 *
 * `verify-dashboard.mjs` cobre `contas.js` — validação do formulário, corpo do
 * POST, quem pode ser desligado. Aquilo pode estar todo certo e a tela ainda
 * errar: oferecer o botão de desligar a própria conta, ou mostrar "—" na praça
 * de um admin, que enxerga a rede inteira e não está com dado faltando.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Linhas, NovaConta } from '../src/views/ev/Contas.jsx'

const OPERADOR = {
  id: 'u1',
  full_name: 'Maria Souza',
  email: 'maria@empresa.com',
  role: 'operator',
  is_active: true,
  site_id: 's1',
  site_nome: 'Shopping Morumbi',
  last_login_at: '2026-09-01T10:00:00Z'
}

const ADMIN = {
  id: 'u2',
  full_name: 'Ana Admin',
  email: 'ana@goodwe.com',
  role: 'admin',
  is_active: true,
  site_id: null,
  site_nome: null,
  last_login_at: null
}

describe('a tabela de contas', () => {
  it('mostra a praça do operador e a rede do admin', () => {
    // "—" na linha do admin sugeriria dado faltando, e alguém iria "corrigir"
    // atribuindo uma praça — que é justamente o que ele não deve ter.
    render(<Linhas contas={[OPERADOR, ADMIN]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByText('Shopping Morumbi')).toBeInTheDocument()
    expect(screen.getByText('toda a rede')).toBeInTheDocument()
  })

  it('diz quem nunca entrou', () => {
    // É a pergunta que esta tela responde e nenhuma outra: conta criada há
    // meses e nunca usada é acesso aberto sem dono.
    render(<Linhas contas={[ADMIN]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByText('nunca entrou')).toBeInTheDocument()
  })

  it('não oferece desligar a própria conta', () => {
    // O servidor recusa com 409. Aqui o botão nasce apagado, em vez de a pessoa
    // descobrir depois do clique.
    render(<Linhas contas={[OPERADOR]} meuId={OPERADOR.id} aoMudar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Desligar' })).toBeDisabled()
  })

  it('oferece desligar outra conta', () => {
    render(<Linhas contas={[OPERADOR]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Desligar' })).toBeEnabled()
  })

  it('conta desligada oferece religar, e não desligar', () => {
    render(<Linhas contas={[{ ...OPERADOR, is_active: false }]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Religar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Desligar' })).not.toBeInTheDocument()
    expect(screen.getByText('Desligada')).toBeInTheDocument()
  })

  it('lista vazia diz isso em vez de mostrar tabela oca', () => {
    render(<Linhas contas={[]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByText(/Nenhuma conta de operação/)).toBeInTheDocument()
  })

  it('papel desconhecido não apaga a linha', () => {
    // A API pode ganhar um papel antes do painel. Cair aqui derrubaria a
    // tabela inteira por causa de uma linha — justamente a linha nova.
    render(<Linhas contas={[{ ...OPERADOR, role: 'auditor' }]} meuId="outro" aoMudar={() => {}} />)
    expect(screen.getByText('maria@empresa.com')).toBeInTheDocument()
    expect(screen.getByText('auditor')).toBeInTheDocument()
  })
})

describe('o formulário de nova conta', () => {
  // A forma REAL de `GET /power/sites`, copiada da resposta da API — não
  // inventada a partir do componente. A versão anterior deste arquivo usava
  // `{ id, name }`, que era o que o código lia; o servidor devolve `site_id` e
  // `nome`. O teste ficou verde e o seletor renderizava quatro opções vazias,
  // com o formulário travado, porque a praça é obrigatória para operador.
  const SITES = [
    {
      site_id: '6a8aaaad-2964-4b1d-a14e-e437ceb76e17',
      nome: 'Shopping Morumbi - Piso G3',
      cidade: 'Sao Paulo',
      estado: 'SP',
      timezone: 'America/Sao_Paulo'
    },
    {
      site_id: '492bfe4f-5a29-494a-8210-f7e1c87e70e0',
      nome: 'LAB FIAP Eco Station',
      cidade: 'Sao Paulo',
      estado: 'SP',
      timezone: 'America/Sao_Paulo'
    }
  ]

  it('começa fechado, com só o botão de abrir', () => {
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Nova conta' })).toBeInTheDocument()
    expect(screen.queryByText('Papel')).not.toBeInTheDocument()
  })

  it('aberto, o seletor lista as praças pelo nome', async () => {
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))

    expect(screen.getByRole('option', { name: 'Shopping Morumbi - Piso G3' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'LAB FIAP Eco Station' })).toBeInTheDocument()
  })

  it('cada praça carrega o próprio identificador', async () => {
    // Nome certo com valor vazio deixaria a lista bonita e o envio impossível.
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))

    const opcao = screen.getByRole('option', { name: 'Shopping Morumbi - Piso G3' })
    expect(opcao).toHaveValue('6a8aaaad-2964-4b1d-a14e-e437ceb76e17')
  })

  it('sem praça escolhida, criar continua bloqueado', async () => {
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))

    expect(screen.getByRole('button', { name: 'Criar conta' })).toBeDisabled()
  })

  it('admin não precisa de praça, e o seletor some', async () => {
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))
    await usuario.selectOptions(screen.getByLabelText(/Papel/), 'admin')

    expect(screen.queryByRole('option', { name: 'Shopping Morumbi - Piso G3' })).toBeNull()
  })

  it('não pré-seleciona a primeira praça', async () => {
    // Escolher a primeira da lista por conta própria é LITERALMENTE o
    // comportamento de servidor que a obrigatoriedade da praça existe para
    // evitar — e aqui seria pior, porque pareceria escolha de quem cadastrou.
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))

    expect(screen.getByLabelText('Praça')).toHaveValue('')
  })

  it('o campo do admin afirma o alcance em vez de sumir', async () => {
    // Campo que some parece campo que quebrou, e a linha ainda pulava de cinco
    // colunas para quatro no instante da troca. A afirmação ocupa o mesmo lugar
    // e escreve a regra que antes estava só no buraco.
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))
    await usuario.selectOptions(screen.getByLabelText(/Papel/), 'admin')

    // As mesmas palavras que a tabela usa na linha de um admin.
    expect(screen.getByText('toda a rede')).toBeInTheDocument()
    expect(screen.getByText(/não fica preso a uma praça/)).toBeInTheDocument()
  })
})

describe('o formulário conversa antes de recusar', () => {
  const SITES = [
    { site_id: 's1', nome: 'Shopping Morumbi - Piso G3', cidade: 'Sao Paulo', estado: 'SP' }
  ]

  const abrir = async (props = {}) => {
    const usuario = userEvent.setup()
    render(<NovaConta sites={SITES} aoCriar={() => {}} {...props} />)
    await usuario.click(screen.getByRole('button', { name: 'Nova conta' }))
    return usuario
  }

  const preencher = async (usuario) => {
    await usuario.type(screen.getByLabelText('Nome completo'), 'Maria Souza')
    await usuario.type(screen.getByLabelText('E-mail de acesso'), 'Maria@Empresa.COM')
    await usuario.type(screen.getByLabelText('Senha inicial'), 'senha-comprida')
    await usuario.selectOptions(screen.getByLabelText('Praça'), 's1')
  }

  it('não acusa erro em campo que ninguém tocou', async () => {
    // Abrir o formulário e já levar "Escreva o nome completo" é a tela
    // repreendendo alguém que ainda não fez nada.
    await abrir()
    expect(screen.queryByText('Escreva o nome completo.')).toBeNull()
  })

  it('acusa o erro no campo assim que a pessoa sai dele', async () => {
    const usuario = await abrir()
    await usuario.type(screen.getByLabelText('Nome completo'), 'M')
    await usuario.tab()

    expect(screen.getByText('Escreva o nome completo.')).toBeInTheDocument()
    // E só naquele campo: os outros continuam mostrando a dica.
    expect(screen.queryByText(/Confira o e-mail/)).toBeNull()
  })

  it('o botão apagado diz tudo o que ainda falta', async () => {
    // Botão desabilitado sem motivo visível é beco sem saída: clica, nada
    // acontece, e não há como saber se falta algo ou se a tela quebrou.
    await abrir()
    expect(screen.getByRole('button', { name: 'Criar conta' })).toBeDisabled()
    expect(screen.getByText('Ainda falta: nome, e-mail, senha e praça.')).toBeInTheDocument()
  })

  it('a dica da senha avisa que ninguém vai pedir troca no primeiro acesso', async () => {
    // O fato operacional mais caro desta tela: quem cria a conta precisa
    // ENTREGAR esta senha, e ela vale até alguém trocar de propósito.
    await abrir()
    expect(screen.getByText(/não há troca no primeiro acesso/)).toBeInTheDocument()
  })

  it('a senha pode ser revelada para ser ditada', async () => {
    // Esta senha não é de quem digita: é a que ela vai passar para outra
    // pessoa. Digitada às cegas, o erro de digitação só aparece dias depois,
    // como "não consigo entrar", sem saber qual das pontas errou.
    const usuario = await abrir()
    expect(screen.getByLabelText('Senha inicial')).toHaveAttribute('type', 'password')

    await usuario.click(screen.getByRole('button', { name: 'Mostrar a senha inicial' }))
    expect(screen.getByLabelText('Senha inicial')).toHaveAttribute('type', 'text')
  })

  it('o navegador não é convidado a preencher com o login de quem está logado', async () => {
    // E-mail mais senha na mesma linha é a assinatura de um formulário de LOGIN
    // para o navegador. Criar a conta de outra pessoa com as credenciais do
    // próprio admin é um acidente de um clique.
    await abrir()
    expect(screen.getByLabelText('E-mail de acesso')).toHaveAttribute('autocomplete', 'off')
    expect(screen.getByLabelText('Senha inicial')).toHaveAttribute('autocomplete', 'new-password')
  })

  it('todo controle responde pelo próprio rótulo', async () => {
    // `getByLabelText` só encontra o que um leitor de tela também encontraria.
    await abrir()
    for (const rotulo of ['Nome completo', 'E-mail de acesso', 'Senha inicial', 'Papel', 'Praça']) {
      expect(screen.getByLabelText(rotulo)).toBeInTheDocument()
    }
  })

  it('criar envia o corpo certo e confirma na tela', async () => {
    // Fechar o formulário e recarregar a lista não é aviso de sucesso: a linha
    // nova entra em ordem alfabética, no meio, e some do olhar.
    const criarConta = vi.fn().mockResolvedValue({ id: 'u9' })
    const aoCriar = vi.fn()
    const usuario = await abrir({ criarConta, aoCriar })
    await preencher(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Criar conta' }))

    expect(criarConta).toHaveBeenCalledWith({
      full_name: 'Maria Souza',
      email: 'maria@empresa.com',
      password: 'senha-comprida',
      role: 'operator',
      site_id: 's1'
    })
    expect(aoCriar).toHaveBeenCalled()
    expect(await screen.findByText(/maria@empresa.com/)).toBeInTheDocument()
    expect(screen.getByText(/primeiro acesso/)).toBeInTheDocument()
    // E o formulário fecha, como antes.
    expect(screen.queryByLabelText('Nome completo')).toBeNull()
  })

  it('409 vira instrução de procurar a conta desligada na lista', async () => {
    // O `detail` do servidor diz que já existe e para aí. O que a pessoa faz a
    // respeito — religar em vez de criar uma segunda conta para a mesma pessoa,
    // com o rastro de auditoria antigo preso na primeira — é o que falta.
    const criarConta = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error('409'), { status: 409, detail: 'já cadastrado' }))
    const usuario = await abrir({ criarConta })
    await preencher(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Criar conta' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/religar/i)
  })

  it('mexer no e-mail depois do 409 apaga o erro antigo', async () => {
    // O erro fala do que foi ENVIADO. Parado embaixo de um e-mail novo, ele
    // parece recusa do novo.
    const criarConta = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error('409'), { status: 409, detail: 'já cadastrado' }))
    const usuario = await abrir({ criarConta })
    await preencher(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Criar conta' }))
    await screen.findByRole('alert')

    await usuario.type(screen.getByLabelText('E-mail de acesso'), '.br')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
