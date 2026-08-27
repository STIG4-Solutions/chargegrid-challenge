/**
 * Onde os tokens ficam guardados.
 *
 * A assinatura é a do `localStorage` de propósito: tanto ele quanto o
 * `AsyncStorage` do React Native satisfazem esta interface sem adaptador
 * nenhum. A diferença entre os dois — um é síncrono, o outro devolve Promise —
 * some porque tudo aqui é aguardado.
 */
export interface TokenStorage {
  getItem(chave: string): string | null | Promise<string | null>
  setItem(chave: string, valor: string): unknown
  removeItem(chave: string): unknown
}

/** Sem armazenamento configurado, a sessão vive só enquanto o processo viver. */
export function memoryStorage(): TokenStorage {
  const dados = new Map<string, string>()
  return {
    getItem: (chave) => dados.get(chave) ?? null,
    setItem: (chave, valor) => dados.set(chave, valor),
    removeItem: (chave) => dados.delete(chave)
  }
}
