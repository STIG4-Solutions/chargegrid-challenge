/**
 * Regras puras da edição de veículo.
 *
 * Vivem fora do componente pelo mesmo motivo dos módulos `.js` do painel: são a
 * parte que decide **o que vai para o servidor**, e componente com hook não roda
 * em Node. Assim `npm run verify:mobile` as exercita sem simulador.
 */
import type { Veiculo } from '@chargegrid/sdk'

/**
 * Campos que a tela edita.
 *
 * `vin` e `max_ac_kw` ficam fora de propósito: ninguém digita VIN de cabeça, e
 * o limite AC é característica do carro lida do equipamento, não coisa que o
 * dono corrige no cadastro.
 */
export interface CamposDoVeiculo {
  modelo: string
  placa: string
  bateria: string
}

export function camposIniciais(v: Veiculo): CamposDoVeiculo {
  return {
    modelo: v.model ?? '',
    placa: v.plate ?? '',
    bateria: v.battery_kwh ? String(v.battery_kwh) : ''
  }
}

/** Vírgula é o separador decimal de quem digita em português. */
export function comoNumero(texto: string): number | null {
  const limpo = texto.trim().replace(',', '.')
  if (!limpo) return null
  const n = Number(limpo)
  return Number.isFinite(n) && n >= 0 ? n : null
}

/** O que impede a edição de ser salva. `null` quando pode. */
export function problemaNaEdicao(campos: CamposDoVeiculo): string | null {
  const modelo = campos.modelo.trim()
  if (!modelo) return 'O modelo não pode ficar vazio.'
  if (modelo.length > 80) return 'Modelo com mais de 80 caracteres.'
  if (campos.bateria.trim() && comoNumero(campos.bateria) === null) {
    return 'Bateria: use só números, em kWh.'
  }
  return null
}

/**
 * Só o que mudou, para um PATCH que é mesmo parcial.
 *
 * A rota usa `exclude_unset`, então mandar o cadastro inteiro funcionaria — e
 * transformaria toda correção de placa numa reescrita de todos os campos.
 *
 * Devolve `{}` quando nada mudou, e é isso que deixa o botão calado em vez de
 * gravar uma alteração que não existe.
 */
export function corpoDaEdicao(
  original: Veiculo,
  campos: CamposDoVeiculo
): Record<string, unknown> {
  const corpo: Record<string, unknown> = {}

  const modelo = campos.modelo.trim()
  if (modelo !== (original.model ?? '')) corpo.model = modelo

  // Placa apagada vira `null`, e nao string vazia: o banco guarda ausencia como
  // NULL, e `''` seria uma placa que existe e nao tem caracteres.
  const placa = campos.placa.trim()
  if (placa !== (original.plate ?? '')) corpo.plate = placa || null

  const bateria = comoNumero(campos.bateria)
  if (bateria !== (original.battery_kwh ?? null)) corpo.battery_kwh = bateria

  return corpo
}
