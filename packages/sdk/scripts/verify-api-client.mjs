// Verificação em runtime do SDK (@chargegrid/sdk) com fetch e armazenamento
// simulados. Cobre o que é difícil de ver no navegador: renovação de token,
// erro de domínio, erro de validação e queda da API. Como o mesmo SDK atende
// painel e app do motorista, um cenário quebrado aqui quebra os dois.
//
//   npm run verify:api
import { build } from 'esbuild'
import { mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

// O SDK é publicado como TypeScript (sem build) para Vite e Metro compilarem
// direto — o Node não lê isso, então transpilamos para um arquivo temporário.
const raizSdk = fileURLToPath(new URL('..', import.meta.url))
const workspace = fileURLToPath(new URL('../../..', import.meta.url))
// Dentro de node_modules para o `react` externo continuar resolvendo.
const cache = join(workspace, 'node_modules/.cache/chargegrid')
mkdirSync(cache, { recursive: true })
const saida = join(cache, 'sdk.mjs')
await build({
  entryPoints: [join(raizSdk, 'src/index.ts')],
  outfile: saida,
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  external: ['react']
})

const sdk = await import(pathToFileURL(saida).href)
const {
  api,
  ApiError,
  configureSdk,
  currentTokens,
  hydrateTokens,
  saveTokens,
  socketUrl,
  accessToken
} = sdk

// Armazenamento assíncrono de propósito: é o do React Native. Se o SDK
// funciona com este, funciona com o localStorage síncrono da web.
const store = new Map()
const storage = {
  getItem: async (k) => (store.has(k) ? store.get(k) : null),
  setItem: async (k, v) => void store.set(k, v),
  removeItem: async (k) => void store.delete(k)
}

let sessaoExpirou = 0
configureSdk({
  baseUrl: 'http://localhost:8000',
  storage,
  onSessionExpired: () => sessaoExpirou++
})

const calls = []
let refreshCount = 0
let recusarRefresh = false
globalThis.fetch = async (url, init = {}) => {
  const u = String(url)
  calls.push(`${init.method || 'GET'} ${u.replace('http://localhost:8000', '')}`)

  if (u.includes('/auth/refresh')) {
    refreshCount++
    if (recusarRefresh)
      return new Response(JSON.stringify({ detail: 'refresh expirado' }), { status: 401 })
    return new Response(
      JSON.stringify({
        access_token: 'novo',
        refresh_token: 'r2',
        token_type: 'bearer',
        expires_in: 3600
      }),
      { status: 200, headers: { 'content-type': 'application/json' } }
    )
  }
  if (u.includes('/expira')) {
    const auth = init.headers?.Authorization
    if (auth === 'Bearer novo') return new Response(JSON.stringify({ ok: true }), { status: 200 })
    return new Response(JSON.stringify({ detail: 'credenciais invalidas' }), { status: 401 })
  }
  if (u.includes('/conflito')) {
    return new Response(
      JSON.stringify({ code: 'invalid_transition', detail: 'sessao ja encerrada' }),
      { status: 409 }
    )
  }
  if (u.includes('/validacao')) {
    return new Response(
      JSON.stringify({
        detail: [{ loc: ['body', 'limit_kw'], msg: 'Input should be less than 350' }]
      }),
      { status: 422 }
    )
  }
  if (u.includes('/rede')) throw new TypeError('fetch failed')
  if (u.includes('/assistant/conversations/cheia/')) {
    return new Response(JSON.stringify({ detail: 'limite de 6 mensagens por minuto' }), {
      status: 429
    })
  }
  if (u.includes('/assistant/conversations/pendurada/')) {
    // Fluxo que nunca termina sozinho. Como o fetch de verdade, cancelar o
    // signal derruba o corpo com AbortError.
    const corpo = new ReadableStream({
      start(controle) {
        controle.enqueue(new TextEncoder().encode('event: meta\ndata: {"conversa_id":"p"}\n\n'))
        init.signal?.addEventListener('abort', () =>
          controle.error(new DOMException('abortado', 'AbortError'))
        )
      }
    })
    return new Response(corpo, { status: 200 })
  }
  if (u.includes('/assistant/conversations/c1/messages')) {
    if (init.headers?.Authorization !== 'Bearer novo') {
      return new Response(JSON.stringify({ detail: 'credenciais invalidas' }), { status: 401 })
    }
    pedidoDoFluxo = JSON.parse(init.body)
    // Pedacos cortados onde a rede corta: no meio da linha, entre o '\n' duplo,
    // e no meio do 'ç' (2 bytes em UTF-8).
    const bytes = new TextEncoder().encode(
      'event: meta\ndata: {"conversa_id":"c1","mensagem_id":"m1"}\n\n' +
        ': keep-alive\n\n' +
        'event: ferramenta\ndata: {"nome":"potencia_agora","rotulo":"Consultando","estado":"inicio"}\n\n' +
        'event: delta\ndata: {"texto":"Potência "}\n\n' +
        'event: delta\ndata: {"texto":"disponível: 55 kW"}\r\n\r\n' +
        'event: fim\ndata: {"mensagem_id":"m2","tokens_entrada":10,"tokens_saida":5}\n\n'
    )
    const cedilha = bytes.indexOf(0xc3)
    const cortes = [7, 30, 61, cedilha + 1, bytes.length - 3, bytes.length]
    const corpo = new ReadableStream({
      start(controle) {
        let inicio = 0
        for (const fim of cortes) {
          controle.enqueue(bytes.slice(inicio, fim))
          inicio = fim
        }
        controle.close()
      }
    })
    return new Response(corpo, { status: 200, headers: { 'content-type': 'text/event-stream' } })
  }
  return new Response(null, { status: 204 })
}
let pedidoDoFluxo = null

let falhas = 0
const check = (nome, cond, extra = '') => {
  console.log(`${cond ? 'ok  ' : 'FALHA'} ${nome}${extra ? ' -> ' + extra : ''}`)
  if (!cond) falhas++
}

// 0. Hidratação: token já gravado no armazenamento vira sessão ativa.
store.set('chargegrid.tokens', JSON.stringify({ access_token: 'novo', refresh_token: 'r2' }))
const hidratados = await hydrateTokens()

check('hydrateTokens le o armazenamento assincrono', hidratados?.access_token === 'novo')
check('accessToken responde de forma sincrona apos hidratar', accessToken() === 'novo')

// 1. Renovação automática ao tomar 401 e repetição da requisição original.
await saveTokens({ access_token: 'velho', refresh_token: 'r1' })
refreshCount = 0
const retomada = await api.get('/expira')
check('401 dispara refresh e repete a chamada', retomada?.ok === true)
check('refresh executado uma vez', refreshCount === 1, `refreshCount=${refreshCount}`)
check('token novo persistido', currentTokens().access_token === 'novo')
check(
  'token novo gravado no armazenamento',
  JSON.parse(store.get('chargegrid.tokens')).access_token === 'novo'
)

// 2. Refresh único mesmo com várias chamadas simultâneas tomando 401.
await saveTokens({ access_token: 'velho', refresh_token: 'r1' })
refreshCount = 0
await Promise.all([api.get('/expira'), api.get('/expira'), api.get('/expira')])
check('3 chamadas concorrentes = 1 refresh so', refreshCount === 1, `refreshCount=${refreshCount}`)

// 3. Erro de domínio preserva code e detail.
try {
  await api.post('/conflito')
  check('erro de dominio propagado', false)
} catch (err) {
  check(
    'erro de dominio propagado',
    err instanceof ApiError && err.code === 'invalid_transition' && err.status === 409,
    err.detail
  )
}

// 4. Erro de validação do FastAPI vira mensagem legível.
try {
  await api.post('/validacao')
  check('422 formatado', false)
} catch (err) {
  check(
    '422 formatado por campo',
    err.detail.includes('limit_kw') && err.detail.includes('less than 350'),
    err.detail
  )
}

// 5. Backend fora do ar é sinalizado como offline, não como erro genérico.
try {
  await api.get('/rede')
  check('falha de rede sinalizada', false)
} catch (err) {
  check('falha de rede sinalizada como offline', err.isOffline === true, err.detail)
}

// 6. Query string ignora valores vazios (filtro "Todas" não manda state=).
calls.length = 0
await saveTokens({ access_token: 'novo', refresh_token: 'r2' })
await api.get('/sessions', { state: undefined, limit: 100 })
check('params vazios omitidos da URL', calls[0] === 'GET /api/v1/sessions?limit=100', calls[0])

// 7. URL do WebSocket com token e protocolo corretos.
check(
  'websocket usa ws:// e leva o token',
  socketUrl('/ws/site', accessToken()) === 'ws://localhost:8000/api/v1/ws/site?token=novo',
  socketUrl('/ws/site', accessToken())
)

// 8. Refresh recusado encerra a sessão e avisa o app (é o que desloga a tela).
recusarRefresh = true
await saveTokens({ access_token: 'velho', refresh_token: 'expirado' })
sessaoExpirou = 0
try {
  await api.get('/expira')
  check('refresh recusado propaga erro', false)
} catch {
  check('refresh recusado propaga erro', true)
}
check('sessao expirada notificada ao app', sessaoExpirou === 1, `chamadas=${sessaoExpirou}`)
check(
  'tokens descartados apos refresh recusado',
  currentTokens() === null && !store.has('chargegrid.tokens')
)

// Uma baseUrl vazia nao pode apagar a que ja esta configurada.
//
// O spread aplicava tudo antes da checagem de truthiness, entao '' zerava o
// endereco: as requisicoes saiam relativas ao host - 404 em HTML no lugar de
// JSON, e um WebSocket sem esquema. Nao da erro na configuracao; so' aparece
// na primeira chamada.
const wsAntes = socketUrl('/ws/site', accessToken())
configureSdk({ baseUrl: '' })
check(
  'baseUrl vazia nao apaga a configurada',
  socketUrl('/ws/site', accessToken()) === wsAntes,
  socketUrl('/ws/site', accessToken())
)
configureSdk({ baseUrl: 'http://localhost:8000/' })
check(
  'barra final e removida',
  socketUrl('/ws/site', accessToken()) === wsAntes,
  socketUrl('/ws/site', accessToken())
)

// 9. Fluxo do assistente (SSE sobre fetch).
const { assistant, criarLeitorSse } = sdk
recusarRefresh = false
await saveTokens({ access_token: 'velho', refresh_token: 'r1' })
refreshCount = 0
calls.length = 0
configureSdk({ siteId: 'praca-1' })
const recebidos = []
for await (const evento of assistant.enviar('c1', 'Como está?', { aba: '/ev/power' })) {
  recebidos.push(evento)
}
check(
  'fluxo: 401 antes de abrir renova o token e repete',
  refreshCount === 1 && recebidos.length > 0,
  `refreshCount=${refreshCount}`
)
check(
  'fluxo: leva site_id do seletor e o corpo da pergunta',
  calls.some((c) => c === 'POST /api/v1/assistant/conversations/c1/messages?site_id=praca-1') &&
    pedidoDoFluxo?.texto === 'Como está?' &&
    pedidoDoFluxo?.aba === '/ev/power',
  calls.join(' | ')
)
check(
  'fluxo: eventos inteiros apesar dos pedacos partidos',
  recebidos.map((e) => e.tipo).join(',') === 'meta,ferramenta,delta,delta,fim',
  recebidos.map((e) => e.tipo).join(',')
)
check(
  'fluxo: acento partido entre pedacos chega intacto',
  recebidos
    .filter((e) => e.tipo === 'delta')
    .map((e) => e.texto)
    .join('') === 'Potência disponível: 55 kW'
)
check('fluxo: comentario keep-alive nao vira evento', !recebidos.some((e) => e.tipo === 'message'))
configureSdk({ siteId: undefined })

try {
  for await (const _ of assistant.enviar('cheia', 'oi')) void _
  check('fluxo: 429 antes de abrir vira ApiError', false)
} catch (err) {
  check(
    'fluxo: 429 antes de abrir vira ApiError com a mensagem do servidor',
    err instanceof ApiError && err.status === 429 && err.detail.includes('por minuto'),
    err.detail
  )
}

const parar = new AbortController()
try {
  for await (const evento of assistant.enviar('pendurada', 'oi', { signal: parar.signal })) {
    if (evento.tipo === 'meta') parar.abort()
  }
  check('fluxo: parar interrompe a leitura', false)
} catch (err) {
  check(
    'fluxo: parar interrompe sem se passar por falta de rede',
    err?.name === 'AbortError' && !(err instanceof ApiError),
    String(err)
  )
}

const ler = criarLeitorSse()
const partes = [...ler('event: delta\nda'), ...ler('ta: {"texto":"a"}\n'), ...ler('\n')]
check(
  'leitor SSE: evento partido em tres pedacos sai uma vez',
  partes.length === 1 && partes[0].dados === '{"texto":"a"}'
)

rmSync(saida, { force: true })
console.log(falhas === 0 ? '\nTodos os cenarios passaram.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
