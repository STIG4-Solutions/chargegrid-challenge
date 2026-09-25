/**
 * O que o operador LÊ no card de previsão.
 *
 * `verify-dashboard.mjs` já cobre as funções puras de `previsao.js` — "há
 * banda?", "o modelo ganha da régua?". Elas podem estar todas certas e a tela
 * ainda mentir: basta o card ignorar `fonte` no rótulo, ou desenhar a barra
 * mesmo com `temBanda` dizendo que não.
 *
 * É exatamente a lacuna que estes testes fecham, e é a razão de a previsão ter
 * três estados em vez de dois: dois deles entregam o MESMO número por motivos
 * opostos, e só o texto os separa.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PrevisaoDeEnergia } from '../src/views/ev/DemandContract.jsx'

const BASE = {
  disponivel: true,
  competencia: '2026-10-01',
  gerado_em: '2026-09-10T03:00:00+00:00',
  kwh_previsto: 2156.1,
  kwh_p10: null,
  kwh_p90: null,
  faturamento_previsto_brl: 3234.15,
  fat_p10_brl: null,
  fat_p90_brl: null,
  media_diaria_28d: 71.87,
  modelo_aplicavel: true,
  fonte: 'media_movel',
  modelo_versao: '1.4.0',
  dias_de_historico: 730,
  cobertura_declarada_pct: 80,
  cobertura_medida_pct: 62.3,
  wape_modelo_pct: 9.05,
  wape_baseline_pct: 7.61,
  avisos: []
}

const comModelo = (extra = {}) => ({
  ...BASE,
  fonte: 'modelo',
  kwh_p10: 1800,
  kwh_p90: 2500,
  fat_p10_brl: 2700,
  fat_p90_brl: 3750,
  ...extra
})

describe('o rótulo do número', () => {
  it('chama de previsão só o que veio do modelo', () => {
    render(<PrevisaoDeEnergia d={comModelo()} />)
    expect(screen.getByText('Energia prevista')).toBeInTheDocument()
  })

  it('chama de média móvel o que veio da régua', () => {
    render(<PrevisaoDeEnergia d={BASE} />)
    expect(screen.getByText('Média dos últimos 28 dias')).toBeInTheDocument()
    expect(screen.queryByText('Energia prevista')).not.toBeInTheDocument()
  })
})

describe('a barra de incerteza', () => {
  it('aparece quando o número é do modelo e tem os dois extremos', () => {
    const { container } = render(<PrevisaoDeEnergia d={comModelo()} />)
    expect(screen.getByText(/faixa 1\.?800/)).toBeInTheDocument()
    expect(container.querySelectorAll('div[style*="border-radius: 999px"]').length).toBeGreaterThan(
      0
    )
  })

  it('não aparece em volta de uma média móvel', () => {
    // O ponto todo: desenhar incerteza em volta de uma conta de três linhas
    // daria a ela ares de previsão, e é com esse desenho que se contrata
    // demanda.
    const { container } = render(<PrevisaoDeEnergia d={BASE} />)
    expect(screen.queryByText(/faixa/)).not.toBeInTheDocument()
    expect(container.querySelectorAll('div[style*="border-radius: 999px"]')).toHaveLength(0)
  })

  it('não aparece quando a média móvel VEM com banda', () => {
    // O caso que prova que a guarda olha `fonte`, e não `modelo_aplicavel`.
    //
    // Com p10/p90 nulos os dois critérios concordam, e o teste passaria de
    // qualquer jeito — foi assim que a primeira versão deste arquivo deixou a
    // mutação sobreviver. Aqui os extremos existem e a fonte é a régua: só
    // quem lê `fonte` recusa desenhar.
    //
    // O CHECK do banco já barra essa linha, mas o painel é um artefato
    // separado e pode conversar com uma API mais velha que a coluna.
    render(<PrevisaoDeEnergia d={{ ...BASE, kwh_p10: 1800, kwh_p90: 2500 }} />)
    expect(screen.queryByText(/faixa/)).not.toBeInTheDocument()
    expect(screen.getByText('Média dos últimos 28 dias')).toBeInTheDocument()
  })

  it('não aparece com meia banda, mesmo vindo do modelo', () => {
    // Meia banda mente sobre a incerteza declarada.
    render(<PrevisaoDeEnergia d={comModelo({ kwh_p90: null })} />)
    expect(screen.queryByText(/faixa/)).not.toBeInTheDocument()
  })

  // A COR da barra, que é o único sinal de que a cobertura foi conferida.
  //
  // `verify-dashboard.mjs` cobre `bandaConfiavel` como função pura, e os três
  // estados dela estão presos lá. O que faltava era a ligação com o JSX: a mutação
  // que troca `confiavel === true` por `confiavel !== false` sobrevivia a toda a
  // suíte — e é exatamente a que devolve o verde à faixa não medida.
  const fundoDaBarra = (container) =>
    [...container.querySelectorAll('div[style*="border-radius: 999px"]')]
      .map((el) => el.style.background)
      .find((bg) => bg && bg.includes('rgba'))

  const VERDE = '52, 199, 89'
  const AMBAR = '255, 204, 0'

  it('é verde quando a cobertura foi medida e ficou dentro do declarado', () => {
    const { container } = render(
      <PrevisaoDeEnergia d={comModelo({ cobertura_medida_pct: 79.6 })} />
    )
    expect(fundoDaBarra(container)).toContain(VERDE)
  })

  it('é âmbar quando a cobertura medida ficou abaixo do declarado', () => {
    const { container } = render(
      <PrevisaoDeEnergia d={comModelo({ cobertura_medida_pct: 60.5 })} />
    )
    expect(fundoDaBarra(container)).toContain(AMBAR)
  })

  it('é âmbar quando a cobertura NÃO foi medida', () => {
    // O caso de staging: os fatores da faixa vêm de 54 resíduos e a cobertura foi
    // medida em nenhum, porque a calibração rolante junta 18 com 3 praças. A faixa é
    // legítima; a aferição dela não existe, e ausência de medição não é aprovação.
    const { container } = render(
      <PrevisaoDeEnergia d={comModelo({ cobertura_medida_pct: null })} />
    )
    expect(fundoDaBarra(container)).toContain(AMBAR)
  })
})

describe('a base de cálculo distingue os dois fallbacks', () => {
  it('diz que falta histórico quando o modelo não conhece o ponto', () => {
    render(<PrevisaoDeEnergia d={{ ...BASE, modelo_aplicavel: false }} />)
    expect(screen.getByText(/sem histórico para o modelo/)).toBeInTheDocument()
  })

  it('diz que o modelo perdeu quando ele conhece o ponto e não é usado', () => {
    render(<PrevisaoDeEnergia d={BASE} />)
    expect(screen.getByText(/o modelo não supera esta régua/)).toBeInTheDocument()
  })

  it('mostra a versão do modelo quando é ele que responde', () => {
    render(<PrevisaoDeEnergia d={comModelo()} />)
    expect(screen.getByText(/modelo 1\.4\.0/)).toBeInTheDocument()
  })
})

describe('os avisos', () => {
  it('são impressos como vieram da API', () => {
    const texto = 'Este número é a média dos últimos 28 dias.'
    render(<PrevisaoDeEnergia d={{ ...BASE, avisos: [{ nivel: 'medio', texto }] }} />)
    expect(screen.getByText(texto)).toBeInTheDocument()
  })

  it('nível desconhecido não derruba a tela', () => {
    // A API pode ganhar um nível novo antes do painel. Cair aqui apagaria o
    // card inteiro — e com ele o aviso que justamente importava mostrar.
    const texto = 'nível que o painel ainda não conhece'
    render(<PrevisaoDeEnergia d={{ ...BASE, avisos: [{ nivel: 'critico', texto }] }} />)
    expect(screen.getByText(texto)).toBeInTheDocument()
  })
})

describe('quando não há previsão', () => {
  it('mostra o motivo, e não um zero', () => {
    // Zero e "não calculamos" são coisas diferentes, e um ponto que aparece
    // vendendo 0 kWh é o tipo de número que alguém leva para uma reunião.
    const motivo = 'Nenhuma previsão calculada para este ponto ainda.'
    render(<PrevisaoDeEnergia d={{ disponivel: false, motivo }} />)
    expect(screen.getByText(motivo)).toBeInTheDocument()
    expect(screen.queryByText('kWh')).not.toBeInTheDocument()
  })
})
