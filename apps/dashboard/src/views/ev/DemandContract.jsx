import { brl, num, power, useApi } from '@chargegrid/sdk'
import { Async } from '../../components/Async.jsx'

/**
 * Demanda contratada: previsão de estouro e custo evitado.
 *
 * As outras telas falam de energia (kWh) — o que foi consumido. Esta fala de
 * demanda (kW) — o quanto se puxa no pico, que no Grupo A é contratado à parte
 * e faturado pela MAIOR média de 15 minutos do mês. Um pico de quinze minutos,
 * uma vez, define a conta inteira. Por isso avisar antes vale mais do que
 * relatar depois: depois de medido, já foi.
 */
export default function DemandContract() {
  const previsao = useApi(() => power.demandForecast(8), [], { pollMs: 60000 })
  const evitado = useApi(() => power.avoidedCost(30), [], { pollMs: 300000 })
  const contrato = useApi(() => power.contractSimulator(30), [], { pollMs: 600000 })

  return (
    <div>
      <Async
        loading={previsao.loading}
        error={previsao.error}
        data={previsao.data}
        onRetry={previsao.refetch}
      >
        {previsao.data && <Previsao d={previsao.data} />}
      </Async>

      <Async
        loading={evitado.loading}
        error={evitado.error}
        data={evitado.data}
        onRetry={evitado.refetch}
      >
        {evitado.data && <Evitado d={evitado.data} />}
      </Async>

      <Async
        loading={contrato.loading}
        error={contrato.error}
        data={contrato.data}
        onRetry={contrato.refetch}
      >
        {contrato.data && <Simulador d={contrato.data} />}
      </Async>
    </div>
  )
}

