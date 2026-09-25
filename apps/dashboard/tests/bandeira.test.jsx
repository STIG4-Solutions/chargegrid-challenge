/**
 * A bandeira do site no topo da aba Potência.
 *
 * O que o operador lê: a cor, o multiplicador que uma recarga iniciada agora
 * trava, a folga e o motivo. Desatualizada ela aparece marcada, e não some —
 * sumir faria parecer que a precificação dinâmica nem existe. O botão de pico
 * de demo só aparece para administrador, e só com o site simulado.
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BandeiraDoSite, comBandeiraDoPlano } from '../src/views/ev/Bandeira.jsx'

const AMARELA = {
  cor: 'amarela',
  multiplicador: 1.15,
  folga_pct: 40,
  motivo: 'Consumo do prédio alto: sobra pouca potência para os carregadores',
  calculada_em: '2026-09-25T14:00:00Z',
  desatualizada: false
}

describe('a bandeira do site', () => {
  it('mostra cor, multiplicador, folga e motivo', () => {
    render(<BandeiraDoSite bandeira={AMARELA} />)
    const b = screen.getByRole('status')
    expect(b).toHaveTextContent('Bandeira amarela')
    expect(b).toHaveTextContent('x1,15')
    expect(b).toHaveTextContent('40,0% de folga')
    expect(b).toHaveTextContent('Consumo do prédio alto')
  })

  it('desatualizada, diz isso em vez de mostrar a cor', () => {
    render(<BandeiraDoSite bandeira={{ ...AMARELA, desatualizada: true }} />)
    const b = screen.getByRole('status')
    expect(b).toHaveTextContent('Bandeira desatualizada')
    expect(b).not.toHaveTextContent('Bandeira amarela')
  })

  it('sem bandeira (flag desligada), não aparece', () => {
    const { container } = render(<BandeiraDoSite bandeira={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('o botão de pico só aparece para admin com o site simulado', () => {
    const { rerender } = render(
      <BandeiraDoSite bandeira={AMARELA} isAdmin={false} demoDisponivel />
    )
    expect(screen.queryByRole('button', { name: /simular pico/i })).toBeNull()

    rerender(<BandeiraDoSite bandeira={AMARELA} isAdmin demoDisponivel={false} />)
    expect(screen.queryByRole('button', { name: /simular pico/i })).toBeNull()

    const onSimular = vi.fn()
    rerender(<BandeiraDoSite bandeira={AMARELA} isAdmin demoDisponivel onSimular={onSimular} />)
    fireEvent.click(screen.getByRole('button', { name: /simular pico/i }))
    expect(onSimular).toHaveBeenCalledOnce()
  })

  it('com pico em andamento, avisa até quando em vez de oferecer outro', () => {
    render(
      <BandeiraDoSite
        bandeira={{ ...AMARELA, cor: 'vermelha', multiplicador: 1.3 }}
        isAdmin
        demoDisponivel
        picoAte="2026-09-25T14:05:00Z"
        fuso="America/Sao_Paulo"
      />
    )
    expect(screen.getByRole('status')).toHaveTextContent('Pico simulado até 11:05')
    expect(screen.queryByRole('button', { name: /simular pico/i })).toBeNull()
  })
})

describe('o evento power_plan atualiza a bandeira', () => {
  it('troca a bandeira do overview pela do plano', () => {
    const overview = { total_count: 2, bandeira: AMARELA }
    const plano = { bandeira: { ...AMARELA, cor: 'vermelha', multiplicador: 1.3 } }
    expect(comBandeiraDoPlano(overview, plano).bandeira.cor).toBe('vermelha')
    expect(comBandeiraDoPlano(overview, plano).total_count).toBe(2)
  })

  it('plano sem bandeira (flag desligada) não apaga nada', () => {
    const overview = { bandeira: null }
    expect(comBandeiraDoPlano(overview, {})).toBe(overview)
    expect(comBandeiraDoPlano(null, plano())).toBeNull()
  })
})

function plano() {
  return { bandeira: AMARELA }
}
