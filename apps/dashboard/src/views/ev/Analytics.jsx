/**
 * Analytics — a visão executiva da operação deste eletroposto.
 *
 * Existe porque as outras abas respondem cada uma a sua pergunta operacional, e
 * nenhuma responde à pergunta de quem decide: **como está indo?** Potência
 * responde "o que está acontecendo agora", Ocupação responde "onde rende mais",
 * Plano & Contrato responde "quanto pago à rede". Faltava a leitura no tempo.
 *
 * Três princípios que o resto do painel já segue e que aqui pesam mais, porque
 * gráfico convence mais rápido do que tabela:
 *
 * 1. NÃO DESENHAR O QUE NÃO SE MEDIU. Janela maior que a idade do site vem com
 *    `janela_completa: false`, e a tela diz — média diária sobre dias que não
 *    existiram é média falsa.
 * 2. RECEBIDO E A RECEBER SEPARADOS, sempre. Somar os dois infla a leitura com
 *    dinheiro que ainda pode não entrar.
 * 3. TENDÊNCIA SÓ COM AMOSTRA. Menos de quatro dias não formam tendência, e uma
 *    seta verde sobre ruído é pior que seta nenhuma.
 *
 * Os gráficos são SVG à mão, no mesmo idioma de `DemandContract`: `viewBox` de
 * 0 a 100 com `preserveAspectRatio="none"`. Nenhuma biblioteca — o painel tem
 * quatro dependências, e nenhuma delas é de desenho.
 */

import { power, sessions, useApi } from '@chargegrid/sdk'
import { useState } from 'react'
import { Async } from '../../components/Async.jsx'
import {
  comoKwh,
  comoReais,
  diaCurto,
  participacao,
  rotulosDoEixo,
  tendencia,
  topoDaEscala
} from './analytics.js'

const JANELAS = [
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
  { dias: 90, rotulo: '90 dias' }
]

export default function Analytics() {
  const [dias, setDias] = useState(30)
  const serie = useApi(() => power.dailyAnalytics(dias), [dias], { pollMs: 300000 })
  const kpis = useApi(() => sessions.kpis(), [], { pollMs: 30000 })
  const pontos = useApi(() => power.utilizationByPoint(dias), [dias])

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 16
        }}
      >
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: 18 }}>Analytics</h2>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Como a operação está indo — não só quanto ela somou.
          </p>
        </div>
        <div role="group" aria-label="Janela de análise" style={{ display: 'flex', gap: 6 }}>
          {JANELAS.map((j) => (
            <button
              key={j.dias}
              className={dias === j.dias ? 'btn btn-primary btn-sm' : 'btn btn-sm'}
              aria-pressed={dias === j.dias}
              onClick={() => setDias(j.dias)}
            >
              {j.rotulo}
            </button>
          ))}
        </div>
      </div>

      <Async
        loading={kpis.loading}
        error={kpis.error}
        data={kpis.data}
        onRetry={kpis.refetch}
        empty={null}
      >
        {kpis.data && <AgoraMesmo d={kpis.data} />}
      </Async>

      <Async
        loading={serie.loading}
        error={serie.error}
        data={serie.data}
        onRetry={serie.refetch}
        empty={null}
      >
        {serie.data && <NoTempo d={serie.data} />}
      </Async>

      <Async
        loading={pontos.loading}
        error={pontos.error}
        data={pontos.data}
        onRetry={pontos.refetch}
        empty={null}
      >
        {pontos.data && <Concentracao d={pontos.data} />}
      </Async>
    </div>
  )
}

/**
 * A faixa de agora — o que está acontecendo neste instante.
 *
 * Separada do resto porque é de natureza diferente: os números da série são de
 * uma janela fechada, estes são do momento. Misturá-los num mesmo bloco faria
 * "3 ativas" parecer um total do mês.
 */
