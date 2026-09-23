/**
 * Abrir uma praça pelo painel.
 *
 * Até esta tela existir, a rede não tinha como abrir uma unidade: `Site` só
 * nascia no seed. E a falta não aparecia em log — aparecia na ausência de
 * outras telas, porque o seletor de praça e a Visão de Rede só se mostram com
 * mais de uma.
 *
 * O que se cobre aqui é o que faz uma praça nascer quebrada sem ninguém notar:
 * identificador que diverge do que o modelo de previsão conhece, e orçamento
 * que não sobra potência para ponto nenhum.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { NovaPraca } from '../src/views/ev/Contas.jsx'

const UMA = [{ site_id: 's1', nome: 'LAB FIAP Eco Station', cidade: 'São Paulo' }]

async function abrir(props = {}) {
  const criarPraca =
    props.criarPraca ?? vi.fn(() => Promise.resolve({ nome: 'Shopping Ibirapuera' }))
  const usuario = userEvent.setup()
  render(<NovaPraca pracas={UMA} aoCriar={() => {}} criarPraca={criarPraca} {...props} />)
  await usuario.click(screen.getByRole('button', { name: 'Nova praça' }))
  return { usuario, criarPraca }
}

async function preencher(
  usuario,
  { nome = 'Shopping Ibirapuera', limite = '150', reserva = '30' } = {}
) {
  await usuario.type(screen.getByLabelText('Nome'), nome)
  const campoLimite = screen.getByLabelText('Limite da rede (kW)')
  await usuario.clear(campoLimite)
  await usuario.type(campoLimite, limite)
  const campoReserva = screen.getByLabelText('Reserva do prédio (kW)')
  await usuario.clear(campoReserva)
  await usuario.type(campoReserva, reserva)
}

describe('antes de abrir', () => {
  it('com uma praça, explica o que a segunda destrava', () => {
    render(<NovaPraca pracas={UMA} aoCriar={() => {}} criarPraca={vi.fn()} />)
    expect(screen.getByText(/Com a segunda, o seletor aparece/)).toBeInTheDocument()
  })

  it('com mais de uma, conta quantas são', () => {
    render(
      <NovaPraca
        pracas={[...UMA, { site_id: 's2', nome: 'Outra' }]}
        aoCriar={() => {}}
        criarPraca={vi.fn()}
      />
    )
    expect(screen.getByText(/2 praças/)).toBeInTheDocument()
  })
})

describe('o formulário', () => {
  it('sugere o identificador a partir do nome, sem acento nem espaço', async () => {
    const { usuario } = await abrir()
    await usuario.type(screen.getByLabelText('Nome'), 'Shopping Ibirapuera')

    expect(screen.getByLabelText('Identificador')).toHaveValue('shopping-ibirapuera')
  })

  it('para de sugerir assim que alguém edita o identificador', async () => {
    // Continuar sobrescrevendo apagaria a escolha da pessoa a cada tecla no nome.
    const { usuario } = await abrir()
    await usuario.type(screen.getByLabelText('Nome'), 'Shopping')
    await usuario.clear(screen.getByLabelText('Identificador'))
    await usuario.type(screen.getByLabelText('Identificador'), 'ibira')
    await usuario.type(screen.getByLabelText('Nome'), ' Ibirapuera')

    expect(screen.getByLabelText('Identificador')).toHaveValue('ibira')
  })

  it('bloqueia o envio e diz o que falta', async () => {
    await abrir()
    expect(screen.getByRole('button', { name: 'Criar praça' })).toBeDisabled()
    expect(screen.getByText(/Dê um nome à praça/)).toBeInTheDocument()
  })

  it('recusa reserva maior que o limite, explicando a consequência', async () => {
    // Orçamento negativo: a praça fica de pé, aparece no seletor e rateia zero.
    const { usuario } = await abrir()
    await preencher(usuario, { limite: '50', reserva: '80' })

    expect(screen.getByRole('button', { name: 'Criar praça' })).toBeDisabled()
    expect(screen.getByText(/não sobra potência para nenhum ponto/)).toBeInTheDocument()
  })

  it('recusa limite zero', async () => {
    const { usuario } = await abrir()
    await preencher(usuario, { limite: '0' })

    expect(screen.getByRole('button', { name: 'Criar praça' })).toBeDisabled()
    expect(screen.getByText(/limite da rede em kW/)).toBeInTheDocument()
  })

  it('envia com os nomes que a rota espera, e a UF em maiúscula', async () => {
    const { usuario, criarPraca } = await abrir()
    await preencher(usuario)
    await usuario.type(screen.getByLabelText('Cidade'), 'São Paulo')
    await usuario.type(screen.getByLabelText('UF'), 'sp')
    await usuario.click(screen.getByRole('button', { name: 'Criar praça' }))

    expect(criarPraca).toHaveBeenCalledWith({
      nome: 'Shopping Ibirapuera',
      slug: 'shopping-ibirapuera',
      cidade: 'São Paulo',
      estado: 'SP',
      limite_da_rede_kw: 150,
      reserva_kw: 30
    })
  })

  it('depois de criar, diz que o seletor passou a existir', async () => {
    // Sem isso a pessoa procuraria a praça nova numa tela que mostra a antiga.
    const { usuario } = await abrir()
    await preencher(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Criar praça' }))

    const aviso = await screen.findByRole('status')
    expect(aviso).toHaveTextContent('Shopping Ibirapuera criada')
    expect(aviso).toHaveTextContent('seletor de praça agora aparece')
  })

  it('erro do servidor aparece como alerta', async () => {
    const recusa = () => Promise.reject({ detail: "ja existe uma praca com o identificador 'x'" })
    const { usuario } = await abrir({ criarPraca: recusa })
    await preencher(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Criar praça' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('ja existe uma praca')
  })

  it('avisa que a praça nasce vazia', async () => {
    await abrir()
    expect(
      screen.getByText(/sem pontos de recarga, tarifa ou método de pagamento/)
    ).toBeInTheDocument()
  })
})
