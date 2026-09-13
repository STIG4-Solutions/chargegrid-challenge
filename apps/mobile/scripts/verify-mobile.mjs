// Verificação em runtime da lógica do app do motorista, sem simulador.
//
//   npm run verify:mobile
//
// Mesmo formato — e mesmo motivo — do `verify-dashboard.mjs`: Node puro mais
// esbuild, sem trazer runner de teste para um workspace que não tem nenhum.
//
// O app não tinha verificação automática de espécie alguma: `tsc --noEmit` era
// tudo. Typecheck diz que `corpoDaEdicao` devolve um objeto; não diz que ele
// devolve *vazio* quando nada mudou, que é a regra que impede um PATCH de
// reescrever o cadastro inteiro a cada correção de placa.
//
// O que NÃO dá para cobrir aqui é renderização: toque, foco, teclado numérico.
// Isso exigiria react-native em Node. Limite conhecido, anotado — não
// esquecimento.
import { build } from 'esbuild'
import { mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const raiz = fileURLToPath(new URL('..', import.meta.url))
const workspace = fileURLToPath(new URL('../../..', import.meta.url))
const cache = join(workspace, 'node_modules/.cache/chargegrid')
mkdirSync(cache, { recursive: true })
const saidaVeiculo = join(cache, 'veiculo.mjs')
const saidaFrota = join(cache, 'frota.mjs')

// Só os módulos puros entram. Importar um `.tsx` puxaria react-native para
// dentro do Node — e o que se quer verificar não depende dele.
//
// Uma chamada por módulo: com mais de uma entrada o esbuild exige `outdir` e
// passa a decidir os nomes, e o import abaixo deixaria de saber o que procurar.
for (const [entrada, destino] of [
  ['src/veiculo.ts', saidaVeiculo],
  ['src/frota.ts', saidaFrota]
]) {
  await build({
    entryPoints: [join(raiz, entrada)],
    outfile: destino,
    bundle: true,
    format: 'esm',
    platform: 'neutral'
  })
}

const { camposIniciais, comoNumero, corpoDaEdicao, problemaNaEdicao } = await import(
  pathToFileURL(saidaVeiculo).href
)
const { CENTRO_MAXIMO, centrosEmUso, problemaNoCentro, semArea } = await import(
  pathToFileURL(saidaFrota).href
)

let falhas = 0
const check = (nome, cond, extra = '') => {
  console.log(`${cond ? 'ok  ' : 'FALHA'} ${nome}${extra ? ' -> ' + extra : ''}`)
  if (!cond) falhas++
}
const mesmo = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// --------------------------------------------------------------- veículo

const carro = {
  id: 'v1',
  model: 'Nissan Leaf',
  plate: 'ABC1D23',
  battery_kwh: 40,
  max_ac_kw: 7.4,
  vin: '123'
}

// 1. Abrir o editor mostra o que está gravado, e não campos em branco.
check('campos iniciais espelham o carro',
  mesmo(camposIniciais(carro), { modelo: 'Nissan Leaf', placa: 'ABC1D23', bateria: '40' }))
check('bateria ausente vira campo vazio',
  camposIniciais({ ...carro, battery_kwh: null }).bateria === '')

// 2. O PATCH é parcial de verdade. Sem isto, corrigir a placa reescreveria
//    modelo e bateria junto — e um carro com bateria nula seria "corrigido"
//    para nula de novo a cada edição.
check('nada mudou, nada e enviado',
  mesmo(corpoDaEdicao(carro, camposIniciais(carro)), {}))
check('so a placa mudou, so a placa vai',
  mesmo(corpoDaEdicao(carro, { modelo: 'Nissan Leaf', placa: 'XYZ9K88', bateria: '40' }),
    { plate: 'XYZ9K88' }))
check('espaco em volta nao conta como mudanca',
  mesmo(corpoDaEdicao(carro, { modelo: '  Nissan Leaf  ', placa: 'ABC1D23', bateria: '40' }), {}))

// 3. Apagar a placa manda `null`, e não string vazia: o banco guarda ausência
//    como NULL, e `''` seria uma placa que existe e não tem caracteres.
check('placa apagada vira null',
  mesmo(corpoDaEdicao(carro, { modelo: 'Nissan Leaf', placa: '', bateria: '40' }),
    { plate: null }))
check('bateria apagada vira null',
  mesmo(corpoDaEdicao(carro, { modelo: 'Nissan Leaf', placa: 'ABC1D23', bateria: '' }),
    { battery_kwh: null }))

// 4. Vírgula é o separador de quem digita em português. Sem isto, "62,5" vira
//    NaN e o app mandaria lixo para o servidor.
check('virgula e separador decimal', comoNumero('62,5') === 62.5)
check('ponto tambem serve', comoNumero('62.5') === 62.5)
check('texto nao e numero', comoNumero('meia carga') === null)
check('negativo nao e bateria', comoNumero('-5') === null)
check('vazio e ausencia, nao zero', comoNumero('  ') === null)
check('bateria em virgula chega convertida',
  mesmo(corpoDaEdicao(carro, { modelo: 'Nissan Leaf', placa: 'ABC1D23', bateria: '62,5' }),
    { battery_kwh: 62.5 }))

// 5. O modelo é NOT NULL no banco e `max_length=80` no schema. Deixar salvar
//    daria 422 depois do toque, quando dava para dizer antes.
check('modelo vazio impede salvar', problemaNaEdicao(camposIniciais({ ...carro, model: '' })) !== null)
check('modelo so com espaco impede salvar',
  problemaNaEdicao({ modelo: '   ', placa: '', bateria: '' }) !== null)
check('modelo longo demais impede salvar',
  problemaNaEdicao({ modelo: 'x'.repeat(81), placa: '', bateria: '' }) !== null)
check('modelo de 80 passa',
  problemaNaEdicao({ modelo: 'x'.repeat(80), placa: '', bateria: '' }) === null)
check('bateria com letra impede salvar',
  problemaNaEdicao({ modelo: 'Leaf', placa: '', bateria: 'quarenta' }) !== null)
check('edicao valida nao reclama',
  problemaNaEdicao({ modelo: 'Leaf', placa: 'ABC1D23', bateria: '40' }) === null)

// --------------------------------------------------------------- frota

const frota = [
  { id: '1', modelo: 'Kwid', placa: 'AAA1A11', centro_de_custo: 'Logística', motorista: 'Ana' },
  { id: '2', modelo: 'Leaf', placa: 'BBB2B22', centro_de_custo: null, motorista: 'Bruno' },
  { id: '3', modelo: 'e-208', placa: 'CCC3C33', centro_de_custo: '  ', motorista: 'Carla' },
  { id: '4', modelo: 'Dolphin', placa: 'DDD4D44', centro_de_custo: 'Comercial', motorista: 'Davi' },
  { id: '5', modelo: 'Zoe', placa: 'EEE5E55', centro_de_custo: 'Logística', motorista: 'Eva' }
]

// 6. As áreas em uso viram sugestão. É o que evita "Logistica" e "Logística"
//    virarem duas linhas no relatório de rateio.
check('sugestoes sem repetir e em ordem',
  mesmo(centrosEmUso(frota), ['Comercial', 'Logística']))
check('so espaco nao vira sugestao', !centrosEmUso(frota).includes('  '))
check('frota vazia nao sugere nada', mesmo(centrosEmUso([]), []))

// 7. O contador é o mesmo número que o relatório cobra no aviso. Espaço em
//    branco conta como sem área — senão o aviso cobraria um carro que a tela
//    mostra como resolvido.
check('conta os sem area, espaco incluso', semArea(frota) === 2)
check('frota toda classificada nao tem pendencia',
  semArea(frota.filter((v) => v.centro_de_custo?.trim())) === 0)

// 8. Nome vazio não salva: para limpar existe o botão "Sem área", que manda
//    `null` explicitamente. Salvar '' criaria uma área chamada nada.
check('nome vazio impede salvar', problemaNoCentro('   ') !== null)
check('nome longo demais impede salvar', problemaNoCentro('x'.repeat(CENTRO_MAXIMO + 1)) !== null)
check('nome no limite passa', problemaNoCentro('x'.repeat(CENTRO_MAXIMO)) === null)
check('nome comum passa', problemaNoCentro('Logística') === null)

rmSync(saidaVeiculo, { force: true })
rmSync(saidaFrota, { force: true })
console.log(falhas === 0 ? '\nTodos os cenarios passaram.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
