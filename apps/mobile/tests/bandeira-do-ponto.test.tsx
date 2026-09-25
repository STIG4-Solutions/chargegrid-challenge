/**
 * A bandeira e o preco final no card do ponto, antes de iniciar.
 *
 * O preco mostrado e' o que a fatura vai cobrar por kWh se a recarga comecar
 * agora - janela vigente x bandeira. Com a bandeira velha, o servidor ja' manda o
 * preco sem multiplicador (e' o que a sessao travaria), e a tela diz por que.
 */
import { render, screen } from '@testing-library/react-native'
import BandeiraDoPonto from '../src/BandeiraDoPonto'

const AMARELA = {
  cor: 'amarela',
  multiplicador: 1.15,
  folga_pct: 40,
  motivo: 'Consumo do prédio alto: sobra pouca potência para os carregadores',
  calculada_em: '2026-09-25T14:00:00Z',
  desatualizada: false
}

test('mostra a bandeira, o multiplicador e o preco final', async () => {
  await render(<BandeiraDoPonto bandeira={AMARELA} preco={2.3} />)
  expect(screen.getByText('Bandeira amarela · x1,15')).toBeTruthy()
  expect(screen.getByText(/R\$\s?2,30\/kWh se iniciar agora/)).toBeTruthy()
  expect(screen.getByText(/Consumo do prédio alto/)).toBeTruthy()
})

test('bandeira velha aparece como indisponivel, com o preco sem multiplicador', async () => {
  await render(<BandeiraDoPonto bandeira={{ ...AMARELA, desatualizada: true }} preco={2} />)
  expect(screen.getByText('Bandeira indisponível')).toBeTruthy()
  expect(screen.queryByText(/Bandeira amarela/)).toBeNull()
  expect(screen.getByText(/R\$\s?2,00\/kWh se iniciar agora/)).toBeTruthy()
})

test('sem bandeira (flag desligada), mostra so o preco', async () => {
  await render(<BandeiraDoPonto bandeira={null} preco={2} />)
  expect(screen.queryByText(/Bandeira/)).toBeNull()
  expect(screen.getByText(/R\$\s?2,00\/kWh se iniciar agora/)).toBeTruthy()
})

test('ponto sem tarifa e sem bandeira nao mostra nada', async () => {
  await render(<BandeiraDoPonto bandeira={null} preco={null} />)
  expect(screen.toJSON()).toBeNull()
})
