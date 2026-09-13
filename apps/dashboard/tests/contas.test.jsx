/**
 * A tela de contas de operação.
 *
 * `verify-dashboard.mjs` cobre `contas.js` — validação do formulário, corpo do
 * POST, quem pode ser desligado. Aquilo pode estar todo certo e a tela ainda
 * errar: oferecer o botão de desligar a própria conta, ou mostrar "—" na praça
 * de um admin, que enxerga a rede inteira e não está com dado faltando.
 */

import { render, screen } from '@testing-library/react'
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
    render(
      <Linhas contas={[{ ...OPERADOR, is_active: false }]} meuId="outro" aoMudar={() => {}} />
    )
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
    render(
      <Linhas contas={[{ ...OPERADOR, role: 'auditor' }]} meuId="outro" aoMudar={() => {}} />
    )
    expect(screen.getByText('maria@empresa.com')).toBeInTheDocument()
    expect(screen.getByText('auditor')).toBeInTheDocument()
  })
})

describe('o formulário de nova conta', () => {
  const SITES = [{ id: 's1', name: 'Shopping Morumbi' }]

  it('começa fechado, com só o botão de abrir', () => {
    render(<NovaConta sites={SITES} aoCriar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Nova conta' })).toBeInTheDocument()
    expect(screen.queryByText('Papel')).not.toBeInTheDocument()
  })
})
