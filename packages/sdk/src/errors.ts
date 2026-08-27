/** Erro de API com código estável — o cliente distingue causas sem ler texto. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: string

  constructor(status: number, code: string, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }

  /** Backend fora do ar — o caso mais comum em desenvolvimento. */
  get isOffline(): boolean {
    return this.code === 'network'
  }

  /** Sem potência no site: a sessão não pôde ser autorizada. */
  get isInsufficientPower(): boolean {
    return this.code === 'insufficient_power'
  }
}
