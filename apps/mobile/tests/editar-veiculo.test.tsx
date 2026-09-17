/**
 * A edição de veículo na tela.
 *
 * `verify-mobile.mjs` cobre `veiculo.ts` — o corpo do PATCH, o piso do modelo,
 * a vírgula decimal. Aquilo pode estar todo certo e a tela ainda oferecer
 * "Salvar" quando não há nada para salvar, gravando uma alteração que não
 * existe.
 */
import { render, screen } from '@testing-library/react-native'
import EditarVeiculo from '../src/EditarVeiculo'

const CARRO = {
  id: 'v1',
  model: 'Nissan Leaf',
  plate: 'ABC1D23',
  battery_kwh: 40,
  max_ac_kw: 7.4,
  vin: null
} as never

const nada = () => {}

test('abre com o que esta gravado, e nao em branco', async () => {
  await render(<EditarVeiculo veiculo={CARRO} aoSalvar={nada} aoFechar={nada} />)
  expect(screen.getByDisplayValue('Nissan Leaf')).toBeTruthy()
  expect(screen.getByDisplayValue('ABC1D23')).toBeTruthy()
  expect(screen.getByDisplayValue('40')).toBeTruthy()
})

test('sem mudanca nenhuma, Salvar nasce desabilitado', async () => {
  // A regra de `corpoDaEdicao`: corpo vazio significa "nada mudou". Se o botao
  // ficasse ativo, o toque mandaria um PATCH sem campo algum.
  await render(<EditarVeiculo veiculo={CARRO} aoSalvar={nada} aoFechar={nada} />)
  const salvar = screen.getByRole('button', { name: 'Salvar' })
  expect(salvar.props.accessibilityState.disabled).toBe(true)
})

test('Cancelar continua disponivel mesmo sem mudanca', async () => {
  // Fechar o editor nao depende de ter editado - travar os dois botoes deixaria
  // a pessoa presa no formulario.
  await render(<EditarVeiculo veiculo={CARRO} aoSalvar={nada} aoFechar={nada} />)
  const cancelar = screen.getByRole('button', { name: 'Cancelar' })
  expect(cancelar.props.accessibilityState.disabled).toBe(false)
})
