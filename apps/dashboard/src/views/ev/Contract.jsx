import { useState } from 'react'
import { brl, num, platform, useAction, useApi } from '@chargegrid/sdk'

import { Async } from '../../components/Async.jsx'
import { mesesRestantes, multaPorRescisao } from './contrato.js'

const ESTADOS = {
  ativa: { rotulo: 'Ativo', classe: 'badge-green' },
  em_aviso_previo: { rotulo: 'Em aviso prévio', classe: 'badge-yellow' },
  inadimplente: { rotulo: 'Inadimplente', classe: 'badge-red' },
  encerrada: { rotulo: 'Encerrado', classe: 'badge-gray' }
}

const COBRANCAS = {
  aberta: { rotulo: 'Em aberto', classe: 'badge-yellow' },
  // Vencida é vermelho, e não amarelo como "em aberto": a diferença entre uma
  // cobrança de ontem e uma de três meses atrás é a informação toda.
  vencida: { rotulo: 'Vencida', classe: 'badge-red' },
  paga: { rotulo: 'Paga', classe: 'badge-green' },
  cancelada: { rotulo: 'Cancelada', classe: 'badge-gray' }
}

/**
 * A dívida em atraso, no topo da tela.
 *
 * Vai no topo e não no rodapé da lista de cobranças: é a única informação desta
 * aba que pede ação hoje. E diz a CONSEQUÊNCIA — parar de renovar — porque um
 * aviso vermelho que não explica o efeito vira enfeite que ninguém lê duas
 * vezes.
 *
 * Diz também o que NÃO acontece, de propósito: ninguém fica sem recarregar.
 * Quem deixou de pagar foi o estabelecimento, e cortar o serviço puniria o
 * motorista. Sem essa frase a primeira reação do operador é achar que os pontos
 * pararam.
 *
 * Exportado para o teste montá-lo com props, sem subir a aba inteira.
 */
export function AvisoDeAtraso({ atraso }) {
  if (!(atraso?.cobrancas > 0)) return null
  const quantas =
    atraso.cobrancas === 1 ? '1 cobrança vencida' : `${atraso.cobrancas} cobranças vencidas`
  return (
    <div className="async-error" role="alert" style={{ marginTop: 16 }}>
      <div>
        <strong>
          {quantas} — {brl(atraso.total_brl)}
        </strong>
        <p className="muted">
          A mais antiga venceu em {new Date(`${atraso.desde}T12:00:00`).toLocaleDateString('pt-BR')}
          . Enquanto houver cobrança vencida o contrato não renova sozinho. As recargas continuam
          funcionando normalmente.
        </p>
      </div>
    </div>
  )
}

function Stat({ rotulo, valor, nota, destaque }) {
  return (
    <div className="stat">
      <div className="label">{rotulo}</div>
      <div className="value" style={destaque ? { color: 'var(--sems-red)' } : undefined}>
        {valor}
      </div>
      {nota && <div className="trend muted">{nota}</div>}
    </div>
  )
}

function Planos({ aoContratar }) {
  const planos = useApi(() => platform.plans(), [])
  const contratar = useAction((codigo) => platform.subscribe(codigo), { onSuccess: aoContratar })

  return (
    <Async
      loading={planos.loading}
      error={planos.error}
      data={planos.data}
      onRetry={planos.refetch}
    >
      {planos.data && (
        <div className="grid grid-2">
          {planos.data.map((p) => (
            <div className="card" key={p.codigo}>
              <div className="card-title">{p.nome}</div>
              <div className="card-sub">{p.descricao}</div>
              <div className="kv" style={{ marginTop: 12 }}>
                <div>
                  <span className="muted">Mensalidade</span>
                  <span>{brl(p.preco_mensal_brl)}</span>
                </div>
                <div>
                  <span className="muted">Pontos inclusos</span>
                  <span>
                    {num(p.pontos_inclusos, 0)} · {brl(p.preco_por_ponto_brl)} por ponto extra
                  </span>
                </div>
                <div>
                  <span className="muted">Taxa por transação</span>
                  <span>{num(p.fee_percent_transacao, 2)}% do que você fatura</span>
                </div>
                <div>
                  <span className="muted">Fidelidade</span>
                  <span>{num(p.meses_minimos, 0)} meses</span>
                </div>
              </div>
              <button
                className="btn btn-primary"
                style={{ marginTop: 12 }}
                disabled={contratar.pending}
                onClick={() => contratar.run(p.codigo)}
              >
                Contratar {p.nome}
              </button>
            </div>
          ))}
          {contratar.error && <div className="async-error compact">{contratar.error.detail}</div>}
        </div>
      )}
    </Async>
  )
}

