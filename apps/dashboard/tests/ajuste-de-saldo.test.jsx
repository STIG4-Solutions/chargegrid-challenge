/**
 * O ajuste manual de saldo, na lista de faturas.
 *
 * A rota `POST /wallets/{id}/adjust` e o método do SDK existiam desde sempre, e
 * nenhuma tela os chamava: o admin não tinha como corrigir o saldo de alguém
 * pelo painel. Capacidade declarada e inalcançável — o padrão que esta base já
 * corrigiu várias vezes.
 *
 * O que se cobre aqui é o que torna essa ação segura de existir. É o único
 * lançamento do razão em que alguém escolhe o número:
 *
 * - a pessoa afetada é NOMEADA, porque a lista tem várias faturas parecidas e
 *   abrir na linha errada é o erro provável;
 * - o sentido aparece em palavras, porque "-50" e "+50" diferem por um
 *   caractere e aqui o engano cria ou apaga dinheiro de verdade;
 * - o botão desabilitado DIZ o que falta, senão a tela trava em silêncio.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AjusteDeSaldo } from '../src/views/ev/TariffPayment.jsx'

const montar = (props = {}) => {
  const ajustar = props.ajustar ?? vi.fn(() => Promise.resolve({ saldo: 150 }))
  render(
    <AjusteDeSaldo
      email="ana.costa@email.com"
      userId="u-1"
      aoConcluir={() => {}}
      ajustar={ajustar}
      {...props}
    />
  )
  return { ajustar, usuario: userEvent.setup() }
}

describe('o formulário', () => {
  it('nomeia quem vai ser afetado', () => {
    montar()
    expect(screen.getByText(/Ajustar o saldo de ana.costa@email.com/)).toBeInTheDocument()
  })

  it('começa com o envio bloqueado, e diz por quê', () => {
    montar()
    expect(screen.getByRole('button', { name: /Lançar ajuste/ })).toBeDisabled()
    expect(screen.getByText('Informe o valor do ajuste.')).toBeInTheDocument()
  })

  it('valor sem motivo continua bloqueado', async () => {
    // Motivo é obrigatório também no banco: dinheiro que aparece na conta de
    // alguém sem ninguém saber explicar é o defeito que um razão impede.
    const { usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '50')

    expect(screen.getByRole('button', { name: /Lançar ajuste/ })).toBeDisabled()
    expect(screen.getByText(/O motivo é obrigatório/)).toBeInTheDocument()
  })

  it('zero é recusado antes de sair da tela', async () => {
    const { usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '0')
    await usuario.type(screen.getByLabelText('Motivo'), 'correção')

    expect(screen.getByRole('button', { name: /Lançar ajuste/ })).toBeDisabled()
    expect(screen.getByText('Ajuste de zero não corrige nada.')).toBeInTheDocument()
  })

  it('anuncia o sentido em palavras enquanto se digita', async () => {
    const { usuario } = montar()
    const valor = screen.getByLabelText('Valor')

    await usuario.type(valor, '50')
    expect(screen.getByText(/^Crédito:/)).toBeInTheDocument()

    await usuario.clear(valor)
    await usuario.type(valor, '-50')
    expect(screen.getByText(/^Débito:/)).toBeInTheDocument()
  })

  it('envia o valor como número e o motivo sem espaço sobrando', async () => {
    const { ajustar, usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '-12.5')
    await usuario.type(screen.getByLabelText('Motivo'), '  estorno em duplicidade  ')
    await usuario.click(screen.getByRole('button', { name: /Lançar ajuste/ }))

    expect(ajustar).toHaveBeenCalledWith('u-1', -12.5, 'estorno em duplicidade')
  })

  it('depois de lançar, confirma o sentido e o novo saldo', async () => {
    const { usuario } = montar({ ajustar: () => Promise.resolve({ saldo: 87.5 }) })
    await usuario.type(screen.getByLabelText('Valor'), '-12.5')
    await usuario.type(screen.getByLabelText('Motivo'), 'estorno')
    await usuario.click(screen.getByRole('button', { name: /Lançar ajuste/ }))

    const aviso = await screen.findByRole('status')
    expect(aviso).toHaveTextContent('Debitado')
    expect(aviso).toHaveTextContent('R$ 12,50')
    expect(aviso).toHaveTextContent('R$ 87,50')
  })

  it('erro do servidor aparece como alerta, não em silêncio', async () => {
    const recusa = () => Promise.reject({ detail: 'ajuste deixaria o saldo negativo' })
    const { usuario } = montar({ ajustar: recusa })
    await usuario.type(screen.getByLabelText('Valor'), '-999')
    await usuario.type(screen.getByLabelText('Motivo'), 'teste')
    await usuario.click(screen.getByRole('button', { name: /Lançar ajuste/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('saldo negativo')
  })
})
