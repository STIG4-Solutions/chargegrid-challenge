/**
 * A trilha de auditoria na tela.
 *
 * `verify-dashboard.mjs` cobre `auditoria.js` — tradução da ação, diff entre
 * antes e depois, formatação de valor. Aquilo pode estar todo certo e a tabela
 * ainda esconder o que importa: quem fez, ou que ali existia um segredo.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Linhas } from '../src/views/ev/Auditoria.jsx'

const LINHA = {
  id: 'a1',
  quando: '2026-09-12T14:30:00Z',
  quem: 'admin@chargegrid.com.br',
  quem_id: 'u1',
  acao: 'carteira.ajustada',
  entidade: 'user',
  entidade_id: '0123456789abcdef',
  antes: { saldo: 10 },
  depois: { saldo: 25, motivo: 'Cortesia' },
  ip: '203.0.113.7'
}

describe('a tabela', () => {
  it('mostra quem, o que e de onde', () => {
    render(<Linhas linhas={[LINHA]} />)
    expect(screen.getByText('admin@chargegrid.com.br')).toBeInTheDocument()
    expect(screen.getByText('Saldo corrigido à mão')).toBeInTheDocument()
    expect(screen.getByText('203.0.113.7')).toBeInTheDocument()
  })

  it('não imprime o nome do evento', () => {
    render(<Linhas linhas={[LINHA]} />)
    expect(screen.queryByText('carteira.ajustada')).not.toBeInTheDocument()
  })

  it('mostra o que mudou, e não o retrato de cada lado', () => {
    render(<Linhas linhas={[LINHA]} />)
    expect(screen.getByText(/10 → 25/)).toBeInTheDocument()
  })

  it('conta apagada ainda diz que houve alguém', () => {
    // `actor_id` é SET NULL e o e-mail fica gravado junto justamente por isso.
    // Quando nem o e-mail houver, a célula não pode ficar vazia — vazio parece
    // defeito, e "conta removida" é informação.
    render(<Linhas linhas={[{ ...LINHA, quem: null }]} />)
    expect(screen.getByText('conta removida')).toBeInTheDocument()
  })

  it('o segredo mascarado aparece como mascarado', () => {
    // Esconder o `***` esconderia que houve mascaramento. Quem audita precisa
    // ver que ali existia uma credencial.
    render(
      <Linhas
        linhas={[
          {
            ...LINHA,
            acao: 'metodo_de_pagamento.alterado',
            antes: { provider_config: { client_secret: '***' } },
            depois: { provider_config: { client_secret: '***', base_url: 'https://psp' } }
          }
        ]}
      />
    )
    expect(screen.getByText(/\*\*\*/)).toBeInTheDocument()
  })

  it('trilha vazia diz isso', () => {
    render(<Linhas linhas={[]} />)
    expect(screen.getByText(/Nenhuma ação registrada/)).toBeInTheDocument()
  })

  it('ausente não quebra', () => {
    // Painel novo contra API velha, ou a primeira carga.
    render(<Linhas linhas={undefined} />)
    expect(screen.getByText(/Nenhuma ação registrada/)).toBeInTheDocument()
  })
})
