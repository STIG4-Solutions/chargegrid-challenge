/**
 * O seletor de frota do formulário de campanha.
 *
 * `verify-dashboard.mjs` cobre `corpoDaCampanha` — o `''` virando `null` a
 * caminho do servidor. Aquilo pode estar certo e a tela ainda enganar: basta o
 * campo sugerir que escolher uma frota muda quem paga, que é a leitura natural
 * de quem o vê ao lado de "Benefício".
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SeletorDeFrota } from '../src/views/ev/Campaigns.jsx'

const FROTAS = [
  { id: 'f1', nome: 'Logistica SP' },
  { id: 'f2', nome: 'Transportes ABC' }
]

const montar = (props = {}) =>
  render(<SeletorDeFrota frotas={FROTAS} valor="" aoMudar={() => {}} {...props} />)

describe('as opções', () => {
  it('começa em "todos" e lista as frotas', () => {
    montar()
    expect(screen.getByRole('combobox')).toHaveValue('')
    expect(screen.getByRole('option', { name: 'Todos os motoristas' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Frota Logistica SP' })).toBeInTheDocument()
  })

  it('a opção "todos" tem valor vazio', () => {
    // É este vazio que `corpoDaCampanha` converte em `null`. Um `value` que
    // fosse a string "null" ou "todos" chegaria ao servidor como frota
    // inexistente.
    montar()
    expect(screen.getByRole('option', { name: 'Todos os motoristas' })).toHaveValue('')
  })

  it('sem frota nenhuma ainda dá para criar campanha', () => {
    // Uma consulta de frotas que falhou não pode impedir o caso comum. Este
    // teste é o que impede alguém de "melhorar" o componente com um <Async>.
    montar({ frotas: undefined })
    expect(screen.getByRole('option', { name: 'Todos os motoristas' })).toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(1)
  })
})

describe('a nota abaixo do campo', () => {
  it('diz que quem paga NÃO muda ao escolher uma frota', () => {
    // O campo fica ao lado de "Benefício", e patrocínio é justamente o que ele
    // não é. Sem esta frase, a leitura natural é a errada.
    montar({ valor: 'f1' })
    expect(screen.getByText(/Quem paga não muda/)).toBeInTheDocument()
  })

  it('sem frota, diz que não há restrição', () => {
    montar()
    expect(screen.getByText('Sem restrição de frota.')).toBeInTheDocument()
    expect(screen.queryByText(/Quem paga não muda/)).not.toBeInTheDocument()
  })
})
