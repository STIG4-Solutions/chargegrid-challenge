/**
 * Regras puras do cadastro de praça.
 *
 * Espelham o que o servidor exige, e não menos — não para "validar antes" (ele
 * recusa de qualquer jeito), mas porque um 409 depois de clicar não diz à
 * pessoa o que fazer, e aqui dá para dizer enquanto ela digita.
 *
 * Se um dos lados mudar, o outro passa a mentir: o sintoma é um botão
 * habilitado que sempre falha, ou um aviso que impede o que a API aceitaria.
 */

/** O que o servidor aceita em `slug` — minúsculas, dígitos e hífen simples. */
export const FORMATO_DO_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

/**
 * Sugere um identificador a partir do nome — sem decidir por ninguém.
 *
 * O campo continua editável de propósito. O slug é a chave estável entre
 * reconstruções do banco, e é por ele que o artefato do modelo de previsão
 * reconhece o local; deixar a máquina escolher sozinha faria duas praças de
 * nome parecido virarem "shopping-morumbi" e "shopping-morumbi-2", e o modelo
 * cairia em fallback silencioso na segunda.
 */
export function sugerirSlug(nome) {
  return (nome ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/, '')
}

/**
 * Por que esta praça não pode ser cadastrada — ou `null` se pode.
 *
 * Uma razão por vez, na ordem em que a pessoa preenche: apontar três problemas
 * de campos que ela ainda nem viu é repreender quem não fez nada.
 */
export function problemaNaPraca({ nome, slug, limite, reserva, uf }) {
  if (!(nome ?? '').trim() || nome.trim().length < 2) {
    return 'Dê um nome à praça — é como ela aparece no seletor.'
  }
  if (!FORMATO_DO_SLUG.test(slug ?? '')) {
    return 'O identificador aceita só minúsculas, números e hífen: shopping-morumbi.'
  }
  if ((slug ?? '').length > 40) {
    return 'O identificador passa de 40 caracteres.'
  }
  if (uf && uf.trim().length !== 2) {
    return 'A UF tem duas letras.'
  }

  const teto = Number(limite)
  if (!Number.isFinite(teto) || teto <= 0) {
    return 'Informe o limite da rede em kW — sem ele a praça não distribui potência.'
  }
  const guardada = Number(reserva ?? 0)
  if (!Number.isFinite(guardada) || guardada < 0) {
    return 'A reserva não pode ser negativa.'
  }
  // O servidor recusa, e a razão é mais útil que o código: com a reserva
  // consumindo o limite inteiro, a praça fica de pé, aparece no seletor e
  // rateia zero para todos os pontos.
  if (guardada >= teto) {
    return 'A reserva precisa ser menor que o limite — senão não sobra potência para nenhum ponto.'
  }
  return null
}

/** O corpo que vai para a API, com os nomes que a rota espera. */
export function corpoDaPraca({ nome, slug, cidade, uf, limite, reserva }) {
  return {
    nome: (nome ?? '').trim(),
    slug: (slug ?? '').trim(),
    cidade: (cidade ?? '').trim() || null,
    estado: (uf ?? '').trim().toUpperCase() || null,
    limite_da_rede_kw: Number(limite),
    reserva_kw: Number(reserva ?? 0)
  }
}

/**
 * O que dizer depois de criar.
 *
 * Diz o que a pessoa ganha agora, e não só "criada": com a segunda praça, o
 * seletor passa a existir no topo da seção — e quem não souber disso vai
 * procurar a praça nova numa tela que ainda mostra a antiga.
 */
export function mensagemDaPraca({ nome, total }) {
  if (total >= 2) {
    return `${nome} criada. O seletor de praça agora aparece no topo — troque por lá para operá-la.`
  }
  return `${nome} criada.`
}