export function AgoraMesmo({ d }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Agora</h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        Estado do eletroposto neste instante. Os blocos abaixo são da janela escolhida.
      </p>
      <div className="grid grid-4" style={{ gap: 12 }}>
        <Numero rotulo="Recargas em curso" valor={String(d.active ?? 0)} />
        <Numero rotulo="Na fila" valor={String(d.queued ?? 0)} />
        <Numero rotulo="Sessões hoje" valor={String(d.today ?? 0)} />
        <Numero rotulo="A receber" valor={comoReais(d.pending_revenue)} nota="faturas em aberto" />
      </div>
    </div>
  )
}

/**
 * A evolução no tempo. É o motivo de a aba existir.
 */
export function NoTempo({ d }) {
  const serie = d.serie ?? []
  const totais = d.totais ?? {}
  const varReceita = tendencia(serie, 'receita_brl')
  const varEnergia = tendencia(serie, 'energia_kwh')

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>
        No tempo — {d.desde && diaCurto(d.desde)} a {d.ate && diaCurto(d.ate)}
      </h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        Cada barra é um dia, no fuso do ponto ({d.timezone}). Dia parado aparece com zero — não é
        omitido, senão a linha passaria reta por cima da queda.
      </p>

      {/* A janela pedida pode ser maior que a idade do ponto. Dizer isso é o
          que impede a média diária de ser lida como desempenho ruim. */}
      {d.janela_completa === false && (
        <div className="async-error compact" role="status" style={{ marginBottom: 12 }}>
          Este ponto é mais novo que a janela pedida. A série cobre {d.dias_na_serie} dia(s), e as
          médias usam esse período — não os {d.dias} pedidos.
        </div>
      )}

      <div className="grid grid-4" style={{ gap: 12, marginBottom: 16 }}>
        <Numero
          rotulo="Receita recebida"
          valor={comoReais(totais.receita_brl)}
          variacao={varReceita}
        />
        <Numero
          rotulo="A receber"
          valor={comoReais(totais.a_receber_brl)}
          nota="ainda não entrou no caixa"
        />
        <Numero
          rotulo="Energia entregue"
          valor={comoKwh(totais.energia_kwh)}
          variacao={varEnergia}
        />
        <Numero
          rotulo="Ticket médio"
          valor={comoReais(totais.ticket_medio_brl)}
          nota={`${totais.sessoes ?? 0} sessões`}
        />
      </div>

      <Barras
        serie={serie}
        campo="receita_brl"
        titulo="Receita por dia"
        formatar={comoReais}
        cor="var(--sems-green)"
      />
      <Barras
        serie={serie}
        campo="energia_kwh"
        titulo="Energia por dia"
        formatar={comoKwh}
        cor="var(--sems-blue)"
      />

      {/* Percentual verde é da janela inteira, não por dia: o número diário
          oscila com pouca amostra e sugeriria uma variação que é só ruído. */}
      <p className="muted" style={{ fontSize: 12, margin: '12px 0 0' }}>
        {totais.verde_pct > 0
          ? `${totais.verde_pct}% da energia da janela veio de geração solar (${comoKwh(totais.verde_kwh)}).`
          : 'Sem energia de origem solar registrada nesta janela.'}
      </p>
    </div>
  )
}

/**
 * Gráfico de barras de um campo da série.
 *
 * `role="img"` com `aria-label` somando o período: leitor de tela não lê SVG de
 * barras, e sem isto o bloco inteiro seria silêncio. Não substitui o gráfico —
 * dá a mesma conclusão por outro caminho.
 */
function Barras({ serie, campo, titulo, formatar, cor }) {
  if (!serie.length) return null
  const topo = topoDaEscala(serie, campo)
  const largura = 100 / serie.length
  const indices = rotulosDoEixo(serie)
  const total = serie.reduce((t, d) => t + Number(d[campo] ?? 0), 0)

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 6
        }}
      >
        <span style={{ fontSize: 13 }}>{titulo}</span>
        <span className="muted" style={{ fontSize: 12 }}>
          pico {formatar(topo)}
        </span>
      </div>
      <div style={{ height: 120 }}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%' }}
          role="img"
          aria-label={`${titulo}: ${formatar(total)} no período, pico de ${formatar(topo)} em um dia`}
        >
          {serie.map((dia, i) => {
            const valor = Number(dia[campo] ?? 0)
            const h = Math.max(0, Math.min(100, (valor / topo) * 100))
            return (
              <rect
                key={dia.dia}
                x={i * largura + largura * 0.15}
                y={100 - h}
                width={largura * 0.7}
                height={h}
                fill={cor}
                opacity={valor > 0 ? 0.75 : 0.18}
              >
                <title>{`${diaCurto(dia.dia)}: ${formatar(valor)}`}</title>
              </rect>
            )
          })}
        </svg>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        {indices.map((i) => (
          <span key={i} className="muted" style={{ fontSize: 10 }}>
            {diaCurto(serie[i].dia)}
          </span>
        ))}
      </div>
    </div>
  )
}

