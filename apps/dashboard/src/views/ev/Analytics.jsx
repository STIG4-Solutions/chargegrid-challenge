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
import { useAuth } from '../../auth/AuthContext.jsx'
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
import {
  JANELAS_DE_PREVISAO,
  rotuloDaFonte,
  rotuloDoBucket,
  temFaixaNaSerie,
  topoDaSerie,
  totaisDaSerie
} from './janelas.js'

const JANELAS = [
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
  { dias: 90, rotulo: '90 dias' }
]

export default function Analytics() {
  const { isAdmin } = useAuth()
  const [dias, setDias] = useState(30)
  const [janela, setJanela] = useState('dia')
  const [escopo, setEscopo] = useState('praca')
  const serie = useApi(() => power.dailyAnalytics(dias), [dias], { pollMs: 300000 })
  // Uma hora de poll: quem escreve e' um job que roda fora da API, e nao adianta
  // perguntar de minuto em minuto por um numero que muda uma vez por dia.
  const previsao = useApi(
    () =>
      escopo === 'rede' ? power.energyForecastNetwork(janela) : power.energyForecastSeries(janela),
    [janela, escopo],
    { pollMs: 3600000 }
  )
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
        loading={previsao.loading}
        error={previsao.error}
        data={previsao.data}
        onRetry={previsao.refetch}
        empty={null}
      >
        {previsao.data && (
          <Previsao
            d={previsao.data}
            janela={janela}
            onJanela={setJanela}
            escopo={escopo}
            onEscopo={setEscopo}
            podeVerRede={isAdmin}
          />
        )}
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

/**
 * A previsão nas cinco janelas: hora, dia, semana, mês e ano.
 *
 * O seletor é separado do de cima de propósito. O da janela de ANÁLISE recorta o
 * passado — 7, 30, 90 dias medidos. Este recorta o FUTURO, e misturar os dois num
 * controle só faria "30 dias" significar duas coisas na mesma tela.
 *
 * Cada janela diz DE ONDE veio o número. Não é rodapé: quatro das cinco são
 * servidas por régua sem modelo, porque a folga medida entre a melhor régua e o
 * ruído irredutível é de −0,05 ponto na hora e +3,38 no mês. Onde a folga é zero,
 * nenhum modelo pode ganhar — e a tela precisa dizer que aquilo é uma média, não
 * uma previsão, senão o operador contrata demanda pelo número errado.
 */
export function Previsao({ d, janela, onJanela, escopo = 'praca', onEscopo, podeVerRede = false }) {
  const escolhida = JANELAS_DE_PREVISAO.find((j) => j.chave === janela)

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 12
        }}
      >
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Previsão</h3>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            {escolhida?.pergunta ?? 'O que vem pela frente'} — calculada fora da API.
          </p>
        </div>
        <div role="group" aria-label="Janela de previsão" style={{ display: 'flex', gap: 6 }}>
          {JANELAS_DE_PREVISAO.map((j) => (
            <button
              key={j.chave}
              className={janela === j.chave ? 'btn btn-primary btn-sm' : 'btn btn-sm'}
              aria-pressed={janela === j.chave}
              onClick={() => onJanela(j.chave)}
            >
              {j.rotulo}
            </button>
          ))}
        </div>
      </div>

      {podeVerRede && (
        <div style={{ marginBottom: 12 }}>
          <div role="group" aria-label="Escopo da previsão" style={{ display: 'flex', gap: 6 }}>
            {[
              { chave: 'praca', rotulo: 'Esta praça' },
              { chave: 'rede', rotulo: 'Rede inteira' }
            ].map((e) => (
              <button
                key={e.chave}
                className={escopo === e.chave ? 'btn btn-primary btn-sm' : 'btn btn-sm'}
                aria-pressed={escopo === e.chave}
                onClick={() => onEscopo?.(e.chave)}
              >
                {e.rotulo}
              </button>
            ))}
          </div>
          {escopo === 'rede' && (
            <p className="muted" style={{ margin: '6px 0 0', fontSize: 12, lineHeight: 1.5 }}>
              Soma de todas as praças, e só administrador vê. Com poucas praças, um total da rede
              permite inferir o movimento das outras — com duas, por subtração exata. É também o
              único escopo em que a janela de hora tem densidade: a célula hora×praça tem 20% de
              ocupação, contra 54% da rede.
            </p>
          )}
        </div>
      )}

      {!d.disponivel ? (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {d.motivo}
        </p>
      ) : (
        <SeriePrevista d={d} janela={janela} />
      )}
    </div>
  )
}

