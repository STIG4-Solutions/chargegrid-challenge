import { useId, useState } from 'react'
import { admin, power, useAction, useApi } from '@chargegrid/sdk'

import { Async, Empty } from '../../components/Async.jsx'
import { Campo } from '../../components/Campo.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import {
  alcanceDoPapel,
  CAMPOS_DA_CONTA,
  CONTA_VAZIA,
  corpoDaConta,
  mensagemDeSucesso,
  mensagemDoErro,
  podeDesligar,
  pracaDaConta,
  problemaNaConta,
  problemasDaConta,
  resumoDoQueFalta,
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

/**
 * Exportado para o teste montar com props, sem subir a aba inteira.
 *
 * `criarConta` entra por prop, com o SDK como padrão, pelo mesmo motivo de
 * `aoResolver` em `FilaDeReportes`: o sucesso e o 409 são metade da experiência
 * desta tela, e sem poder trocar a chamada não haveria como testar nenhum dos
 * dois sem levantar servidor.
 */
export function NovaConta({ sites, aoCriar, criarConta = admin.createUser }) {
  const [campos, setCampos] = useState(CONTA_VAZIA)
  const [aberto, setAberto] = useState(false)
  const [sucesso, setSucesso] = useState(null)
  const [senhaVisivel, setSenhaVisivel] = useState(false)
  // Em quais campos a pessoa já mexeu. Sem isto, abrir o formulário já acusa
  // "Escreva o nome completo" num campo que ela nem viu ainda — a tela começa
  // repreendendo alguém que não fez nada.
  const [tocados, setTocados] = useState({})

  const idBase = useId()
  const id = (chave) => `${idBase}-${chave}`

  const problemas = problemasDaConta(campos)
  const problema = problemaNaConta(campos)
  const falta = resumoDoQueFalta(campos)
  // Erro só aparece depois do primeiro contato com o campo.
  const erro = (chave) => (tocados[chave] ? problemas[chave] : null)

  const criar = useAction(() => criarConta(corpoDaConta(campos)), {
    onSuccess: () => {
      setSucesso(mensagemDeSucesso(campos))
      setCampos(CONTA_VAZIA)
      setTocados({})
      setSenhaVisivel(false)
      setAberto(false)
      aoCriar?.()
    }
  })

  const campo = (chave) => (e) => {
    setCampos({ ...campos, [chave]: e.target.value })
    // O erro do servidor fala do que foi ENVIADO. Assim que a pessoa muda um
    // campo ele passa a descrever um envio que não existe mais — e um 409 de
    // e-mail repetido parado embaixo de um e-mail novo parece recusa do novo.
    if (criar.error) criar.clearError()
  }
  const tocar = (chave) => () => setTocados((atuais) => ({ ...atuais, [chave]: true }))

  const enviar = (e) => {
    e.preventDefault()
    // Enter num campo envia. Se ainda falta algo, em vez de não acontecer nada,
    // todos os campos passam a tocados e cada pendência aparece na sua célula.
    if (problema) {
      setTocados({ nome: true, email: true, senha: true, siteId: true })
      return
    }
    void criar.run()
  }

  const abrir = () => {
    setSucesso(null)
    setAberto(true)
  }

  return (
    <div className="card" style={{ marginTop: 16, display: 'grid', gap: 12 }}>
      {/*
        Região viva SEMPRE montada, mesmo vazia: leitor de tela só anuncia
        mudança em região que já existia antes da mudança. Se ela nascesse junto
        com a mensagem, o sucesso passaria em silêncio — que é exatamente o que
        acontecia antes, quando o formulário só fechava.
      */}
      <div role="status" aria-live="polite">
        {sucesso && <div className="form-ok">{sucesso}</div>}
      </div>

      {!aberto ? (
        <div>
          <button type="button" className="btn" onClick={abrir}>
            Nova conta
          </button>
        </div>
      ) : (
        <form onSubmit={enviar} style={{ display: 'grid', gap: 12 }}>
          <div>
            <div className="card-title">Nova conta</div>
            <div className="card-sub" style={{ margin: 0 }}>
              Conta de quem trabalha na rede. Motorista se cadastra sozinho pelo app e não entra
              aqui.
            </div>
          </div>

          {/*
            Os cinco campos numa linha só. `auto-fit` com mínimo de 180px mantém
            a linha em tela larga e quebra sozinho no notebook — cinco campos
            fixos num monitor estreito viram cinco campos ilegíveis. Eram 160px:
            subiu porque agora cada célula carrega uma dica embaixo, e a 160 ela
            quebrava em quatro linhas e desalinhava a fileira.

            `alignItems: start` e não `end`: as dicas têm alturas diferentes, e
            alinhar por baixo faria os campos flutuarem em alturas diferentes.
          */}
          <div
            style={{
              display: 'grid',
              gap: 12,
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              alignItems: 'start'
            }}
          >
            <Campo
              id={id('nome')}
              rotulo={CAMPOS_DA_CONTA.nome.rotulo}
              dica={CAMPOS_DA_CONTA.nome.dica}
              erro={erro('nome')}
            >
              <input
                id={id('nome')}
                className="input"
                value={campos.nome}
                onChange={campo('nome')}
                onBlur={tocar('nome')}
                aria-describedby={`${id('nome')}-dica`}
                aria-invalid={erro('nome') ? true : undefined}
                autoComplete="off"
              />
            </Campo>

            <Campo
              id={id('email')}
              rotulo={CAMPOS_DA_CONTA.email.rotulo}
              dica={CAMPOS_DA_CONTA.email.dica}
              erro={erro('email')}
            >
              {/*
                `autoComplete="off"` e, na senha, `new-password`: e-mail mais
                senha na mesma linha é a assinatura de um formulário de LOGIN
                para o navegador, e ele oferece preencher com as credenciais de
                quem está logado. Criar a conta de outra pessoa com o e-mail e a
                senha do próprio admin é um acidente de um clique.
              */}
              <input
                id={id('email')}
                className="input"
                type="email"
                inputMode="email"
                value={campos.email}
                onChange={campo('email')}
                onBlur={tocar('email')}
                aria-describedby={`${id('email')}-dica`}
                aria-invalid={erro('email') ? true : undefined}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
              />
            </Campo>

            <Campo
              id={id('senha')}
              rotulo={CAMPOS_DA_CONTA.senha.rotulo}
              dica={CAMPOS_DA_CONTA.senha.dica}
              erro={erro('senha')}
              acao={
                /*
                  Revelar a senha aqui não é conveniência: esta senha não é da
                  pessoa que digita, é a que ela vai DITAR para outra, e o
                  servidor não pede troca no primeiro acesso. Digitada às cegas,
                  um erro de digitação só aparece como "não consigo entrar" dias
                  depois, sem ninguém saber qual das duas pontas errou.
                */
                <button
                  type="button"
                  onClick={() => setSenhaVisivel((visivel) => !visivel)}
                  aria-label={senhaVisivel ? 'Ocultar a senha inicial' : 'Mostrar a senha inicial'}
                  style={{
                    background: 'none',
                    border: 0,
                    padding: 0,
                    color: 'var(--sems-muted)',
                    font: 'inherit',
                    fontSize: 11,
                    textDecoration: 'underline',
                    cursor: 'pointer'
                  }}
                >
                  {senhaVisivel ? 'ocultar' : 'mostrar'}
                </button>
              }
            >
              <input
                id={id('senha')}
                className="input"
                type={senhaVisivel ? 'text' : 'password'}
                value={campos.senha}
                onChange={campo('senha')}
                onBlur={tocar('senha')}
                aria-describedby={`${id('senha')}-dica`}
                aria-invalid={erro('senha') ? true : undefined}
                autoComplete="new-password"
              />
            </Campo>

            <Campo
              id={id('papel')}
              rotulo={CAMPOS_DA_CONTA.papel.rotulo}
              /* A dica do papel é o alcance dele, e muda com a escolha: é a
                 única diferença entre os dois que decide qual usar. */
              dica={alcanceDoPapel(campos.papel)}
            >
              <select
                id={id('papel')}
                className="input"
                value={campos.papel}
                onChange={campo('papel')}
                aria-describedby={`${id('papel')}-dica`}
              >
                <option value="operator">Operador</option>
                <option value="admin">Administrador</option>
              </select>
            </Campo>

            {campos.papel === 'operator' ? (
              <Campo
                id={id('praca')}
                rotulo={CAMPOS_DA_CONTA.siteId.rotulo}
                dica={CAMPOS_DA_CONTA.siteId.dica}
                erro={erro('siteId')}
              >
                <select
                  id={id('praca')}
                  className="input"
                  value={campos.siteId}
                  onChange={campo('siteId')}
                  onBlur={tocar('siteId')}
                  aria-describedby={`${id('praca')}-dica`}
                  aria-invalid={erro('siteId') ? true : undefined}
                >
                  {/*
                    Nasce em branco de propósito, e a primeira praça NÃO vem
                    pré-selecionada: escolher a primeira da lista por conta
                    própria é literalmente o comportamento de servidor que esta
                    obrigatoriedade existe para evitar. Aqui seria pior ainda,
                    porque pareceria escolha de quem cadastrou.
                  */}
                  <option value="">Escolha a praça…</option>
                  {/*
                    `site_id` e `nome` — as chaves que `GET /power/sites`
                    devolve. Com `id`/`name` as opções renderizavam vazias e o
                    formulário não tinha como ser enviado, porque a praça é
                    obrigatória.
                  */}
                  {sites.map((s) => (
                    <option key={s.site_id} value={s.site_id}>
                      {s.nome}
                    </option>
                  ))}
                </select>
              </Campo>
            ) : (
              /*
                Admin não escolhe praça — mas o campo SUMIR fazia a linha pular
                de cinco colunas para quatro no instante da troca, e campo que
                some parece campo que quebrou. Aqui ele vira uma afirmação com
                cara de campo: a linha não se mexe, e a regra ("admin é global")
                fica escrita em vez de implícita no buraco.

                O texto vem de `pracaDaConta`, o mesmo que a tabela usa na linha
                de um admin. Escrito à mão aqui, o formulário diria "toda a
                rede" e a tabela poderia dizer outra coisa depois.
              */
              <div style={{ display: 'grid', gap: 4, alignContent: 'start' }}>
                <div style={{ fontSize: 12, color: 'var(--sems-muted)', minHeight: 18 }}>
                  {CAMPOS_DA_CONTA.siteId.rotulo}
                </div>
                <div className="input somente-leitura">{pracaDaConta({ role: 'admin' })}</div>
                <div className="muted" style={{ fontSize: 11, lineHeight: 1.35 }}>
                  Administrador não fica preso a uma praça.
                </div>
              </div>
            )}
          </div>

          {/*
            `role="alert"` e não texto solto: quando o POST volta 409, o foco
            está no botão, longe daqui, e sem o anúncio a pessoa fica olhando
            para um formulário que aparentemente não fez nada.
          */}
          {criar.error && (
            <div className="form-error" role="alert">
              {mensagemDoErro(criar.error)}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={Boolean(problema) || criar.pending}
            >
              {criar.pending ? 'Criando…' : 'Criar conta'}
            </button>
            <button type="button" className="btn" onClick={() => setAberto(false)}>
              Cancelar
            </button>
            {/*
              Por que o botão está apagado, ao lado dele. Botão desabilitado sem
              motivo visível é beco sem saída — e o resumo entra numa região viva
              porque `disabled` tira o botão da ordem de tabulação: quem usa
              leitor de tela não consegue chegar nele para ouvir a explicação,
              mas ouve a região mudar sozinha.
            */}
            <span className="muted" aria-live="polite" style={{ fontSize: 12 }}>
              {falta}
            </span>
          </div>
        </form>
      )}
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
                {/* `badge-green`/`badge-gray` e nao `ok`/`warn`: estas duas nao
                    existem no CSS, e as pilulas sairam sem cor nenhuma - as duas
                    situacoes pintadas igual, que e' o oposto do que a coluna serve
                    para mostrar. */}
                <span className={`badge ${c.is_active ? 'badge-green' : 'badge-gray'}`}>
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
