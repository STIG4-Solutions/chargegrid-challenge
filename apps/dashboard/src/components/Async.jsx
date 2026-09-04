// Estados de carregamento, erro e vazio — as três telas de EV usam os mesmos.

export function Spinner({ size = 18 }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />
}

export function Loading({ label = 'Carregando…' }) {
  return (
    <div className="async-state">
      <Spinner size={22} />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ error, onRetry, compact = false }) {
  if (!error) return null
  const offline = error.isOffline

  return (
    <div className={'async-error' + (compact ? ' compact' : '')} role="alert">
      <div>
        <strong>{offline ? 'API indisponível' : 'Não foi possível carregar'}</strong>
        <p className="muted">{error.detail || error.message}</p>
        {offline && (
          <p className="muted" style={{ fontSize: 12 }}>
            Suba o backend com <code>npm run infra:up</code> na raiz do repositório.
          </p>
        )}
      </div>
      {onRetry && (
        <button className="btn btn-sm" onClick={() => onRetry()}>
          Tentar de novo
        </button>
      )}
    </div>
  )
}

export function Empty({ label = 'Nada por aqui ainda.' }) {
  return <div className="async-state muted">{label}</div>
}

/**
 * Envolve uma seção: mostra carregamento na primeira busca, erro quando não há
 * dado nenhum, e o conteúdo assim que houver — inclusive durante recargas.
 */
export function Async({ loading, error, data, onRetry, children, empty }) {
  if (loading && !data) return <Loading />
  if (error && !data) return <ErrorState error={error} onRetry={onRetry} />
  if (!data) return null
  if (empty && (Array.isArray(data) ? data.length === 0 : false)) return <Empty label={empty} />
  return (
    <>
      {error && <ErrorState error={error} onRetry={onRetry} compact />}
      {children}
    </>
  )
}
