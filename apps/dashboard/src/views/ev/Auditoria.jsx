import { dateTime, admin, useApi } from '@chargegrid/sdk'

import { Async, Empty } from '../../components/Async.jsx'
import { comoTexto, mudancas, rotuloDaAcao } from './auditoria.js'

/**
 * Quem fez o que, com dinheiro e com permissão.
 *
 * A trilha era gravada e não tinha leitor: o dado existia no banco e a pergunta
 * continuava dependendo de alguém com acesso a produção. Esta aba é o leitor.
 *
 * Só aparece para admin, porque a rota é de admin — ela diz quem mexeu em quê e
 * de qual IP, e isso não é assunto de operador de praça.
 */
export default function Auditoria() {
  const trilha = useApi(() => admin.auditTrail(100), [], { pollMs: 60000 })

  return (
    <div>
      <div className="panel">
        <div className="card-title">Trilha de auditoria</div>
        <div className="card-sub">
          Ações de pessoas que mexem em dinheiro ou em permissão. O que os workers fazem sozinhos —
          cashback concedido, mensalidade cobrada — fica de fora: são consequências de regra, não
          decisões de alguém, e encheriam esta lista de linhas sem responsável.
        </div>
      </div>

      <Async
        loading={trilha.loading}
        error={trilha.error}
        data={trilha.data}
        onRetry={trilha.refetch}
        empty="Nenhuma ação registrada ainda."
      >
        {trilha.data && <Linhas linhas={trilha.data} />}
      </Async>
    </div>
  )
}

/** Exportado para o teste montar com props, sem subir a aba inteira. */
export function Linhas({ linhas }) {
  if (!linhas?.length) return <Empty label="Nenhuma ação registrada ainda." />

  return (
    <div className="card" style={{ marginTop: 16, overflowX: 'auto' }}>
      <table className="table" style={{ minWidth: 860 }}>
        <thead>
          <tr>
            <th>Quando</th>
            <th>Quem</th>
            <th>O que</th>
            <th>Mudou</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.id}>
              <td className="muted">{dateTime(l.quando)}</td>
              {/*
                O e-mail vem gravado junto do id justamente porque a FK é SET
                NULL: conta apagada ainda precisa dizer quem foi.
              */}
              <td>{l.quem ?? <span className="muted">conta removida</span>}</td>
              <td>
                {rotuloDaAcao(l.acao)}
                <div className="muted" style={{ fontSize: 12 }}>
                  {l.entidade}
                  {l.entidade_id ? ` · ${l.entidade_id.slice(0, 8)}` : ''}
                </div>
              </td>
              <td>
                {mudancas(l.antes, l.depois).map(({ campo, de, para }) => (
                  <div key={campo} style={{ fontSize: 12 }}>
                    <span className="muted">{campo}:</span> {comoTexto(de)} → {comoTexto(para)}
                  </div>
                ))}
              </td>
              <td className="muted">{l.ip ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