/**
 * De onde vem a receita — e o quanto ela depende de um ponto só.
 *
 * A pergunta não é "qual rende mais" (a aba de Ocupação já responde): é
 * concentração. Um ponto que responde por metade da receita é um risco de
 * operação, porque um defeito nele derruba metade do faturamento.
 */
export function Concentracao({ d }) {
  const fatias = participacao(d.pontos ?? [], 'receita_brl')
  if (!fatias.length) {
    return (
      <div className="card">
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Concentração da receita</h3>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Nenhuma receita registrada nesta janela — nada a concentrar ainda.
        </p>
      </div>
    )
  }

  const lider = fatias[0]
  const cores = ['var(--sems-green)', 'var(--sems-blue)', 'var(--sems-yellow)', 'var(--sems-muted)']

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Concentração da receita</h3>
      <p className="muted" style={{ margin: '0 0 12px', fontSize: 13 }}>
        Quanto do faturamento depende de cada ponto. A aba Ocupação &amp; Retorno diz qual rende
        mais; aqui a pergunta é outra — o que acontece se um deles parar.
      </p>

      <div
        style={{ display: 'flex', height: 26, borderRadius: 6, overflow: 'hidden', gap: 2 }}
        role="img"
        aria-label={`${lider.code} responde por ${lider.pct.toFixed(0)}% da receita da janela`}
      >
        {fatias.map((f, i) => (
          <div
            key={f.code}
            style={{
              width: `${f.pct}%`,
              background: cores[i % cores.length],
              opacity: 0.8
            }}
            title={`${f.code}: ${comoReais(f.valor)} (${f.pct.toFixed(1)}%)`}
          />
        ))}
      </div>

      <table className="table" style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th>Ponto</th>
            <th style={{ textAlign: 'right' }}>Receita</th>
            <th style={{ textAlign: 'right' }}>Fatia</th>
          </tr>
        </thead>
        <tbody>
          {fatias.map((f, i) => (
            <tr key={f.code}>
              <td>
                <span
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    borderRadius: 2,
                    marginRight: 8,
                    background: cores[i % cores.length]
                  }}
                />
                {f.code}
              </td>
              <td style={{ textAlign: 'right' }}>{comoReais(f.valor)}</td>
              <td style={{ textAlign: 'right' }}>{f.pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      {lider.pct >= 50 && (
        <p className="muted" style={{ fontSize: 12, margin: '12px 0 0' }}>
          {lider.code} sozinho responde por {lider.pct.toFixed(0)}% da receita. Uma falha nele
          derruba metade do faturamento da janela.
        </p>
      )}
    </div>
  )
}

/** Um número da faixa executiva, com a variação quando ela existe. */
function Numero({ rotulo, valor, nota, variacao }) {
  const sobe = variacao != null && variacao > 0
  return (
    <div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}>
        {rotulo}
      </div>
      <div style={{ fontSize: 20, fontWeight: 600 }}>{valor}</div>
      {variacao != null && (
        <div
          style={{ fontSize: 12, color: sobe ? 'var(--sems-green)' : 'var(--sems-red)' }}
          title="Segunda metade da janela contra a primeira"
        >
          {sobe ? '▲' : '▼'} {Math.abs(variacao).toFixed(1)}% na 2ª metade
        </div>
      )}
      {nota && !variacao && (
        <div className="muted" style={{ fontSize: 11 }}>
          {nota}
        </div>
      )}
    </div>
  )
}
