/**
 * A fila de reportes na tela do operador.
 *
 * `verify-dashboard.mjs` cobre `manutencao.js` — tradução da categoria, piso da
 * resolução, idade em palavras. Aquilo pode estar todo certo e a tela ainda
 * deixar fechar um reporte sem dizer o que foi feito, que é justamente o que a
 * API recusa e o que transformaria a fila num botão de sumir com a reclamação.
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { FilaDeReportes } from '../src/views/ev/PowerManagement.jsx'

const REPORTE = {
  id: 'r1',
  charge_point_id: 'cp1',
  ponto: 'CP-01',
  categoria: 'cabo_danificado',
  descricao: 'cabo com fio à mostra',
  reportado_em: new Date().toISOString(),
  reportado_por: 'ana.costa@email.com',
  resolvido: false,
  resolvido_em: null,
  resolvido_por: null,
  resolucao: null
}

const montar = (props = {}) =>
  render(<FilaDeReportes reportes={[REPORTE]} aoResolver={() => {}} {...props} />)

describe('a lista', () => {
  it('mostra o ponto, o problema em português e quem reportou', () => {
    montar()
    expect(screen.getByText('CP-01')).toBeInTheDocument()
    expect(screen.getByText('Cabo danificado')).toBeInTheDocument()
    expect(screen.getByText('cabo com fio à mostra')).toBeInTheDocument()
    expect(screen.getByText('ana.costa@email.com')).toBeInTheDocument()
  })

  it('não imprime o nome da coluna', () => {
    // `cabo_danificado` é o valor do banco. Imprimi-lo é o mesmo defeito que os
    // ROTULOS do recibo corrigiram.
    montar()
    expect(screen.queryByText('cabo_danificado')).not.toBeInTheDocument()
  })

  it('fila vazia diz isso, e explica para que serve', () => {
    const { container } = render(<FilaDeReportes reportes={[]} aoResolver={() => {}} />)
    expect(screen.getByText(/Nenhum reporte em aberto/)).toBeInTheDocument()
    expect(container.querySelector('table')).toBeNull()
  })

  it('conta quantos estão abertos', () => {
    render(
      <FilaDeReportes
        reportes={[REPORTE, { ...REPORTE, id: 'r2' }]}
        aoResolver={() => {}}
      />
    )
    expect(screen.getByText('2')).toBeInTheDocument()
  })
})

describe('fechar um reporte', () => {
  it('exige dizer o que foi feito antes de habilitar o botão', () => {
    montar()
    fireEvent.click(screen.getByRole('button', { name: 'Resolver' }))

    expect(screen.getByRole('button', { name: 'Fechar reporte' })).toBeDisabled()
    expect(screen.getByText('Descreva o que foi feito.')).toBeInTheDocument()
  })

  it('texto curto demais continua barrado', () => {
    // Espelha o `min_length=3` do servidor: descobrir no 422 é a mesma
    // informação chegando tarde.
    montar()
    fireEvent.click(screen.getByRole('button', { name: 'Resolver' }))
    fireEvent.change(screen.getByLabelText('O que foi feito'), { target: { value: 'ok' } })

    expect(screen.getByRole('button', { name: 'Fechar reporte' })).toBeDisabled()
  })

  it('com descrição, fecha e entrega o texto limpo', () => {
    const aoResolver = vi.fn()
    montar({ aoResolver })
    fireEvent.click(screen.getByRole('button', { name: 'Resolver' }))
    fireEvent.change(screen.getByLabelText('O que foi feito'), {
      target: { value: '  Cabo trocado na terça  ' }
    })
    fireEvent.click(screen.getByRole('button', { name: 'Fechar reporte' }))

    expect(aoResolver).toHaveBeenCalledWith('r1', 'Cabo trocado na terça')
  })

  it('o formulário abre só no reporte clicado', () => {
    // Um campo por linha, e não um compartilhado: com o texto vazando entre
    // linhas, o operador fecharia um reporte com a descrição do outro.
    render(
      <FilaDeReportes reportes={[REPORTE, { ...REPORTE, id: 'r2' }]} aoResolver={() => {}} />
    )
    fireEvent.click(screen.getAllByRole('button', { name: 'Resolver' })[0])

    expect(screen.getAllByLabelText('O que foi feito')).toHaveLength(1)
  })

  it('enquanto fecha, o botão diz que está fechando', () => {
    montar({ pendente: true })
    fireEvent.click(screen.getByRole('button', { name: 'Resolver' }))
    expect(screen.getByRole('button', { name: 'Fechando…' })).toBeDisabled()
  })

  it('erro da ação aparece onde quem clicou está olhando', () => {
    montar({ erro: { detail: 'reporte não encontrado' } })
    expect(screen.getByRole('alert')).toHaveTextContent('reporte não encontrado')
  })
})