function Previsao({ d }) {
  const alerta = d.risco
  const hora = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })

  return (
    <>
      <div className={'card' + (alerta ? ' card-alert' : '')} style={{ marginBottom: 16 }}>
        <div className="flex" style={{ justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>
              {alerta ? '⚠ Risco de ultrapassar a demanda contratada' : 'Demanda projetada dentro do contrato'}
            </h2>
            <p className="muted" style={{ margin: '4px 0 0', fontSize: 13 }}>
              {alerta
                ? `Projeção passa de ${num(d.teto_com_tolerancia_kw, 1)} kW às ${hora(d.primeiro_estouro_em)}. Reduzir o teto dos pontos agora evita a penalidade do mês.`
                : `Pico projetado de ${num(d.pico_previsto_kw, 1)} kW nas próximas horas, com folga de ${num(d.margem_kw, 1)} kW.`}
            </p>
          </div>
          <span className="muted" style={{ fontSize: 12 }}>
            perfil de {d.dias_de_historico} dia(s) · janelas de 15 min
          </span>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Stat rotulo="Demanda contratada" valor={`${num(d.contratada_kw, 1)} kW`} nota="do contrato com a distribuidora" />
        <Stat rotulo="Teto com tolerância" valor={`${num(d.teto_com_tolerancia_kw, 1)} kW`} nota="5% antes de caracterizar ultrapassagem" />
        <Stat rotulo="Pico projetado" valor={`${num(d.pico_previsto_kw, 1)} kW`} nota="próximas 8 horas" destaque={alerta} />
        <Stat rotulo="Carga EV agora" valor={`${num(d.ev_atual_kw, 1)} kW`} nota="mantida fixa na projeção" />
      </div>

      <Curva d={d} />
    </>
  )
}

function Stat({ rotulo, valor, nota, destaque }) {
  return (
    <div className="stat">
      <div className="label">{rotulo}</div>
      <div className="value" style={destaque ? { color: 'var(--sems-red)' } : undefined}>{valor}</div>
      <div className="trend muted">{nota}</div>
    </div>
  )
}

/**
 * A curva projetada, em barras.
 *
 * SVG inline em vez de biblioteca de gráfico: são 32 barras e uma linha de
 * limite. Uma dependência a mais no bundle custaria mais do que entrega, e o
 * eixo aqui tem significado fixo — a escala é o contrato, não os dados.
 */
function Curva({ d }) {
  const fatias = d.fatias || []
  if (!fatias.length) return null

  const teto = d.teto_com_tolerancia_kw
  // A escala vai até o maior entre o teto e o pico: a linha do limite nunca sai
  // do desenho, e um estouro aparece como barra ultrapassando ela.
  //
  // Barras curtas quando há folga não são defeito — são a informação: o
  // operador vê de relance o quanto sobra. Comprimir a escala até os dados
  // deixaria o desenho bonito e mentiria sobre a margem.
  const topo = Math.max(teto, d.pico_previsto_kw) * 1.15
  const largura = 100 / fatias.length

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Projeção das próximas horas</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        Cada barra é uma janela de 15 minutos — a mesma que a distribuidora usa para faturar.
        O prédio segue o perfil típico do horário; a carga dos carros é mantida no valor de agora.
      </p>

      <div style={{ position: 'relative', height: 180, marginBottom: 8 }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
          {fatias.map((f, i) => {
            const h = Math.min(100, (f.demanda_prevista_kw / topo) * 100)
            return (
              <rect
                key={f.inicio}
                x={i * largura + largura * 0.15}
                y={100 - h}
                width={largura * 0.7}
                height={h}
                fill={f.excede ? 'var(--sems-red)' : 'var(--sems-green, #4cd268)'}
                opacity={f.excede ? 0.95 : 0.55}
              />
            )
          })}
          <line
            x1="0" x2="100"
            y1={100 - (teto / topo) * 100}
            y2={100 - (teto / topo) * 100}
            stroke="var(--sems-red)"
            strokeWidth="0.6"
            strokeDasharray="2 1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <span className="muted" style={{ position: 'absolute', right: 0, top: `${Math.max(0, 100 - (teto / topo) * 100 - 8)}%`, fontSize: 11 }}>
          limite {num(teto, 1)} kW
        </span>
      </div>

      <div className="flex" style={{ justifyContent: 'space-between', fontSize: 11 }}>
        <span className="muted">{new Date(fatias[0].inicio).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
        <span className="muted">{new Date(fatias[fatias.length - 1].inicio).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
    </div>
  )
}

/**
 * Custo evitado: o mesmo histórico, com e sem rateio.
 *
 * O contrafactual é conservador de propósito — pega exatamente as sessões que
 * existiram e devolve a cada ponto a potência nominal dele. Não supõe mais
 * carros nem sessões mais longas. É o que teria acontecido num eletroposto sem
 * controle de demanda, que é a lacuna que o projeto se propõe a cobrir.
 */
function Evitado({ d }) {
  const semTarifa = !d.tarifa_configurada
  const houveGanho = d.evitado_brl > 0

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Custo evitado nos últimos 30 dias</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        {d.janelas_analisadas} janelas de 15 minutos analisadas. A comparação usa o mesmo histórico:
        de um lado o que o medidor registrou, de outro o que teria sido se cada ponto ocupado
        tivesse puxado a potência nominal, sem teto.
      </p>

      {semTarifa ? (
        <p className="muted" style={{ fontSize: 13 }}>
          Sem a tarifa de demanda do contrato, o resultado sai em kW e não em reais.
          Informe <code>demand_tariff_brl_per_kw</code> no cadastro do site para ver o valor.
        </p>
      ) : (
        <div className="grid grid-3" style={{ marginBottom: 16 }}>
          <Stat
            rotulo="Evitado no período"
            valor={brl(d.evitado_brl)}
            nota={houveGanho ? 'penalidade que não entrou na conta' : 'não houve ultrapassagem a evitar'}
            destaque={houveGanho}
          />
          <Stat rotulo="Custo real" valor={brl(d.custo_real_brl)} nota={`ultrapassagem de ${num(d.ultrapassagem_real_kw, 1)} kW`} />
          <Stat rotulo="Custo sem rateio" valor={brl(d.custo_sem_rateio_brl)} nota={`ultrapassagem de ${num(d.ultrapassagem_sem_rateio_kw, 1)} kW`} />
        </div>
      )}

        <table className="table">
          <thead>
            <tr><th>Cenário</th><th>Pico de demanda</th><th>Ultrapassagem</th><th>Penalidade</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Com rateio <span className="muted">(real)</span></td>
              <td>{num(d.pico_real_kw, 2)} kW</td>
              <td>{num(d.ultrapassagem_real_kw, 2)} kW</td>
              <td>{semTarifa ? '—' : brl(d.custo_real_brl)}</td>
            </tr>
            <tr>
              <td>Sem rateio <span className="muted">(contrafactual)</span></td>
              <td style={{ color: 'var(--sems-red)' }}>{num(d.pico_sem_rateio_kw, 2)} kW</td>
              <td>{num(d.ultrapassagem_sem_rateio_kw, 2)} kW</td>
              <td>{semTarifa ? '—' : brl(d.custo_sem_rateio_brl)}</td>
            </tr>
          </tbody>
        </table>

      <p className="muted" style={{ margin: '12px 0 0', fontSize: 12 }}>
        Demanda contratada de {num(d.contratada_kw, 1)} kW, com 5% de tolerância regulatória; o
        excedente é faturado ao dobro da tarifa. Maior pico do período em{' '}
        {d.momento_do_pico ? new Date(d.momento_do_pico).toLocaleString('pt-BR') : '—'}.
      </p>
    </div>
  )
}

/**
 * Simulador de contrato.
 *
 * Contratar demais paga folga o ano inteiro — o valor contratado é cobrado
 * tenha sido atingido ou não. Contratar de menos paga ultrapassagem ao dobro.
 * O mínimo dessa soma não é óbvio a olho, e a intuição erra para o lado caro:
 * contrata-se com folga por medo da penalidade.
 *
 * É uma conta que só quem tem a medição consegue fazer.
 */
function Simulador({ d }) {
  if (!d.opcoes?.length) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Simulador de contrato</h3>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Ainda não há medição suficiente no período para simular.
        </p>
      </div>
    )
  }

  const melhor = d.melhor_kw
  const vale = d.economia_mensal_brl > 0
  const maiorCusto = Math.max(...d.opcoes.map((o) => o.custo_total_brl))

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Simulador de contrato</h3>
      <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>
        {d.janelas_analisadas} janelas medidas em {d.dias} dias, pico de {num(d.pico_medido_kw, 1)} kW.
        Cada linha soma o custo fixo da demanda contratada com a penalidade de ultrapassagem que
        aquele contrato teria gerado sobre este mesmo histórico.
      </p>

      {!d.confiavel && (
        <p
          style={{
            margin: '0 0 16px',
            padding: '10px 12px',
            borderRadius: 6,
            border: '1px solid var(--aviso-borda, #d9a441)',
            background: 'var(--aviso-fundo, rgba(217, 164, 65, 0.12))',
            fontSize: 13,
          }}
        >
          <strong>Amostra insuficiente para decidir.</strong> A tarifa de demanda e cobrada pelo
          maior pico do mes, e {d.janelas_analisadas} de {d.janelas_minimas} janelas nao bastam
          para afirmar que esse pico ja apareceu. Reduzir a demanda contratada com base nisto
          arrisca pagar ultrapassagem ao dobro todo mes. Use os numeros abaixo como ordem de
          grandeza, nao como recomendacao.
        </p>
      )}

      {!d.tarifa_configurada ? (
        <p className="muted" style={{ fontSize: 13 }}>
          Informe a tarifa de demanda do contrato para ver os valores em reais.
        </p>
      ) : (
        <div className="grid grid-3" style={{ marginBottom: 16 }}>
          <Stat rotulo="Contrato atual" valor={`${num(d.atual_kw, 0)} kW`} nota={brl(d.custo_atual_brl) + ' por mês'} />
          <Stat rotulo="Melhor contrato" valor={`${num(melhor, 0)} kW`} nota={brl(d.custo_melhor_brl) + ' por mês'} />
          <Stat
            rotulo="Economia mensal"
            valor={brl(d.economia_mensal_brl)}
            nota={vale ? `${brl(d.economia_mensal_brl * 12)} por ano` : 'o contrato atual já é o melhor'}
            destaque={vale}
          />
        </div>
      )}

      <table className="table">
        <thead>
          <tr><th>Demanda</th><th>Custo fixo</th><th>Ultrapassagem</th><th>Total</th><th>Janelas excedidas</th></tr>
        </thead>
        <tbody>
          {d.opcoes.map((o) => {
            const ehMelhor = o.demanda_kw === melhor
            const ehAtual = Math.abs(o.demanda_kw - d.atual_kw) < 0.01
            return (
              <tr key={o.demanda_kw} style={ehMelhor ? { background: 'var(--sems-header-row)' } : undefined}>
                <td style={{ fontWeight: ehMelhor || ehAtual ? 600 : 400 }}>
                  {num(o.demanda_kw, 0)} kW
                  {ehMelhor && <span className="badge badge-green" style={{ marginLeft: 8 }}>melhor</span>}
                  {ehAtual && <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>atual</span>}
                </td>
                <td>{brl(o.custo_fixo_brl)}</td>
                <td style={o.custo_ultrapassagem_brl > 0 ? { color: 'var(--sems-red)' } : undefined}>
                  {brl(o.custo_ultrapassagem_brl)}
                </td>
                <td style={{ fontWeight: 600 }}>{brl(o.custo_total_brl)}</td>
                <td>
                  <span style={{ display: 'inline-block', width: 60, height: 4, background: 'var(--sems-border)', borderRadius: 2, marginRight: 8, verticalAlign: 'middle' }}>
                    <span style={{ display: 'block', width: `${(o.custo_total_brl / maiorCusto) * 100}%`, height: '100%', background: ehMelhor ? 'var(--sems-green, #4cd268)' : 'var(--sems-red)', borderRadius: 2 }} />
                  </span>
                  {o.janelas_excedidas}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <p className="muted" style={{ margin: '12px 0 0', fontSize: 12 }}>
        A ultrapassagem é calculada sobre o maior excedente do período, não sobre cada janela:
        uma vez que se estoura, o dano do mês está feito.
      </p>
    </div>
  )
}
