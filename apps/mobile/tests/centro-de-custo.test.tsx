/**
 * A atribuição de centro de custo na tela da Frota.
 *
 * `verify-mobile.mjs` cobre `frota.ts` — sugestões sem repetir, contagem de
 * carros sem área, piso do nome. O que ele não alcança é o caso que motivou a
 * seção: **frota vazia não pode renderizar seção nenhuma**. Uma seção "Carros
 * da frota" sem carro nenhum é pior que a ausência dela — o próprio `App.tsx`
 * já documenta essa regra para as abas.
 */
import { render, screen, waitFor } from '@testing-library/react-native'

const mockListar = jest.fn()

jest.mock('@chargegrid/sdk', () => {
  const real = jest.requireActual('@chargegrid/sdk')
  return { ...real, app: { ...real.app, fleetVehicles: () => mockListar() } }
})

import CentroDeCusto from '../src/CentroDeCusto'

const FROTA = [
  { id: '1', modelo: 'Kwid', placa: 'AAA1A11', centro_de_custo: 'Logística', motorista: 'Ana' },
  { id: '2', modelo: 'Leaf', placa: 'BBB2B22', centro_de_custo: null, motorista: 'Bruno' }
]

beforeEach(() => mockListar.mockReset())

test('frota vazia nao renderiza secao nenhuma', async () => {
  mockListar.mockResolvedValue([])
  await render(<CentroDeCusto />)
  await waitFor(() => expect(mockListar).toHaveBeenCalled())
  expect(screen.queryByText('Carros da frota')).toBeNull()
})

test('com carros, lista e conta os sem area', async () => {
  mockListar.mockResolvedValue(FROTA)
  await render(<CentroDeCusto />)
  await waitFor(() => expect(screen.getByText('Carros da frota')).toBeTruthy())
  expect(screen.getByText('Kwid')).toBeTruthy()
  // O contador e' o mesmo numero que o aviso do relatorio cobra logo acima.
  expect(screen.getByText('1 sem área')).toBeTruthy()
})

test('carro sem area se descreve como sem area', async () => {
  mockListar.mockResolvedValue(FROTA)
  await render(<CentroDeCusto />)
  await waitFor(() => expect(screen.getByText('Leaf')).toBeTruthy())
  expect(screen.getByText('sem área')).toBeTruthy()
  expect(screen.getByText('Logística')).toBeTruthy()
})

test('frota toda classificada nao mostra o contador', async () => {
  // Cobrar "0 sem área" seria ruido: o aviso existe para pedir acao, e nao ha
  // acao a pedir.
  mockListar.mockResolvedValue([FROTA[0]])
  await render(<CentroDeCusto />)
  await waitFor(() => expect(screen.getByText('Carros da frota')).toBeTruthy())
  expect(screen.queryByText(/sem área/)).toBeNull()
})
