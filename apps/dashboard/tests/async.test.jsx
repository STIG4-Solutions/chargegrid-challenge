/**
 * Os estados de `<Async>`, que toda aba do painel usa.
 *
 * A decisão que importa não é "carregando ou pronto": é o que acontece quando
 * há dado ANTIGO na tela e a recarga falha. Mostrar o erro e apagar a tabela
 * troca informação desatualizada — ainda útil — por nada. Manter o conteúdo e
 * avisar em cima é a escolha do componente, e é a que nenhum teste cobria.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Async } from '../src/components/Async.jsx'

const Conteudo = () => <p>1.234 kWh</p>
const erro = { detail: 'API indisponível agora' }

describe('primeira carga', () => {
  it('mostra o carregando enquanto não há dado', () => {
    render(
      <Async loading data={null}>
        <Conteudo />
      </Async>
    )
    expect(screen.getByText('Carregando…')).toBeInTheDocument()
  })

  it('mostra o erro quando falhou sem nunca ter tido dado', () => {
    render(
      <Async loading={false} error={erro} data={null}>
        <Conteudo />
      </Async>
    )
    expect(screen.getByRole('alert')).toHaveTextContent('API indisponível agora')
    expect(screen.queryByText('1.234 kWh')).not.toBeInTheDocument()
  })
})

describe('recarga que falha sobre dado existente', () => {
  it('mantém o conteúdo e avisa por cima', () => {
    render(
      <Async loading={false} error={erro} data={[1]}>
        <Conteudo />
      </Async>
    )
    expect(screen.getByText('1.234 kWh')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('não volta para o carregando quando já há dado na tela', () => {
    // Piscar o spinner por cima de uma tabela preenchida a cada poll seria
    // ruído — e `DemandContract` faz poll de 60 em 60 segundos.
    render(
      <Async loading data={[1]}>
        <Conteudo />
      </Async>
    )
    expect(screen.queryByText('Carregando…')).not.toBeInTheDocument()
    expect(screen.getByText('1.234 kWh')).toBeInTheDocument()
  })
})

describe('vazio', () => {
  it('lista vazia com rótulo mostra o rótulo, não o conteúdo', () => {
    render(
      <Async loading={false} data={[]} empty="Nenhuma campanha ativa.">
        <Conteudo />
      </Async>
    )
    expect(screen.getByText('Nenhuma campanha ativa.')).toBeInTheDocument()
    expect(screen.queryByText('1.234 kWh')).not.toBeInTheDocument()
  })

  it('objeto vazio NÃO é tratado como lista vazia', () => {
    // `{}` é resposta legítima de rota que devolve um resumo. Tratá-lo como
    // vazio esconderia um card que tem o que dizer.
    render(
      <Async loading={false} data={{}} empty="Nada aqui.">
        <Conteudo />
      </Async>
    )
    expect(screen.getByText('1.234 kWh')).toBeInTheDocument()
  })

  it('lista vazia SEM rótulo renderiza o conteúdo', () => {
    render(
      <Async loading={false} data={[]}>
        <Conteudo />
      </Async>
    )
    expect(screen.getByText('1.234 kWh')).toBeInTheDocument()
  })
})

describe('offline', () => {
  it('explica como subir o backend', () => {
    render(<Async loading={false} error={{ isOffline: true, detail: 'falha de rede' }} data={null} />)
    expect(screen.getByText('API indisponível')).toBeInTheDocument()
    expect(screen.getByText('npm run infra:up')).toBeInTheDocument()
  })

  it('sem onRetry não oferece o botão', () => {
    render(<Async loading={false} error={erro} data={null} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
