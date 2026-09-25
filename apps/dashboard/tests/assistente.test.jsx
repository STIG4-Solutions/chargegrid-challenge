/**
 * O widget do assistente: o que o operador lê enquanto a resposta chega.
 *
 * O reducer e o Markdown já são verificados puros no verify:dashboard. Aqui o
 * que se fixa é a tela: o widget some quando a API diz que está desligado, a
 * consulta em andamento aparece com o rótulo da ferramenta, a tabela da
 * resposta vira tabela, e um bloqueio substitui o texto parcial.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Assistente, { Markdown, PainelDoAssistente } from '../src/components/Assistente.jsx'

let mockStatus = { habilitado: true, limite_de_caracteres: 200 }
let mockRoteiro = []
let mockPedidos = []
let liberar = null

vi.mock('@chargegrid/sdk', async (original) => ({
  ...(await original()),
  assistant: {
    status: () => Promise.resolve(mockStatus),
    conversas: () => Promise.resolve([]),
    conversa: () => Promise.reject(new Error('sem conversa')),
    criarConversa: () => Promise.resolve({ id: 'c1' }),
    enviar: async function* (conversaId, texto, opcoes) {
      mockPedidos.push({ conversaId, texto, aba: opcoes.aba })
      for (const evento of mockRoteiro) {
        // `pausa` segura o fluxo até o teste liberar: é como se ver o estado
        // intermediário, com a consulta em andamento.
        if (evento === 'pausa') await new Promise((r) => (liberar = r))
        else yield evento
      }
    }
  }
}))

beforeEach(() => {
  mockStatus = { habilitado: true, limite_de_caracteres: 200 }
  mockRoteiro = []
  mockPedidos = []
  liberar = null
})

const naAba = (ui, aba = '/ev/power') =>
  render(<MemoryRouter initialEntries={[aba]}>{ui}</MemoryRouter>)

describe('Assistente', () => {
  it('não aparece quando a API diz que está desligado', async () => {
    mockStatus = { habilitado: false, limite_de_caracteres: 200 }
    naAba(<Assistente />)
    // Espera o status chegar antes de afirmar a ausência.
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByRole('button', { name: 'Abrir assistente' })).not.toBeInTheDocument()
  })

  it('aparece habilitado e abre com sugestões da aba', async () => {
    const user = userEvent.setup()
    naAba(<Assistente />, '/ev/demand')
    await user.click(await screen.findByRole('button', { name: 'Abrir assistente' }))
    expect(screen.getByRole('region', { name: 'Assistente de operação' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /estourar a demanda contratada/ })
    ).toBeInTheDocument()
  })

  it('mostra a consulta em andamento e depois a resposta com tabela', async () => {
    const user = userEvent.setup()
    mockRoteiro = [
      { tipo: 'meta', conversa_id: 'c1', mensagem_id: 'm1' },
      {
        tipo: 'ferramenta',
        nome: 'potencia_agora',
        rotulo: 'Consultando a potência',
        estado: 'inicio'
      },
      'pausa',
      {
        tipo: 'ferramenta',
        nome: 'potencia_agora',
        rotulo: 'Consultando a potência',
        estado: 'fim',
        ok: true
      },
      { tipo: 'delta', texto: '| Ponto | kW |\n|---|---|\n' },
      { tipo: 'delta', texto: '| CP-01 | 11 |' },
      { tipo: 'fim', mensagem_id: 'm2', tokens_entrada: 1, tokens_saida: 1 }
    ]
    naAba(<PainelDoAssistente limite={200} abertoDeInicio />)

    await user.type(screen.getByLabelText('Pergunta ao assistente'), 'Quanto cada ponto puxa?')
    await user.click(screen.getByRole('button', { name: 'Enviar' }))

    expect(await screen.findByText('Consultando a potência')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Parar' })).toBeInTheDocument()

    liberar()
    expect(await screen.findByRole('cell', { name: 'CP-01' })).toBeInTheDocument()
    expect(screen.queryByText('Consultando a potência')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeInTheDocument()
    expect(mockPedidos).toEqual([
      { conversaId: 'c1', texto: 'Quanto cada ponto puxa?', aba: '/ev/power' }
    ])
  })

  it('bloqueio troca o texto parcial pelo aviso', async () => {
    const user = userEvent.setup()
    mockRoteiro = [
      { tipo: 'delta', texto: 'trecho que o filtro barrou' },
      { tipo: 'bloqueado', motivo: 'saida', mensagem: 'A resposta foi barrada pelas regras.' }
    ]
    naAba(<PainelDoAssistente limite={200} abertoDeInicio />)

    await user.type(screen.getByLabelText('Pergunta ao assistente'), 'x{Enter}')

    expect(await screen.findByText('A resposta foi barrada pelas regras.')).toBeInTheDocument()
    expect(screen.queryByText('trecho que o filtro barrou')).not.toBeInTheDocument()
  })

  it('pergunta acima do limite não pode ser enviada', async () => {
    const user = userEvent.setup()
    naAba(<PainelDoAssistente limite={5} abertoDeInicio />)
    await user.type(screen.getByLabelText('Pergunta ao assistente'), 'longa demais')
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
    expect(screen.getByText('12/5')).toBeInTheDocument()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(mockPedidos).toEqual([]))
  })
})

describe('Markdown da resposta', () => {
  it('HTML da resposta aparece como texto, nunca vira elemento', () => {
    const { container } = render(<Markdown texto={'<img src=x onerror="alert(1)">'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument()
  })

  it('negrito e lista viram elementos', () => {
    const { container } = render(<Markdown texto={'Resumo **55 kW**\n\n- CP-01\n- CP-02'} />)
    expect(container.querySelector('strong')).toHaveTextContent('55 kW')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })
})
