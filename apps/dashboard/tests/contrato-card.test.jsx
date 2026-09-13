/**
 * O aviso de inadimplência na tela de contrato.
 *
 * O estado `inadimplente` existia no CHECK do banco e no mapa de badges desta
 * tela desde a fase 5 — e nada no sistema jamais o atribuía. Agora ele acontece,
 * e o que o operador LÊ quando acontece é o que estes testes fixam.
 *
 * `verify-dashboard.mjs` cobre `contrato.js` (multa, meses restantes). Aquelas
 * funções podem estar todas certas e a tela ainda não avisar nada.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AvisoDeAtraso, Cobrancas } from '../src/views/ev/Contract.jsx'

const SEM_ATRASO = { cobrancas: 0, total_brl: 0, desde: null }

describe('o aviso de cobrança vencida', () => {
  it('não aparece com o contrato em dia', () => {
    const { container } = render(<AvisoDeAtraso atraso={SEM_ATRASO} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('não aparece quando o campo nem veio da API', () => {
    // Painel novo contra API velha. Cair aqui derrubaria a aba inteira.
    const { container } = render(<AvisoDeAtraso atraso={undefined} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('mostra quanto e desde quando', () => {
    render(<AvisoDeAtraso atraso={{ cobrancas: 2, total_brl: 349, desde: '2026-08-03' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('2 cobranças vencidas')
    expect(screen.getByRole('alert')).toHaveTextContent('R$ 349,00')
    expect(screen.getByRole('alert')).toHaveTextContent('03/08/2026')
  })

  it('concorda o singular', () => {
    render(<AvisoDeAtraso atraso={{ cobrancas: 1, total_brl: 149, desde: '2026-08-03' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('1 cobrança vencida')
    expect(screen.getByRole('alert')).not.toHaveTextContent('cobranças')
  })

  it('diz a consequência, e diz o que NÃO acontece', () => {
    // Um aviso vermelho que não explica o efeito vira enfeite que ninguém lê
    // duas vezes. E o operador precisa saber que o motorista não foi cortado —
    // senão a primeira reação é achar que os pontos pararam.
    render(<AvisoDeAtraso atraso={{ cobrancas: 1, total_brl: 149, desde: '2026-08-03' }} />)
    const aviso = screen.getByRole('alert')
    expect(aviso).toHaveTextContent(/não renova sozinho/)
    expect(aviso).toHaveTextContent(/recargas continuam funcionando/)
  })
})

const COBRANCA = {
  id: 'c1',
  competencia: '2026-08-01',
  vence_em: '2026-08-10',
  assinatura_brl: 149,
  pontos_brl: 0,
  transacao_brl: 0,
  multa_brl: 0,
  total_brl: 149,
  pontos_cobrados: 0,
  faturamento_base_brl: 0,
  estado: 'vencida'
}

describe('a situação de cada cobrança', () => {
  it('vencida não se parece com em aberto', () => {
    // O fallback `?? COBRANCAS.aberta` não quebra a tela, e é por isso que
    // precisa de teste: sem ele, uma dívida de três meses apareceria em amarelo
    // como "Em aberto", indistinguível da cobrança emitida ontem.
    render(<Cobrancas linhas={[COBRANCA]} aoDarBaixa={() => {}} />)
    expect(screen.getByText('Vencida')).toBeInTheDocument()
    expect(screen.queryByText('Em aberto')).not.toBeInTheDocument()
  })

  it('em aberto continua em aberto', () => {
    render(<Cobrancas linhas={[{ ...COBRANCA, estado: 'aberta' }]} aoDarBaixa={() => {}} />)
    expect(screen.getByText('Em aberto')).toBeInTheDocument()
  })

  it('estado desconhecido não derruba a tela', () => {
    // A API pode ganhar um estado antes do painel. Cair aqui apagaria a lista
    // inteira de cobranças por causa de uma linha.
    render(<Cobrancas linhas={[{ ...COBRANCA, estado: 'protestada' }]} aoDarBaixa={() => {}} />)
    expect(screen.getByText(/ago\.? de 2026/i)).toBeInTheDocument()
    expect(screen.getAllByText('R$ 149,00').length).toBeGreaterThan(0)
  })

  it('sem cobrança nenhuma diz isso', () => {
    render(<Cobrancas linhas={[]} aoDarBaixa={() => {}} />)
    expect(screen.getByText(/Nenhuma cobrança emitida/)).toBeInTheDocument()
  })
})

describe('cobrança herdada de contrato anterior', () => {
  // A lista passou a ter escopo de SITE, e é isso que impede a dívida de sumir
  // da tela quando o estabelecimento assina outro plano. O efeito colateral é
  // que ela pode misturar contratos — e aí a linha precisa dizer de qual é.

  it('a herdada é marcada', () => {
    render(<Cobrancas linhas={[{ ...COBRANCA, contrato_anterior: true }]} aoDarBaixa={() => {}} />)
    expect(screen.getByText('contrato anterior')).toBeInTheDocument()
  })

  it('a do contrato vigente não é', () => {
    // Carimbar todas seria ruído: a cobrança emitida ontem apareceria como
    // herdada, e a marca deixaria de significar qualquer coisa.
    render(<Cobrancas linhas={[{ ...COBRANCA, contrato_anterior: false }]} aoDarBaixa={() => {}} />)
    expect(screen.queryByText('contrato anterior')).not.toBeInTheDocument()
  })

  it('API antiga, sem o campo, não inventa a marca', () => {
    // `contrato_anterior` é campo novo. Um painel novo contra uma API antiga
    // não pode carimbar tudo como herdado por causa de um `undefined`.
    render(<Cobrancas linhas={[COBRANCA]} aoDarBaixa={() => {}} />)
    expect(screen.queryByText('contrato anterior')).not.toBeInTheDocument()
  })
})