function SeriePrevista({ d, janela }) {
  const buckets = Array.isArray(d.buckets) ? d.buckets : []
  if (!buckets.length) return null

  // O fuso em que os buckets foram CONTADOS, declarado pela API. Sem ele o
  // navegador rotularia o eixo no fuso de quem olha, deslocando a curva do dia -
  // e a curva do dia e' o que da' sentido a janela horaria.
  const fuso = d.timezone || 'UTC'
  const fonte = rotuloDaFonte(buckets[0]?.fonte)
  const totais = totaisDaSerie(buckets)
  const comFaixa = temFaixaNaSerie(buckets)

  return (
    <div>
      <div className="grid grid-3" style={{ gap: 12, marginBottom: 14 }}>
        <Numero rotulo={`Energia prevista (${buckets.length})`} valor={comoKwh(totais.kwh)} />
        <Numero
          rotulo="Faturamento previsto"
          valor={totais.brl == null ? '—' : comoReais(totais.brl)}
          nota={
            totais.brl == null
              ? 'não calculado para a rede: somar praças com tarifas diferentes daria um preço que não existe em contrato'
              : undefined
          }
        />
        <Numero
          rotulo="Base de cálculo"
          valor={fonte.eModelo ? 'Modelo' : 'Régua'}
          nota={fonte.texto}
        />
      </div>

      {!fonte.eModelo && (
        <p className="muted" style={{ margin: '0 0 12px', fontSize: 12, lineHeight: 1.5 }}>
          Este número vem de <strong>{fonte.texto}</strong>, não do modelo. Nesta janela a régua
          mede igual ou melhor que ele — o erro que sobra é variação de contagem, que modelo nenhum
          remove. O modelo continua treinado e volta sozinho quando passar a medir melhor.
        </p>
      )}

      {comFaixa ? (
        <Faixa buckets={buckets} janela={janela} fuso={fuso} />
      ) : (
        <BarrasPrevistas buckets={buckets} janela={janela} fuso={fuso} />
      )}

      {comFaixa && (
        <p className="muted" style={{ margin: '8px 0 0', fontSize: 12, lineHeight: 1.5 }}>
          A área clara é a faixa p10–p90{' '}
          {d.cobertura_medida_pct != null &&
            `— no teste ela conteve o valor real em ${Number(d.cobertura_medida_pct).toFixed(0)}% dos casos`}
          . Nesta janela o valor de uma hora isolada é dominado por variação de contagem: a faixa é
          a resposta honesta, e a linha é só o centro dela.
        </p>
      )}
    </div>
  )
}

/**
 * A curva com a faixa de incerteza em volta.
 *
 * Usada só onde a série declara p10 e p90 — hoje, a janela de hora. A área vem
 * ANTES da linha no SVG de propósito: desenhada depois, cobriria a linha que ela
 * deveria emoldurar.
 */
export function Faixa({ buckets, janela, fuso = 'UTC' }) {
  const topo = topoDaSerie(buckets)
  const n = buckets.length
  const x = (i) => (n === 1 ? 50 : (i / (n - 1)) * 100)
  const y = (v) => 100 - Math.max(0, Math.min(100, (Number(v ?? 0) / topo) * 100))

  const alto = buckets.map((b, i) => `${x(i)},${y(b.kwh_p90)}`)
  const baixo = buckets.map((b, i) => `${x(i)},${y(b.kwh_p10)}`).reverse()
  const linha = buckets.map((b, i) => `${x(i)},${y(b.kwh_previsto)}`).join(' ')
  const indices = rotulosDoEixo(buckets, 6)
  const totais = totaisDaSerie(buckets)

  return (
    <div>
      <div style={{ height: 140 }}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%' }}
          role="img"
          aria-label={`Previsão por ${janela}: ${comoKwh(totais.kwh)} no total, com faixa de incerteza`}
        >
          <polygon points={[...alto, ...baixo].join(' ')} fill="var(--sems-blue)" opacity="0.18" />
          <polyline
            points={linha}
            fill="none"
            stroke="var(--sems-blue)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <EixoDeBuckets buckets={buckets} indices={indices} janela={janela} fuso={fuso} />
    </div>
  )
}

/** A previsão em barras, para as janelas sem faixa. Mesmo idioma de `Barras`. */
export function BarrasPrevistas({ buckets, janela, fuso = 'UTC' }) {
  const topo = topoDaSerie(buckets)
  const largura = 100 / buckets.length
  const indices = rotulosDoEixo(buckets, 6)
  const totais = totaisDaSerie(buckets)

  return (
    <div>
      <div style={{ height: 140 }}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%' }}
          role="img"
          aria-label={`Previsão por ${janela}: ${comoKwh(totais.kwh)} no total`}
        >
          {buckets.map((b, i) => {
            const valor = Number(b.kwh_previsto ?? 0)
            const h = Math.max(0, Math.min(100, (valor / topo) * 100))
            return (
              <rect
                key={b.bucket_inicio}
                x={i * largura + largura * 0.15}
                y={100 - h}
                width={largura * 0.7}
                height={h}
                fill="var(--sems-blue)"
                opacity={valor > 0 ? 0.75 : 0.18}
              >
                <title>{`${rotuloDoBucket(b.bucket_inicio, janela, fuso)}: ${comoKwh(valor)}`}</title>
              </rect>
            )
          })}
        </svg>
      </div>
      <EixoDeBuckets buckets={buckets} indices={indices} janela={janela} fuso={fuso} />
    </div>
  )
}

function EixoDeBuckets({ buckets, indices, janela, fuso = 'UTC' }) {
  return (
    <div style={{ display: 'flex', marginTop: 4 }}>
      {buckets.map((b, i) => (
        <span
          key={b.bucket_inicio}
          className="muted"
          style={{
            flex: 1,
            fontSize: 10,
            textAlign: 'center',
            whiteSpace: 'nowrap',
            visibility: indices.includes(i) ? 'visible' : 'hidden'
          }}
        >
          {rotuloDoBucket(b.bucket_inicio, janela, fuso)}
        </span>
      ))}
    </div>
  )
}
