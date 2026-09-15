/**
 * Uma célula de formulário: rótulo, controle e UMA faixa embaixo que ora é
 * dica, ora é o erro do campo.
 *
 * A mesma faixa para as duas coisas, com o mesmo `id`, por dois motivos. O
 * `aria-describedby` do controle aponta sempre para um nó que existe — com dica
 * e erro em nós separados o atributo teria de trocar de alvo e ficaria
 * apontando para o nada metade do tempo. E o erro SUBSTITUI a dica: uma vez
 * quebrada, repetir a regra ao lado do erro diz a mesma coisa duas vezes e
 * ainda empurra a linha inteira para baixo.
 *
 * `htmlFor` em vez de `<label>` envolvendo o controle: há rótulo que divide a
 * linha com um botão (revelar senha, voltar para agora), e botão dentro de
 * label faz o clique nele também cair no campo.
 *
 * Nasceu no formulário de contas e saiu de lá para ser compartilhado. Duplicar
 * o padrão em cada tela é o caminho curto para as telas divergirem: a segunda
 * cópia nunca recebe a correção que a primeira ganhou.
 */
export function Campo({ id, rotulo, dica, erro, acao, children }) {
  return (
    <div style={{ display: 'grid', gap: 4, alignContent: 'start' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 8,
          minHeight: 18
        }}
      >
        <label htmlFor={id} style={{ fontSize: 12, color: 'var(--sems-muted)' }}>
          {rotulo}
        </label>
        {acao}
      </div>
      {children}
      <div
        id={`${id}-dica`}
        className={erro ? 'red' : 'muted'}
        style={{ fontSize: 11, lineHeight: 1.35 }}
      >
        {erro || dica}
      </div>
    </div>
  )
}
