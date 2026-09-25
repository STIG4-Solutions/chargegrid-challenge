import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App.jsx'

afterEach(cleanup)

function renderAt(pathname) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <App />
    </MemoryRouter>
  )
}

describe('rotas públicas do site', () => {
  test('apresenta a landing com o título e o caminho para o app', () => {
    renderAt('/')

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Recarga que dá lucro sem estourar a energia da sua loja.'
      })
    ).toBeInTheDocument()

    for (const link of screen.getAllByRole('link', { name: 'Baixar o app' })) {
      expect(link).toHaveAttribute('href', '/download')
    }

    for (const link of screen.getAllByRole('link', { name: 'Acessar o painel' })) {
      expect(link).toHaveAttribute('href', 'http://localhost:5173')
    }
  })

  test('apresenta o download Android e os três passos de instalação', () => {
    renderAt('/download')

    expect(
      screen.getByRole('heading', { name: 'Sua recarga continua no bolso' })
    ).toBeInTheDocument()

    expect(screen.getByRole('link', { name: /baixar apk para android/i })).toHaveAttribute(
      'href',
      '/download/android'
    )

    const instructions = screen.getByRole('list', { name: 'Como instalar' })
    expect(within(instructions).getAllByRole('listitem')).toHaveLength(3)
  })
})
