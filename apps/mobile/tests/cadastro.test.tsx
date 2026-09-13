/**
 * A tela de criar conta.
 *
 * `verify-mobile.mjs` cobre `cadastro.ts` — validação, corpo do POST, recado do
 * 409. O que ele não alcança é o que a pessoa vê: o botão precisa nascer
 * apagado, a pendência **não** pode aparecer num formulário ainda em branco, e
 * o 409 tem de oferecer a saída em vez de virar erro genérico.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react-native'
import { renderNaTela } from './util'

const mockRegistrar = jest.fn()
const mockEntrar = jest.fn()

jest.mock('@chargegrid/sdk', () => {
  const real = jest.requireActual('@chargegrid/sdk')
  return { ...real, auth: { ...real.auth, register: (d: unknown) => mockRegistrar(d) } }
})

jest.mock('../src/auth', () => ({
  useAuth: () => ({ login: mockEntrar })
}))

import SignUpScreen from '../src/screens/SignUpScreen'

const nada = () => {}

// `fireEvent` da RNTL 14 devolve Promise, como o `render`. Sem `await`, o
// re-render nao aconteceu ainda quando a assercao roda - e o teste falha
// dizendo que o botao continua apagado, que e' verdade naquele instante.
async function preencher() {
  await fireEvent.changeText(screen.getByPlaceholderText('Maria Souza'), 'Maria Souza')
  await fireEvent.changeText(screen.getByPlaceholderText('voce@email.com'), 'maria@email.com')
  await fireEvent.changeText(
    screen.getByPlaceholderText('pelo menos 8 caracteres'),
    'senha-comprida'
  )
}

beforeEach(() => {
  mockRegistrar.mockReset()
  mockEntrar.mockReset()
})

test('formulario em branco nao reclama de nada', async () => {
  // Abrir uma tela ja' acusando campo vazio e' cobrar antes de haver o que
  // cobrar. A mensagem so' aparece depois que a pessoa comeca a escrever.
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  expect(screen.queryByText(/Escreva seu nome/)).toBeNull()
  expect(screen.getByRole('button', { name: 'Criar conta' }).props.accessibilityState.disabled).toBe(
    true
  )
})

test('formulario incompleto mostra a pendencia e mantem o botao apagado', async () => {
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  await fireEvent.changeText(screen.getByPlaceholderText('Maria Souza'), 'Maria Souza')

  expect(screen.getByText(/Confira o e-mail/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Criar conta' }).props.accessibilityState.disabled).toBe(
    true
  )
})

test('completo, o botao acende', async () => {
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  await preencher()
  expect(
    screen.getByRole('button', { name: 'Criar conta' }).props.accessibilityState.disabled
  ).toBe(false)
})

test('cadastro bem-sucedido entra em seguida, sem pedir a senha de novo', async () => {
  // A rota devolve o USUARIO, nao tokens. Parar no 201 deixaria a pessoa
  // cadastrada e de fora ao mesmo tempo.
  mockRegistrar.mockResolvedValue({ id: 'u1' })
  mockEntrar.mockResolvedValue(undefined)
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  await preencher()

  await fireEvent.press(screen.getByRole('button', { name: 'Criar conta' }))

  await waitFor(() => expect(mockEntrar).toHaveBeenCalledWith('maria@email.com', 'senha-comprida'))
})

test('e-mail ja cadastrado oferece ir para o login', async () => {
  mockRegistrar.mockRejectedValue({ status: 409, detail: 'e-mail já cadastrado' })
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  await preencher()

  await fireEvent.press(screen.getByRole('button', { name: 'Criar conta' }))

  await waitFor(() => expect(screen.getByText(/Já existe uma conta/)).toBeTruthy())
  expect(screen.getByText('Ir para o login')).toBeTruthy()
})

test('outro erro do servidor nao oferece login', async () => {
  // A saida so' faz sentido para quem JA' tem conta. Oferece-la num 500 mandaria
  // a pessoa tentar entrar numa conta que nao existe.
  mockRegistrar.mockRejectedValue({ status: 500, detail: 'falha interna' })
  await renderNaTela(<SignUpScreen aoVoltar={nada} />)
  await preencher()

  await fireEvent.press(screen.getByRole('button', { name: 'Criar conta' }))

  await waitFor(() => expect(screen.getByText('falha interna')).toBeTruthy())
  expect(screen.queryByText('Ir para o login')).toBeNull()
})
