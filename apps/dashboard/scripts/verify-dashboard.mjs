// Verificação em runtime da lógica do painel, sem navegador.
//
//   npm run verify:dashboard
//
// Mesmo formato do `verify-api-client.mjs` do SDK, e pelo mesmo motivo: Node
// puro mais esbuild, sem trazer runner de teste para o projeto. O que dá para
// cobrir assim é a lógica pura — a que decide o que vai para o servidor.
//
// O que NÃO dá é renderização: chave de lista, foco, remoção de linha. Isso
// exige DOM e traria dependências. Está anotado como limite conhecido, não
// como esquecimento.
import { build } from 'esbuild'
import { mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const raiz = fileURLToPath(new URL('..', import.meta.url))
const workspace = fileURLToPath(new URL('../../..', import.meta.url))
const cache = join(workspace, 'node_modules/.cache/chargegrid')
mkdirSync(cache, { recursive: true })
const saida = join(cache, 'painel.mjs')

// Só os módulos puros entram. Importar um `.jsx` puxaria React e o SDK inteiro
// para dentro do Node — e o que se quer verificar não depende de nenhum deles.
await build({
  entryPoints: [join(raiz, 'src/views/ev/orcamento.js')],
  outfile: saida,
  bundle: true,
  format: 'esm',
  platform: 'neutral'
})

const { alteracoesDoOrcamento, mudouPorBaixo } = await import(pathToFileURL(saida).href)

let falhas = 0
const check = (nome, cond, extra = '') => {
  console.log(`${cond ? 'ok  ' : 'FALHA'} ${nome}${extra ? ' -> ' + extra : ''}`)
  if (!cond) falhas++
}
const mesmo = (a, b) => JSON.stringify(a) === JSON.stringify(b)

const CHAVES = [
  'grid_limit_kw',
  'reserved_kw',
  'main_breaker_current_a',
  'battery_min_soc',
  'allow_pv_kw',
  'allow_battery_kw'
]

const base = {
  grid_limit_kw: 75,
  reserved_kw: 20,
  main_breaker_current_a: 100,
  battery_min_soc: 20,
  allow_pv_kw: true,
  allow_battery_kw: true
}

// 1. Nada tocado, nada enviado.
check(
  'rascunho intacto nao gera PATCH',
  mesmo(alteracoesDoOrcamento({ ...base }, base, CHAVES), {}),
  JSON.stringify(alteracoesDoOrcamento({ ...base }, base, CHAVES))
)

// 2. O cenário que motivou tudo isto.
//
// A abre o painel (vê reserva 20). B muda a reserva para 40. A altera só o
// limite da rede e salva. Antes, o PATCH levava `reserved_kw: 20` junto e
// revertia B sem que ninguém visse.
const so_o_limite = alteracoesDoOrcamento({ ...base, grid_limit_kw: 100 }, base, CHAVES)
check(
  'campo nao tocado fica fora do PATCH',
  mesmo(so_o_limite, { grid_limit_kw: 100 }),
  JSON.stringify(so_o_limite)
)
check('reserva alheia nao viaja no PATCH', !('reserved_kw' in so_o_limite))

// 3. String do input não pode virar alteração fantasma.
//
// `<input type="number">` devolve string. Sem a coerção, '75' !== 75 marcaria
// o campo como alterado e ele viajaria por cima do valor de outra pessoa —
// exatamente o problema que este módulo existe para evitar, por outro caminho.
check(
  'string igual ao numero nao conta como alteracao',
  mesmo(alteracoesDoOrcamento({ ...base, grid_limit_kw: '75' }, base, CHAVES), {})
)

// 4. Booleano compara como booleano, não como número.
check(
  'desligar o solar e detectado',
  mesmo(alteracoesDoOrcamento({ ...base, allow_pv_kw: false }, base, CHAVES), { allow_pv_kw: false })
)

// 4b. O caso que exige o desvio de booleano — e que o cenário acima NÃO
//     exige, porque `Number(false) !== Number(true)` já dá a resposta certa.
//
// Aqui a base não traz o campo (resposta antiga, ou coluna recém-adicionada
// que a API ainda não devolvia). Só com número, `Number(undefined ?? 0)` e
// `Number(false)` são ambos 0: a desmarcação sumiria do PATCH, e o operador
// veria o solar voltar sozinho ao orçamento no próximo carregamento.
const semCampo = { ...base }
delete semCampo.allow_pv_kw
check(
  'booleano contra campo ausente conta como alteracao',
  mesmo(alteracoesDoOrcamento({ ...base, allow_pv_kw: false }, semCampo, CHAVES), {
    allow_pv_kw: false
  })
)

// 5. Zero é valor, não ausência.
check(
  'zerar a reserva conta como alteracao',
  mesmo(alteracoesDoOrcamento({ ...base, reserved_kw: 0 }, base, CHAVES), { reserved_kw: 0 })
)

// 6. Campo nulo (o operador limpou para redigitar) contra base numérica.
check(
  'campo limpo difere de valor preenchido',
  'main_breaker_current_a' in
    alteracoesDoOrcamento({ ...base, main_breaker_current_a: null }, base, CHAVES)
)

// ---- aviso de edição concorrente ----

// 7. O que mudou no servidor e eu não toquei: preservado, mas anunciado.
const servidor = { ...base, reserved_kw: 40 }
const meu = alteracoesDoOrcamento({ ...base, grid_limit_kw: 100 }, base, CHAVES)
check(
  'mudanca alheia e sinalizada ao operador',
  mesmo(mudouPorBaixo(servidor, base, CHAVES, meu), ['reserved_kw']),
  JSON.stringify(mudouPorBaixo(servidor, base, CHAVES, meu))
)

// 8. Campo que EU alterei não entra no aviso, mesmo que o servidor também
//    tenha mudado: aí é conflito de verdade, e o meu valor vence — avisar
//    seria dizer que algo será preservado quando não será.
const conflito = alteracoesDoOrcamento({ ...base, reserved_kw: 30 }, base, CHAVES)
check(
  'campo em conflito nao vira aviso de preservacao',
  mesmo(mudouPorBaixo(servidor, base, CHAVES, conflito), [])
)

// 9. Servidor parado: nada a avisar.
check(
  'sem mudanca alheia, sem aviso',
  mesmo(mudouPorBaixo(base, base, CHAVES, meu), [])
)

rmSync(saida, { force: true })
console.log(falhas === 0 ? '\nTodos os cenarios passaram.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
