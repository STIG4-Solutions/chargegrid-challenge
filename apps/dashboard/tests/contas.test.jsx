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
import { describe, expect, it } from 'vitest'
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
})
