/**
 * Os campos da aba Regras de Prioridade.
 *
 * A tela não tinha teste nenhum, e os campos tinham o defeito que o formulário
 * de contas já tinha corrido atrás: `<input>` sem `className="input"`, então
 * sem estilo; rótulo envolvendo o controle, então o botão ao lado disparava o
 * campo; e dica como placeholder, que some justamente quando a pessoa digita.
 *
 * O que estes testes fixam é o acordo do padrão: todo controle responde pelo
 * rótulo (é o que leitor de tela usa, e o que prova a associação), e a dica
 * existe fora do placeholder.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Lista, Previa } from '../src/views/ev/PriorityRules.jsx'

const REGRAS = [
  {
    id: 'r1',
    nome: 'Frota da noite',
    prioridade: 300,
    ordem: 10,
    ativo: true,
    criterio_tipo: 'sempre',
    criterio_valor: null,
    janela_inicio: '22:00',
    janela_fim: '06:00'
  }
]

const PREVIA = {
  timezone: 'America/Sao_Paulo',
  regras_ativas: 1,
  pontos: [
    {
      code: 'CP-01',
      name: 'Vaga 1',
      regra: 'Frota da noite',
      prioridade_base: 100,
      prioridade_efetiva: 300
    },
    { code: 'CP-02', name: 'Vaga 2', regra: null, prioridade_base: 100, prioridade_efetiva: 100 }
  ]
}

async function abrirFormulario() {
  const usuario = userEvent.setup()
  render(<Lista regras={REGRAS} onMudou={() => {}} />)
  await usuario.click(screen.getByRole('button', { name: 'Nova regra' }))
  return usuario
}

describe('nova regra', () => {
  it('cada campo responde pelo rótulo', async () => {
    // É o que leitor de tela usa para anunciar, e o que prova que `htmlFor`
    // aponta para o controle certo.
    await abrirFormulario()
    expect(screen.getByLabelText('Nome')).toBeInTheDocument()
    expect(screen.getByLabelText('Prioridade')).toBeInTheDocument()
    expect(screen.getByLabelText('Ordem de avaliação')).toBeInTheDocument()
    expect(screen.getByLabelText('Aplica-se a')).toBeInTheDocument()
    expect(screen.getByLabelText('Vale a partir de')).toBeInTheDocument()
    expect(screen.getByLabelText('Até')).toBeInTheDocument()
  })

  it('as dicas ficam na tela, não no placeholder', async () => {
    // Placeholder some quando a pessoa começa a digitar — que é exatamente
    // quando "maior é servido primeiro" ainda importa.
    await abrirFormulario()
    expect(screen.getByText(/Maior é servido primeiro/)).toBeInTheDocument()
    expect(screen.getByText(/Menor decide antes/)).toBeInTheDocument()
    expect(screen.getByLabelText('Nome')).not.toHaveAttribute('placeholder')
  })

  it('a janela explica a virada da meia-noite onde o campo está', async () => {
    await abrirFormulario()
    // Específico de propósito: a REGRA já listada também tem janela 22:00→06:00,
    // e casar só pelo horário pegaria a linha da tabela em vez da dica.
    expect(
      screen.getByText('22:00 → 06:00 é aceito e cobre a virada da meia-noite.')
    ).toBeInTheDocument()
  })

  it('o campo de valor só aparece para critério que precisa dele', async () => {
    // Com "Todos os pontos" não há o que listar, e um campo inerte ao lado
    // convidaria a preenchê-lo.
    const usuario = await abrirFormulario()
    // Os DOIS rótulos: o campo só tem um, escolhido pelo critério, e checar só
    // "Códigos dos pontos" passaria mesmo com o campo na tela sob o outro nome.
    expect(screen.queryByLabelText('Códigos dos pontos')).toBeNull()
    expect(screen.queryByLabelText('Conectores')).toBeNull()

    await usuario.selectOptions(screen.getByLabelText('Aplica-se a'), 'ponto')
    expect(screen.getByLabelText('Códigos dos pontos')).toBeInTheDocument()

    await usuario.selectOptions(screen.getByLabelText('Aplica-se a'), 'conector')
    expect(screen.getByLabelText('Conectores')).toBeInTheDocument()
    expect(screen.queryByLabelText('Códigos dos pontos')).toBeNull()
  })

  it('a situação diz o efeito de salvar, e não só "ativa"', async () => {
    const usuario = await abrirFormulario()
    expect(screen.getByText(/Entra no rateio assim que for salva/)).toBeInTheDocument()

    await usuario.click(screen.getByLabelText('Situação'))
    expect(screen.getByText(/Fica cadastrada sem efeito nenhum/)).toBeInTheDocument()
  })
})

describe('quem tem prioridade agora', () => {
  it('o horário responde pelo rótulo e explica o vazio', () => {
    render(<Previa d={PREVIA} hora="" setHora={() => {}} />)
    expect(screen.getByLabelText('Horário simulado')).toBeInTheDocument()
    expect(screen.getByText('Vazio = agora.')).toBeInTheDocument()
  })

  it('com horário escolhido, diz o que está mostrando', () => {
    render(<Previa d={PREVIA} hora="23:30" setHora={() => {}} />)
    expect(screen.getByText(/Mostrando as regras como às 23:30/)).toBeInTheDocument()
  })

  it('o botão de voltar só existe quando há o que desfazer', () => {
    const { rerender } = render(<Previa d={PREVIA} hora="" setHora={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Voltar para agora' })).toBeNull()

    rerender(<Previa d={PREVIA} hora="23:30" setHora={() => {}} />)
    expect(screen.getByRole('button', { name: 'Voltar para agora' })).toBeInTheDocument()
  })

  it('ponto sem regra diz o que vale no lugar', () => {
    // "—" deixaria a pessoa sem saber se falta regra ou se o ponto foi ignorado.
    render(<Previa d={PREVIA} hora="" setHora={() => {}} />)
    expect(screen.getByText(/nenhuma — vale o valor do ponto/)).toBeInTheDocument()
  })
})