/**
 * A lista de cobranças. Exportada pelo mesmo motivo de `AvisoDeAtraso`.
 *
 * O `?? COBRANCAS.aberta` da linha abaixo é um fallback gracioso — não quebra a
 * tela com um estado que o painel ainda não conhece. O preço é que ele MENTE em
 * silêncio: uma cobrança vencida há três meses apareceria em amarelo, idêntica
 * à emitida ontem. `contrato-card.test.jsx` trava isso.
 */
export function Cobrancas({ linhas, aoDarBaixa }) {
  const baixar = useAction((id) => platform.settle(id), { onSuccess: aoDarBaixa })

  if (!linhas.length) {
    return <div className="muted">Nenhuma cobrança emitida ainda.</div>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table" style={{ minWidth: 780 }}>
        <thead>
          <tr>
            <th>Competência</th>
            <th className="text-right">Mensalidade</th>
            <th className="text-right">Pontos</th>
            <th className="text-right">Transação</th>
            <th className="text-right">Multa</th>
            <th className="text-right">Total</th>
            <th>Situação</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {linhas.map((c) => {
            const situacao = COBRANCAS[c.estado] ?? COBRANCAS.aberta
            return (
              <tr key={c.id}>
                <td>
                  {new Date(`${c.competencia}T12:00:00`).toLocaleDateString('pt-BR', {
                    month: 'short',
                    year: 'numeric'
                  })}
                  <div className="muted" style={{ fontSize: 12 }}>
                    vence {new Date(`${c.vence_em}T12:00:00`).toLocaleDateString('pt-BR')}
                  </div>
                  {/*
                    A lista tem escopo de SITE, então pode misturar contratos —
                    é o que impede a dívida de sumir quando o site assina de
                    novo. Sem esta marca, uma cobrança herdada pareceria do
                    contrato que está correndo, e duas competências iguais de
                    contratos diferentes ficariam indistinguíveis.
                  */}
                  {c.contrato_anterior && (
                    <div className="muted" style={{ fontSize: 12 }}>
                      contrato anterior
                    </div>
                  )}
                </td>
                <td className="text-right">{brl(c.assinatura_brl)}</td>
                <td className="text-right">
                  {brl(c.pontos_brl)}
                  {c.pontos_cobrados > 0 && (
                    <div className="muted" style={{ fontSize: 12 }}>
                      {num(c.pontos_cobrados, 0)} pontos
                    </div>
                  )}
                </td>
                <td className="text-right">
                  {brl(c.transacao_brl)}
                  {c.faturamento_base_brl > 0 && (
                    <div className="muted" style={{ fontSize: 12 }}>
                      sobre {brl(c.faturamento_base_brl)}
                    </div>
                  )}
                </td>
                <td className="text-right">{c.multa_brl > 0 ? brl(c.multa_brl) : '—'}</td>
                <td className="text-right">
                  <strong>{brl(c.total_brl)}</strong>
                </td>
                <td>
                  <span className={`badge ${situacao.classe}`}>{situacao.rotulo}</span>
                </td>
                <td className="text-right">
                  {c.estado === 'aberta' && (
                    <button
                      className="btn btn-sm"
                      disabled={baixar.pending}
                      onClick={() => baixar.run(c.id)}
                    >
                      Marcar como paga
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {baixar.error && <div className="async-error compact">{baixar.error.detail}</div>}
    </div>
  )
}

function Contrato({ d, aoMudar }) {
  const [confirmando, setConfirmando] = useState(false)
  const rescindir = useAction(() => platform.terminate(), {
    onSuccess: () => {
      setConfirmando(false)
      aoMudar()
    }
  })

  const situacao = ESTADOS[d.estado] ?? ESTADOS.ativa
  // Recalculado na tela para o operador ver o número enquanto ainda está
  // pensando. O servidor continua sendo a autoridade — mas descobrir a multa
  // depois de confirmar é a diferença entre uma decisão e uma surpresa.
  const restantes = mesesRestantes(new Date(), d.minimo_ate)
  const multa = multaPorRescisao(d.plano.preco_mensal_brl, restantes, d.multa_percentual)

  return (
    <>
      <div className="panel">
        <div className="flex items-center gap-16" style={{ justifyContent: 'space-between' }}>
          <div>
            <div className="card-title">
              {d.plano.nome} <span className={`badge ${situacao.classe}`}>{situacao.rotulo}</span>
            </div>
            <div className="card-sub">
              Mensalidade de {brl(d.plano.preco_mensal_brl)} mais{' '}
              {num(d.plano.fee_percent_transacao, 2)}% sobre o que você fatura.
            </div>
          </div>
        </div>

        <AvisoDeAtraso atraso={d.em_atraso} />

        <div className="grid grid-4" style={{ marginTop: 16 }}>
          <Stat
            rotulo="Fidelidade até"
            valor={new Date(`${d.minimo_ate}T12:00:00`).toLocaleDateString('pt-BR')}
            nota={restantes > 0 ? `faltam ${restantes} meses` : 'prazo cumprido'}
          />
          <Stat
            rotulo="Próxima renovação"
            valor={new Date(`${d.renova_em}T12:00:00`).toLocaleDateString('pt-BR')}
            nota={d.encerra_em ? `encerra em ${d.encerra_em}` : 'renova automaticamente'}
          />
          <Stat
            rotulo="Pontos inclusos"
            valor={num(d.plano.pontos_inclusos, 0)}
            nota={`${brl(d.plano.preco_por_ponto_brl)} por ponto extra`}
          />
          <Stat
            rotulo="Multa se sair hoje"
            valor={multa > 0 ? brl(multa) : '—'}
            nota={
              restantes > 0
                ? `${num(d.multa_percentual, 0)}% de ${restantes} mensalidades`
                : 'sem multa: prazo cumprido'
            }
            destaque={multa > 0}
          />
        </div>

        {d.estado === 'ativa' &&
          (confirmando ? (
            <div className="async-error compact" style={{ marginTop: 16 }}>
              <div style={{ marginBottom: 8 }}>
                {multa > 0 ? (
                  <>
                    Rescindir agora gera uma cobrança de <strong>{brl(multa)}</strong> — são{' '}
                    {num(d.multa_percentual, 0)}% das {restantes} mensalidades que faltam para o fim
                    da fidelidade. O serviço continua até{' '}
                    {new Date(`${d.renova_em}T12:00:00`).toLocaleDateString('pt-BR')}.
                  </>
                ) : (
                  <>
                    A fidelidade já foi cumprida: não há multa. O serviço continua até{' '}
                    {new Date(`${d.renova_em}T12:00:00`).toLocaleDateString('pt-BR')}.
                  </>
                )}
              </div>
              <div className="flex gap-12">
                <button
                  className="btn btn-primary"
                  disabled={rescindir.pending}
                  onClick={() => rescindir.run()}
                >
                  {rescindir.pending ? 'Processando…' : 'Confirmar rescisão'}
                </button>
                <button className="btn" onClick={() => setConfirmando(false)}>
                  Manter contrato
                </button>
              </div>
            </div>
          ) : (
            <button className="btn" style={{ marginTop: 16 }} onClick={() => setConfirmando(true)}>
              Rescindir contrato
            </button>
          ))}
        {rescindir.error && (
          <div className="async-error compact" style={{ marginTop: 12 }}>
            {rescindir.error.detail}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="card-title">Cobranças</div>
        {/* Declarado, e não escondido: não há integração bancária. Uma cobrança
            que parecesse liquidada sem liquidação seria pior que a limitação. */}
        <div className="card-sub">
          A baixa é manual — não há liquidação automática. A GoodWe confirma o recebimento e marca a
          cobrança como paga.
        </div>
        <div style={{ marginTop: 16 }}>
          <Cobrancas linhas={d.cobrancas} aoDarBaixa={aoMudar} />
        </div>
      </div>
    </>
  )
}

/**
 * Contrato do estabelecimento com a plataforma.
 *
 * Dinheiro na direção oposta ao resto do painel: aqui é o estabelecimento que
 * paga a GoodWe. Por isso estas cobranças NÃO aparecem em nenhum relatório de
 * receita — elas moram em tabela própria.
 */
export default function Contract() {
  const contrato = useApi(() => platform.contract(), [], { pollMs: 300000 })
  const recarregar = () => contrato.refetch({ silent: true })

  return (
    <Async
      loading={contrato.loading}
      error={contrato.error}
      data={contrato.data}
      onRetry={contrato.refetch}
    >
      {contrato.data &&
        (contrato.data.contratado ? (
          <Contrato d={contrato.data} aoMudar={recarregar} />
        ) : (
          <div className="panel">
            <div className="card-title">Plano &amp; Contrato</div>
            <div className="card-sub">
              Este ponto ainda não tem contrato com a plataforma. Escolha um plano abaixo.
            </div>
            <div style={{ marginTop: 16 }}>
              <Planos aoContratar={recarregar} />
            </div>
          </div>
        ))}
    </Async>
  )
}
