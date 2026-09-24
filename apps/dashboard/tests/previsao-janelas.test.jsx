/**
 * O que o operador LÊ na seção de previsão por janela.
 *
 * `verify-dashboard.mjs` já cobre as funções puras de `janelas.js` — "esta fonte
 * é modelo?", "a série traz faixa?". Elas podem estar todas certas e a tela ainda
 * mentir: basta o cartão ignorar `fonte` no rótulo, ou desenhar a banda numa
 * janela que não a declara.
 *
 * É a mesma lacuna que `previsao-card.test.jsx` fecha para o card mensal, e pela
 * mesma razão: quatro das cinco janelas são servidas por RÉGUA, e só o texto
 * separa isso de uma previsão de modelo. Quem contrata demanda lê o texto.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Previsao } from '../src/views/ev/Analytics.jsx'

const semRuido = () => {}

const serie = (janela, buckets, extra = {}) => ({
  disponivel: true,
  janela,
  escopo: 'praca',
  gerado_em: '2026-09-24T03:00:00+00:00',
  modelo_versao: '1.0.0',
  wape_modelo_pct: 11.98,
  wape_baseline_pct: 15.38,
  cobertura_declarada_pct: 80,
  cobertura_medida_pct: 71.3,
  buckets,
  avisos: [],
  ...extra
})

const horas = (n = 6) =>
  Array.from({ length: n }, (_, i) => ({
    bucket_inicio: `2026-09-24T${String(10 + i).padStart(2, '0')}:00:00-03:00`,
    kwh_previsto: 40 + i,
    kwh_p10: 10 + i,
    kwh_p90: 90 + i,
    faturamento_previsto_brl: (40 + i) * 2.6,
    fat_p10_brl: (10 + i) * 2.6,
    fat_p90_brl: (90 + i) * 2.6,
    fonte: 'perfil_hora'
  }))

const dias = (n = 5, fonte = 'media_dow') =>
  Array.from({ length: n }, (_, i) => ({
    bucket_inicio: `2026-09-${String(24 + i).padStart(2, '0')}T00:00:00-03:00`,
    kwh_previsto: 500 + i * 10,
    kwh_p10: null,
    kwh_p90: null,
    faturamento_previsto_brl: (500 + i * 10) * 2.6,
    fat_p10_brl: null,
    fat_p90_brl: null,
    fonte
  }))

describe('a seção de previsão por janela', () => {
  it('declara que o número veio de régua, e não do modelo', () => {
    render(<Previsao d={serie('dia', dias())} janela="dia" onJanela={semRuido} />)

    expect(screen.getByText('Régua')).toBeTruthy()
    // A origem e' nomeada em DOIS lugares de proposito: na nota do cartao, para
    // quem só bate o olho, e dentro do aviso, para quem lê a explicação. Um
    // `getByText` recusaria os dois, e é isso que este `getAllByText` afirma.
    expect(screen.getAllByText('média por dia da semana')).toHaveLength(2)
    // E explica POR QUE, senão "régua" soa como defeito em vez de decisão.
    expect(screen.getByText(/régua mede igual ou melhor/i)).toBeTruthy()
  })

  it('não avisa sobre régua quando o número é do modelo', () => {
    render(<Previsao d={serie('mes', dias(3, 'modelo'))} janela="mes" onJanela={semRuido} />)

    expect(screen.getByText('Modelo')).toBeTruthy()
    expect(screen.getByText('modelo de previsão')).toBeTruthy()
    expect(screen.queryByText(/régua mede igual ou melhor/i)).toBeNull()
  })

  it('uma fonte que a tela não conhece não vira "Modelo"', () => {
    // Um valor novo no banco tem de aparecer estranho, não ganhar o selo de
    // previsão sem ninguém ter decidido isso.
    render(<Previsao d={serie('dia', dias(3, 'metodo_novo'))} janela="dia" onJanela={semRuido} />)

    expect(screen.getByText('Régua')).toBeTruthy()
    expect(screen.queryByText('Modelo')).toBeNull()
  })

  it('desenha a faixa só onde a série a declara', () => {
    const { container: comFaixa } = render(
      <Previsao d={serie('hora', horas())} janela="hora" onJanela={semRuido} />
    )
    expect(comFaixa.querySelector('polygon')).toBeTruthy()
    expect(comFaixa.querySelector('polyline')).toBeTruthy()

    const { container: semFaixa } = render(
      <Previsao d={serie('dia', dias())} janela="dia" onJanela={semRuido} />
    )
    expect(semFaixa.querySelector('polygon')).toBeNull()
    // Sem faixa o desenho é de barras: o idioma do resto da aba.
    expect(semFaixa.querySelector('rect')).toBeTruthy()
  })

  it('anuncia a cobertura medida junto da faixa, e não a prometida', () => {
    render(<Previsao d={serie('hora', horas())} janela="hora" onJanela={semRuido} />)

    // 71%, não 80%: a faixa é mais estreita do que anuncia, e esconder isso
    // faria o operador tratar o extremo inferior como pior caso.
    expect(screen.getByText(/71% dos casos/)).toBeTruthy()
  })

  it('a faixa sem cobertura medida não inventa um número', () => {
    render(
      <Previsao
        d={serie('hora', horas(), { cobertura_medida_pct: null })}
        janela="hora"
        onJanela={semRuido}
      />
    )

    expect(screen.getByText(/faixa p10–p90/)).toBeTruthy()
    expect(screen.queryByText(/dos casos/)).toBeNull()
  })

  it('sem previsão calculada mostra o motivo, e não um gráfico vazio', () => {
    const vazia = {
      disponivel: false,
      janela: 'ano',
      escopo: 'praca',
      motivo: "Nenhuma previsão de janela 'ano' calculada ainda."
    }
    const { container } = render(<Previsao d={vazia} janela="ano" onJanela={semRuido} />)

    expect(screen.getByText(/Nenhuma previsão de janela 'ano'/)).toBeTruthy()
    expect(container.querySelector('svg')).toBeNull()
  })

  it('a janela escolhida aparece pressionada, e as outras não', () => {
    render(<Previsao d={serie('semana', dias())} janela="semana" onJanela={semRuido} />)

    const semana = screen.getByRole('button', { name: 'Semana' })
    const hora = screen.getByRole('button', { name: 'Hora' })
    expect(semana.getAttribute('aria-pressed')).toBe('true')
    expect(hora.getAttribute('aria-pressed')).toBe('false')
  })

  it('o eixo da janela horária mostra a hora', () => {
    render(<Previsao d={serie('hora', horas())} janela="hora" onJanela={semRuido} />)

    // Sem a hora, a curva do dia não diz nada - é o sinal que a janela existe
    // para mostrar.
    expect(screen.getByText(/24\/09 10h/)).toBeTruthy()
  })

  it('faturamento ausente vira travessão, e não R$ 0,00', () => {
    // A previsão da REDE é gravada sem reais: somar praças com tarifas
    // diferentes daria um preço que não existe em contrato nenhum. Zero ali
    // afirmaria que a rede não fatura.
    const daRede = dias(3).map((b) => ({ ...b, faturamento_previsto_brl: null }))
    render(
      <Previsao d={serie('dia', daRede, { escopo: 'rede' })} janela="dia" onJanela={semRuido} />
    )

    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.queryByText(/R\$\s*0,00/)).toBeNull()
  })

  it('o escopo rede so aparece para quem administra', () => {
    // Um total da rede com poucas pracas permite inferir o movimento das outras -
    // com duas, por subtracao exata. Quem opera uma praca ve' a praca dele, e a
    // rota do servidor tambem recusa (`AdminUser`): esconder o botao e' a segunda
    // camada, nao a unica.
    const { unmount } = render(
      <Previsao d={serie('dia', dias())} janela="dia" onJanela={semRuido} />
    )
    expect(screen.queryByRole('button', { name: 'Rede inteira' })).toBeNull()
    unmount()

    render(
      <Previsao
        d={serie('dia', dias())}
        janela="dia"
        onJanela={semRuido}
        escopo="praca"
        onEscopo={semRuido}
        podeVerRede
      />
    )
    expect(screen.getByRole('button', { name: 'Rede inteira' })).toBeTruthy()
  })

  it('no escopo da rede a tela explica por que ele e restrito', () => {
    render(
      <Previsao
        d={serie('dia', dias(), { escopo: 'rede' })}
        janela="dia"
        onJanela={semRuido}
        escopo="rede"
        onEscopo={semRuido}
        podeVerRede
      />
    )

    expect(screen.getByText(/subtracao exata|subtração exata/)).toBeTruthy()
    const botao = screen.getByRole('button', { name: 'Rede inteira' })
    expect(botao.getAttribute('aria-pressed')).toBe('true')
  })
})
