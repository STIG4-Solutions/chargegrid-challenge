/**
 * A aba de Analytics.
 *
 * Gráfico convence mais rápido que tabela, então o que se cobre aqui é onde ele
 * pode afirmar algo que o dado não sustenta:
 *
 * - janela maior que a idade do ponto tem de ser DITA, senão a média diária é
 *   lida como desempenho ruim;
 * - recebido e a receber não podem virar um número só;
 * - tendência sobre amostra curta é ruído com cara de conclusão;
 * - série toda zerada não pode estourar a escala nem sumir com as barras.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AgoraMesmo, Concentracao, NoTempo } from '../src/views/ev/Analytics.jsx'

const DIA = (dia, receita, energia, aReceber = 0) => ({
  dia,
  sessoes: receita > 0 ? 2 : 0,
  energia_kwh: energia,
  verde_kwh: energia / 2,
  receita_brl: receita,
  a_receber_brl: aReceber
})

const SERIE = {
  dias: 7,
  timezone: 'America/Sao_Paulo',
  desde: '2026-09-12',
  ate: '2026-09-18',
  janela_completa: true,
  dias_na_serie: 7,
  serie: [
    DIA('2026-09-12', 100, 40),
    DIA('2026-09-13', 0, 0),
    DIA('2026-09-14', 120, 45),
    DIA('2026-09-15', 90, 30),
    DIA('2026-09-16', 200, 70),
    DIA('2026-09-17', 210, 75),
    DIA('2026-09-18', 180, 60, 55)
  ],
  totais: {
    sessoes: 12,
    energia_kwh: 320,
    verde_kwh: 160,
    receita_brl: 900,
    a_receber_brl: 55,
    media_diaria_kwh: 45.7,
    media_diaria_brl: 128.6,
    ticket_medio_brl: 75,
    verde_pct: 50
  }
}

describe('no tempo', () => {
  it('separa o que entrou do que ainda não entrou', () => {
    // Somar os dois chamaria de receita dinheiro que ainda pode não entrar.
    render(<NoTempo d={SERIE} />)
    expect(screen.getByText('Receita recebida')).toBeInTheDocument()
    expect(screen.getByText('A receber')).toBeInTheDocument()
    expect(screen.getByText('R$ 900,00')).toBeInTheDocument()
    expect(screen.getByText('R$ 55,00')).toBeInTheDocument()
  })

  it('avisa quando o ponto é mais novo que a janela pedida', () => {
    // Sem o aviso, a média diária parece desempenho ruim em vez de janela curta.
    render(<NoTempo d={{ ...SERIE, janela_completa: false, dias: 90, dias_na_serie: 7 }} />)
    const aviso = screen.getByRole('status')
    expect(aviso).toHaveTextContent('mais novo que a janela pedida')
    expect(aviso).toHaveTextContent('7 dia(s)')
  })

  it('não avisa nada quando a janela cabe', () => {
    render(<NoTempo d={SERIE} />)
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('mostra a tendência entre as metades da janela', () => {
    // 100+0+120 = 220 na primeira metade, 90+200+210+180 = 680 na segunda.
    render(<NoTempo d={SERIE} />)
    expect(screen.getAllByText(/na 2ª metade/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/▲/).length).toBeGreaterThan(0)
  })

  it('cada gráfico se descreve para quem não enxerga o SVG', () => {
    render(<NoTempo d={SERIE} />)
    expect(screen.getByRole('img', { name: /Receita por dia/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Energia por dia/ })).toBeInTheDocument()
  })

  it('série toda zerada não quebra a tela', () => {
    // Topo da escala zero produziria divisão por zero — barras somem ou estouram.
    const zerada = {
      ...SERIE,
      serie: [DIA('2026-09-17', 0, 0), DIA('2026-09-18', 0, 0)],
      totais: { ...SERIE.totais, receita_brl: 0, energia_kwh: 0, verde_kwh: 0, verde_pct: 0 }
    }
    render(<NoTempo d={zerada} />)
    expect(screen.getByText(/Sem energia de origem solar/)).toBeInTheDocument()
    expect(screen.queryByText(/NaN|Infinity/)).toBeNull()
  })

  it('diz o fuso em que os dias foram agrupados', () => {
    // Sem isso, quem compara com outro relatório não sabe se a virada do dia bate.
    render(<NoTempo d={SERIE} />)
    expect(screen.getByText(/America\/Sao_Paulo/)).toBeInTheDocument()
  })
})

describe('agora', () => {
  it('não mistura o instante com a janela', () => {
    render(<AgoraMesmo d={{ active: 3, queued: 1, today: 12, pending_revenue: 40 }} />)
    expect(screen.getByText(/neste instante/)).toBeInTheDocument()
    expect(screen.getByText('Recargas em curso')).toBeInTheDocument()
  })
})

describe('concentração da receita', () => {
  const PONTOS = {
    pontos: [
      { code: 'CP-01', receita_brl: 700 },
      { code: 'CP-02', receita_brl: 200 },
      { code: 'CP-03', receita_brl: 100 }
    ]
  }

  it('ordena por receita e mostra a fatia de cada um', () => {
    render(<Concentracao d={PONTOS} />)
    const linhas = screen.getAllByRole('row').slice(1)
    expect(linhas[0]).toHaveTextContent('CP-01')
    expect(linhas[0]).toHaveTextContent('70.0%')
    expect(linhas[2]).toHaveTextContent('CP-03')
  })

  it('alerta quando um ponto sozinho passa de metade', () => {
    // É a leitura de risco: uma falha nele derruba metade do faturamento.
    render(<Concentracao d={PONTOS} />)
    expect(screen.getByText(/derruba metade do faturamento/)).toBeInTheDocument()
  })

  it('sem concentração perigosa, não inventa alerta', () => {
    render(
      <Concentracao
        d={{
          pontos: [
            { code: 'CP-01', receita_brl: 100 },
            { code: 'CP-02', receita_brl: 100 },
            { code: 'CP-03', receita_brl: 100 }
          ]
        }}
      />
    )
    expect(screen.queryByText(/derruba metade/)).toBeNull()
  })

  it('sem receita nenhuma, diz isso em vez de desenhar barra vazia', () => {
    render(<Concentracao d={{ pontos: [{ code: 'CP-01', receita_brl: 0 }] }} />)
    expect(screen.getByText(/nada a concentrar ainda/)).toBeInTheDocument()
  })
})
