import { useState } from 'react'
import { admin, power, useAction, useApi } from '@chargegrid/sdk'

import { Async, Empty } from '../../components/Async.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import {
  CONTA_VAZIA,
  corpoDaConta,
  podeDesligar,
  pracaDaConta,
  problemaNaConta,
  rotuloDoPapel,
  ultimoAcesso
} from './contas.js'

/**
 * Quem opera a rede.
 *
 * Até aqui operador e admin só nasciam do seed ou de um INSERT no banco — e a
 * docstring de `/auth/register` apontava para uma rota `/users` que nunca
 * existiu. Esta aba é essa rota, com tela.
 *
 * Só admin, porque a rota é de admin: quem cria operador é a GoodWe, e não o
 * estabelecimento. Motorista não aparece: ele se cadastra sozinho pelo app, e
 * são milhares — misturar os dois transformaria a lista de acessos da operação
 * numa lista de clientes.
 */
export default function Contas() {
  const contas = useApi(() => admin.users(true), [])
  const sites = useApi(() => power.visibleSites(), [])
  // Quem sou eu desce por PROP ate' `Linhas`, em vez de ela ler o contexto: e' o
  // que deixa a dependencia visivel na assinatura e permite testar a tabela sem
  // montar o provedor de sessao inteiro so' para saber um id.
  const { user } = useAuth()

  return (
    <div>
      <div className="panel">
        <div className="card-title">Contas de operação</div>
        <div className="card-sub">
          Operadores e administradores. Não há apagar: as referências de auditoria e faturamento são{' '}
          <code>SET NULL</code>, então apagar a conta apagaria o vínculo do rastro dela. Desligar
          tira o acesso e preserva quem fez o quê.
        </div>
      </div>

      <NovaConta sites={sites.data ?? []} aoCriar={() => void contas.refetch()} />

      <Async
        loading={contas.loading}
        error={contas.error}
        data={contas.data}
        onRetry={contas.refetch}
        empty="Nenhuma conta de operação cadastrada."
      >
        {contas.data && (
          <Linhas contas={contas.data} meuId={user?.id} aoMudar={() => void contas.refetch()} />
        )}
      </Async>
    </div>
  )
}

/** Exportado para o teste montar com props, sem subir a aba inteira. */
export function NovaConta({ sites, aoCriar }) {
  const [campos, setCampos] = useState(CONTA_VAZIA)
  const [aberto, setAberto] = useState(false)
  const problema = problemaNaConta(campos)

  const criar = useAction(() => admin.createUser(corpoDaConta(campos)), {
    onSuccess: () => {
      setCampos(CONTA_VAZIA)
      setAberto(false)
      aoCriar?.()
    }
  })

  const campo = (chave) => (e) => setCampos({ ...campos, [chave]: e.target.value })

  if (!aberto) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <button type="button" className="btn" onClick={() => setAberto(true)}>
          Nova conta
        </button>
      </div>
    )
  }

  return (
    <div className="card" style={{ marginTop: 16, display: 'grid', gap: 12 }}>
      <div className="card-title">Nova conta</div>

      <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
        <label>
          Nome
          <input value={campos.nome} onChange={campo('nome')} placeholder="Maria Souza" />
        </label>
        <label>
          E-mail
          <input value={campos.email} onChange={campo('email')} placeholder="maria@empresa.com" />
        </label>
        <label>
          Senha inicial
          <input type="password" value={campos.senha} onChange={campo('senha')} />
        </label>
        <label>
          Papel
          <select value={campos.papel} onChange={campo('papel')}>
            <option value="operator">Operador</option>
            <option value="admin">Administrador</option>
          </select>
        </label>
      </div>

      {/*
        O seletor de praça só aparece para operador, e não é cosmética: admin é
        global, e oferecer a praça a ele sugeriria que ficaria restrito a ela.
      */}
      {campos.papel === 'operator' && (
        <label>
          Praça
          <select value={campos.siteId} onChange={campo('siteId')}>
            <option value="">selecione…</option>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {problema && <div className="muted">{problema}</div>}
      {criar.error && <div className="error">{criar.error.detail}</div>}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          className="btn primary"
          disabled={Boolean(problema) || criar.pending}
          onClick={() => void criar.run()}
        >
          {criar.pending ? 'Criando…' : 'Criar conta'}
        </button>
        <button type="button" className="btn" onClick={() => setAberto(false)}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

/** Exportado para o teste montar com props, sem subir a aba inteira. */
export function Linhas({ contas, meuId, aoMudar }) {
  const mudar = useAction((id, ativa) => admin.setUserActive(id, ativa), {
    onSuccess: () => aoMudar?.()
  })

  if (!contas?.length) return <Empty label="Nenhuma conta de operação cadastrada." />

  return (
    <div className="card" style={{ marginTop: 16, overflowX: 'auto' }}>
      <table className="table" style={{ minWidth: 820 }}>
        <thead>
          <tr>
            <th>Nome</th>
            <th>E-mail</th>
            <th>Papel</th>
            <th>Praça</th>
            <th>Último acesso</th>
            <th>Situação</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {contas.map((c) => (
            <tr key={c.id} style={{ opacity: c.is_active ? 1 : 0.6 }}>
              <td>{c.full_name}</td>
              <td>{c.email}</td>
              <td>{rotuloDoPapel(c.role)}</td>
              <td>{pracaDaConta(c)}</td>
              <td>{ultimoAcesso(c.last_login_at)}</td>
              <td>
                <span className={`badge ${c.is_active ? 'ok' : 'warn'}`}>
                  {c.is_active ? 'Ativa' : 'Desligada'}
                </span>
              </td>
              <td className="text-right">
                {c.is_active ? (
                  <button
                    type="button"
                    className="btn"
                    /*
                      O servidor recusa desligar a própria conta com 409.
                      Desabilitar aqui é a diferença entre o botão nascer
                      apagado e a pessoa descobrir depois do clique.
                    */
                    disabled={!podeDesligar(c, meuId) || mudar.pending}
                    onClick={() => void mudar.run(c.id, false)}
                  >
                    Desligar
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn"
                    disabled={mudar.pending}
                    onClick={() => void mudar.run(c.id, true)}
                  >
                    Religar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {mudar.error && <div className="error">{mudar.error.detail}</div>}
    </div>
  )
}
