/**
 * Regras puras da atribuição de centro de custo.
 *
 * Mesma separação de `veiculo.ts`: o que decide o que vai para o servidor fica
 * fora do componente, para `npm run verify:mobile` alcançar.
 */
import type { VeiculoDaFrota } from '@chargegrid/sdk'

/** Teto do servidor: `CentroDeCustoIn.centro_de_custo`, max_length=60. */
export const CENTRO_MAXIMO = 60

/**
 * As áreas já em uso na frota, para oferecer em vez de fazer digitar.
 *
 * O centro de custo é texto livre no banco. Duas pessoas digitando "Logistica"
 * e "Logística" viram duas linhas no relatório, e o rateio que deveria fechar
 * passa a contar a mesma área duas vezes — por isso tocar na que já existe é o
 * caminho fácil, e digitar é o de exceção.
 */
export function centrosEmUso(veiculos: VeiculoDaFrota[]): string[] {
  const vistos = new Set<string>()
  for (const v of veiculos) {
    const nome = v.centro_de_custo?.trim()
    if (nome) vistos.add(nome)
  }
  return [...vistos].sort((a, b) => a.localeCompare(b, 'pt-BR'))
}

/** O que impede este nome de ser salvo. `null` quando pode. */
export function problemaNoCentro(texto: string): string | null {
  const limpo = texto.trim()
  if (!limpo) return 'Escreva o nome da área, ou use "Sem área" para limpar.'
  if (limpo.length > CENTRO_MAXIMO) return `No máximo ${CENTRO_MAXIMO} caracteres.`
  return null
}

/** Quantos carros ainda não têm área — o número que o aviso do relatório cobra. */
export function semArea(veiculos: VeiculoDaFrota[]): number {
  return veiculos.filter((v) => !v.centro_de_custo?.trim()).length
}
