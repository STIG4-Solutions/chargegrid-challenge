/**
 * Regras puras do card de previsão de demanda.
 *
 * O que estas funções decidem é **quanta confiança a tela transmite**. Um número
 * de previsão desenhado igual a um número medido diz ao operador que os dois
 * valem o mesmo — e ele contrata demanda por isso.
 *
 * Três perguntas, três funções, porque são três coisas diferentes:
 *   - a faixa cobre o que promete?
 *   - o modelo é melhor que a régua?
 *   - dá para desenhar a banda?
 */

/**
 * A faixa p10–p90 contém o valor real com a frequência que anuncia?
 *
 * O backtest do modelo mediu 62,3%; a faixa promete 80%. Isso não é detalhe de
 * calibração: significa que o "pior caso" desenhado na tela é otimista, e quem
 * dimensiona contrato pelo extremo inferior vai errar mais do que espera.
 *
 * A tolerância existe porque backtest de três meses tem ruído de amostragem —
 * acusar por um ponto de diferença só produziria alarme.
 */
export function bandaConfiavel(medida, declarada, tolerancia = 5) {
  if (medida == null || declarada == null) return true
  return Number(medida) >= Number(declarada) - tolerancia
}

/**
 * O modelo erra menos que uma média móvel de 28 dias?
 *
 * A régua é três linhas de código. Um modelo que perde dela não é inútil — mas
 * não pode ser apresentado como base de decisão, e a tela precisa dizer isso.
 * Empate conta como derrota: se o resultado é o mesmo, a régua é preferível por
 * ser explicável.
 */
export function superaARegua(wapeModelo, wapeRegua) {
  if (wapeModelo == null || wapeRegua == null) return null
  return Number(wapeModelo) < Number(wapeRegua)
}

/**
 * Dá para desenhar a faixa de incerteza?
 *
 * Só quando o modelo se aplica E os dois extremos existem. Meia banda mente
 * sobre a incerteza declarada, e banda em volta de uma média móvel dá ares de
 * previsão a uma conta de padaria.
 */
export function temBanda(previsao) {
  // Depende da FONTE, não de `modelo_aplicavel`: existe o caso em que o modelo
  // conhece o ponto e mesmo assim não é usado, porque perde da régua. Aí o
  // número é média móvel, e desenhar incerteza em volta dele daria ares de
  // previsão a uma conta de padaria.
  if (previsao?.fonte !== 'modelo') return false
  return previsao.kwh_p10 != null && previsao.kwh_p90 != null
}

/**
 * Onde cada marca fica na barra de intervalo, de 0 a 100.
 *
 * A escala é a própria banda, com uma folga de 8% de cada lado para o previsto
 * não colar na borda quando estiver perto de um extremo.
 */
export function escalaDaBanda(previsao) {
  if (!temBanda(previsao)) return null
  const p10 = Number(previsao.kwh_p10)
  const p90 = Number(previsao.kwh_p90)
  const previsto = Number(previsao.kwh_previsto)
  if (!(p90 > p10)) return null

  const folga = (p90 - p10) * 0.08
  const min = p10 - folga
  const max = p90 + folga
  const posicao = (v) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))
  return { inicio: posicao(p10), fim: posicao(p90), previsto: posicao(previsto) }
}

/**
 * Quanto o previsto difere da régua, em percentual.
 *
 * Serve para o operador ver se o modelo está dizendo algo diferente da média
 * móvel. Diferença próxima de zero significa que o modelo não está agregando —
 * e aí a complexidade não se paga.
 */
export function distanciaDaRegua(previsao) {
  const media = Number(previsao?.media_diaria_28d ?? 0)
  const previsto = Number(previsao?.kwh_previsto ?? 0)
  if (!(media > 0)) return null
  const dias = 30
  const regua = media * dias
  if (!(regua > 0)) return null
  return ((previsto - regua) / regua) * 100
}
