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
import { mkdirSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const raiz = fileURLToPath(new URL('..', import.meta.url))
const workspace = fileURLToPath(new URL('../../..', import.meta.url))
const cache = join(workspace, 'node_modules/.cache/chargegrid')
mkdirSync(cache, { recursive: true })
const saida = join(cache, 'painel.mjs')
const saidaCampanha = join(cache, 'campanha.mjs')
const saidaPrevisao = join(cache, 'previsao.mjs')
const saidaContrato = join(cache, 'contrato.mjs')
const saidaManutencao = join(cache, 'manutencao.mjs')
const saidaAuditoria = join(cache, 'auditoria.mjs')
const saidaContas = join(cache, 'contas.mjs')
const saidaAnalytics = join(cache, 'analytics.mjs')
const saidaCarteira = join(cache, 'carteira.mjs')
const saidaPraca = join(cache, 'praca.mjs')
const saidaJanelas = join(cache, 'janelas.mjs')

// Só os módulos puros entram. Importar um `.jsx` puxaria React e o SDK inteiro
// para dentro do Node — e o que se quer verificar não depende de nenhum deles.
//
// Uma chamada por módulo, e não `entryPoints` com os dois: com mais de uma
// entrada o esbuild exige `outdir` e passa a decidir os nomes dos arquivos, e o
// import logo abaixo deixaria de saber o que procurar.
for (const [entrada, destino] of [
  ['src/views/ev/orcamento.js', saida],
  ['src/views/ev/campanha.js', saidaCampanha],
  ['src/views/ev/previsao.js', saidaPrevisao],
  ['src/views/ev/contrato.js', saidaContrato],
  ['src/views/ev/manutencao.js', saidaManutencao],
  ['src/views/ev/auditoria.js', saidaAuditoria],
  ['src/views/ev/contas.js', saidaContas],
  ['src/views/ev/analytics.js', saidaAnalytics],
  ['src/views/ev/carteira.js', saidaCarteira],
  ['src/views/ev/praca.js', saidaPraca],
  ['src/views/ev/janelas.js', saidaJanelas]
]) {
  await build({
    entryPoints: [join(raiz, entrada)],
    outfile: destino,
    bundle: true,
    format: 'esm',
    platform: 'neutral'
  })
}

const { alteracoesDoOrcamento, mudouPorBaixo } = await import(pathToFileURL(saida).href)
const { rotuloDaCategoria, problemaNaResolucao, idadeEmPalavras, diasEmAberto, RESOLUCAO_MINIMA } =
  await import(pathToFileURL(saidaManutencao).href)
const { rotuloDaAcao, mudancas, comoTexto, abasDaSecao, podeEstornar } = await import(
  pathToFileURL(saidaAuditoria).href
)
const {
  NOME_MAXIMO,
  SENHA_MINIMA,
  CAMPOS_DA_CONTA,
  alcanceDoPapel,
  corpoDaConta,
  mensagemDeSucesso,
  mensagemDoErro,
  podeDesligar,
  pracaDaConta,
  problemaNaConta,
  problemasDaConta,
  resumoDoQueFalta,
  rotuloDoPapel,
  ultimoAcesso
} = await import(pathToFileURL(saidaContas).href)
const {
  problemasDaCampanha,
  consumoDoOrcamento,
  situacaoDaCampanha,
  alteracoesDaCampanha,
  corpoDaCampanha
} = await import(pathToFileURL(saidaCampanha).href)
const { bandaConfiavel, superaARegua, temBanda, escalaDaBanda } = await import(
  pathToFileURL(saidaPrevisao).href
)
const { mesesRestantes, multaPorRescisao, pontosExcedentes, proximaCobranca } = await import(
  pathToFileURL(saidaContrato).href
)

// O endereço da API é importado direto, sem passar pelo esbuild: o módulo já é
// `.mjs` e não depende de JSX. É a única peça daqui que lê o disco, e é de
// propósito — o que se quer verificar é justamente a leitura de
// `config/domains.json`.
const { tendencia, topoDaEscala, rotulosDoEixo, participacao } = await import(
  pathToFileURL(saidaAnalytics).href
)

const { problemaNoAjuste, deixariaNegativo, corpoDoAjuste, mensagemDoAjuste } = await import(
  pathToFileURL(saidaCarteira).href
)

const { sugerirSlug, problemaNaPraca, corpoDaPraca, mensagemDaPraca } = await import(
  pathToFileURL(saidaPraca).href
)

const { enderecoDaApi } = await import('./dominios.mjs')

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
  mesmo(alteracoesDoOrcamento({ ...base, allow_pv_kw: false }, base, CHAVES), {
    allow_pv_kw: false
  })
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
check('sem mudanca alheia, sem aviso', mesmo(mudouPorBaixo(base, base, CHAVES, meu), []))

// ---- formulário de campanha ----
//
// O que estas regras protegem é o dinheiro do estabelecimento: uma campanha mal
// formada ou é recusada com uma mensagem que ninguém entende, ou é aceita e
// passa a gastar orçamento de um jeito que quem a criou não previu.

const AMANHA = new Date(Date.now() + 86400000).toISOString()
const DEPOIS = new Date(Date.now() + 30 * 86400000).toISOString()

const cashbackValida = {
  nome: 'Setembro Verde',
  starts_at: AMANHA,
  ends_at: DEPOIS,
  beneficio_tipo: 'cashback_fixo',
  beneficio_valor: 5,
  orcamento_brl: 1000,
  missoes: [{ codigo: 'tres', alvo: 3 }]
}

// 10. O caminho feliz precisa passar, senão os testes abaixo não provam nada:
//     uma função que reprova tudo satisfaria todos os cenários negativos.
check(
  'campanha bem formada nao acusa problema',
  problemasDaCampanha(cashbackValida).length === 0,
  JSON.stringify(problemasDaCampanha(cashbackValida))
)

// ---- o corpo que vai para o servidor ----
//
// A tela guarda tudo como string, e o servidor não aceita string em campo
// numérico nem `''` em campo opcional. É aqui que a tradução acontece, e é aqui
// que ela pode errar em silêncio.

const rascunhoCompleto = {
  ...cashbackValida,
  descricao: '',
  patrocinador: 'site',
  fleet_id: '',
  teto_por_recompensa: '',
  beneficio_valor: '5',
  orcamento_brl: '1000',
  missoes: [{ codigo: 'tres', titulo: 'Tres', metrica: 'sessoes', alvo: '3' }]
}

// 10a. Frota vazia é "todos", e a API espera `null`. Mandar `''` daria 422 num
//      campo que o operador deixou em branco de propósito.
check(
  'frota em branco vira null',
  corpoDaCampanha(rascunhoCompleto).fleet_id === null,
  JSON.stringify(corpoDaCampanha(rascunhoCompleto).fleet_id)
)

// 10b. E a frota escolhida viaja como está.
check(
  'frota escolhida viaja no corpo',
  corpoDaCampanha({ ...rascunhoCompleto, fleet_id: 'abc-123' }).fleet_id === 'abc-123'
)

// 10c. `site_id` nunca sai daqui: quem paga vem do escopo do token. Um campo
//      aceito no corpo deixaria a tela parecer que escolhe.
check(
  'site_id nao viaja no corpo',
  !('site_id' in corpoDaCampanha({ ...rascunhoCompleto, site_id: 'nao-deveria-ir' }))
)

// 10d. Os `<input type="number">` entregam string, e o servidor recusa string
//      em campo numérico.
check(
  'numeros saem como numero',
  typeof corpoDaCampanha(rascunhoCompleto).beneficio_valor === 'number' &&
    typeof corpoDaCampanha(rascunhoCompleto).orcamento_brl === 'number' &&
    typeof corpoDaCampanha(rascunhoCompleto).missoes[0].alvo === 'number'
)

// 10e. Teto em branco é ausência de teto, não zero. Zero seria um teto que
//      impede qualquer recompensa - o oposto de deixar em branco.
check(
  'teto em branco vira null, nao zero',
  corpoDaCampanha(rascunhoCompleto).teto_por_recompensa === null
)

// 11. Cashback sem missão não premia ninguém: não há o que cumprir.
check(
  'cashback sem missao e recusado',
  problemasDaCampanha({ ...cashbackValida, missoes: [] }).some((e) => e.includes('missão'))
)

// 12. Desconto age na fatura, na hora. Missão ali nunca premiaria nada.
check(
  'desconto com missao e recusado',
  problemasDaCampanha({
    ...cashbackValida,
    beneficio_tipo: 'desconto_pct',
    beneficio_valor: 10
  }).some((e) => e.includes('missões'))
)

// 13. Período invertido.
check(
  'termino antes do inicio e recusado',
  problemasDaCampanha({ ...cashbackValida, starts_at: DEPOIS, ends_at: AMANHA }).some((e) =>
    e.includes('depois do início')
  )
)

// 14. Teto acima do orçamento: a primeira recompensa estouraria a campanha.
check(
  'teto maior que o orcamento e recusado',
  problemasDaCampanha({ ...cashbackValida, orcamento_brl: 100, teto_por_recompensa: 500 }).some(
    (e) => e.includes('teto')
  )
)

// 15. Percentual acima de 100 devolveria mais do que o motorista pagou.
check(
  'percentual acima de 100 e recusado',
  problemasDaCampanha({
    ...cashbackValida,
    beneficio_tipo: 'cashback_pct',
    beneficio_valor: 150
  }).some((e) => e.includes('100%'))
)

// 16. Códigos repetidos: o banco tem UNIQUE (campaign_id, codigo) e devolveria
//     um erro de constraint que ninguém sabe ler.
check(
  'missoes com codigo repetido sao recusadas',
  problemasDaCampanha({
    ...cashbackValida,
    missoes: [
      { codigo: 'tres', alvo: 3 },
      { codigo: 'tres', alvo: 5 }
    ]
  }).some((e) => e.includes('mesmo código'))
)

// 17. Campanha SEM orçamento definido não é campanha esgotada.
//
// Pintar a barra cheia diria exatamente o oposto do que é: sem teto, e não sem
// saldo. O operador desligaria uma campanha que ainda está funcionando.
check(
  'sem orcamento a barra fica vazia, nao cheia',
  consumoDoOrcamento({ orcamento_brl: 0, consumido_brl: 0 }) === 0
)
check(
  'consumo e proporcional',
  consumoDoOrcamento({ orcamento_brl: 200, consumido_brl: 50 }) === 25
)
check(
  'consumo nao passa de 100 mesmo estourado',
  consumoDoOrcamento({ orcamento_brl: 100, consumido_brl: 250 }) === 100
)

// 18. `ativa` é intenção; o período é fato.
//
// Uma campanha marcada ativa cujo prazo passou não age sobre nenhuma recarga.
// Mostrá-la como "vigente" faria o operador esperar um efeito que não vem.
const ONTEM = new Date(Date.now() - 86400000).toISOString()
const ANTEONTEM = new Date(Date.now() - 2 * 86400000).toISOString()
check(
  'campanha ativa com prazo vencido aparece como expirada',
  situacaoDaCampanha({ ativa: true, starts_at: ANTEONTEM, ends_at: ONTEM }) === 'expirada'
)
check(
  'campanha ativa que ainda nao comecou aparece como agendada',
  situacaoDaCampanha({ ativa: true, starts_at: AMANHA, ends_at: DEPOIS }) === 'agendada'
)
check(
  'campanha ativa dentro do prazo aparece como vigente',
  situacaoDaCampanha({ ativa: true, starts_at: ONTEM, ends_at: DEPOIS }) === 'vigente'
)
check(
  'campanha desativada aparece como encerrada',
  situacaoDaCampanha({ ativa: false, starts_at: ONTEM, ends_at: DEPOIS }) === 'encerrada'
)

// 19. Mesmo contrato do orçamento: só o que foi tocado viaja.
//
// Aqui isso vale dinheiro — o orçamento é editável, e enviar o rascunho inteiro
// reverteria em silêncio o valor que outra pessoa acabou de ajustar.
const baseCampanha = { nome: 'Setembro', orcamento_brl: 1000, ativa: true }
const CHAVES_CAMPANHA = ['nome', 'orcamento_brl', 'ativa']
check(
  'campanha intacta nao gera PATCH',
  mesmo(alteracoesDaCampanha({ ...baseCampanha }, baseCampanha, CHAVES_CAMPANHA), {})
)
check(
  'orcamento alheio nao viaja no PATCH',
  !(
    'orcamento_brl' in
    alteracoesDaCampanha({ ...baseCampanha, nome: 'Outubro' }, baseCampanha, CHAVES_CAMPANHA)
  )
)
check(
  'string do input numerico nao vira alteracao fantasma',
  mesmo(
    alteracoesDaCampanha({ ...baseCampanha, orcamento_brl: '1000' }, baseCampanha, CHAVES_CAMPANHA),
    {}
  )
)
check(
  'desativar a campanha e detectado',
  mesmo(alteracoesDaCampanha({ ...baseCampanha, ativa: false }, baseCampanha, CHAVES_CAMPANHA), {
    ativa: false
  })
)
// Texto diferente com o mesmo valor numérico não pode ser confundido: 'Setembro'
// e 'Outubro' viram NaN os dois, e comparar como número diria que são iguais.
check(
  'nome trocado e detectado mesmo nao sendo numero',
  mesmo(alteracoesDaCampanha({ ...baseCampanha, nome: 'Outubro' }, baseCampanha, CHAVES_CAMPANHA), {
    nome: 'Outubro'
  })
)

// ---- previsão de demanda ----
//
// Estas regras decidem quanta CONFIANÇA a tela transmite. Um número previsto
// desenhado igual a um número medido diz ao operador que os dois valem o mesmo,
// e ele contrata demanda por isso.

// 20. O caso real medido no retreino: a faixa cobriu 56% do que promete 80%.
//     O "pior caso" desenhado na tela é otimista, e quem dimensiona contrato
//     pelo extremo inferior erra mais do que espera.
check('faixa que cobre 56 quando promete 80 nao e confiavel', bandaConfiavel(56.5, 80) === false)
check('faixa que cobre o prometido e confiavel', bandaConfiavel(80, 80) === true)

// 21. Backtest de três meses tem ruído; acusar por um ponto só geraria alarme.
check('diferenca dentro da tolerancia nao acusa', bandaConfiavel(77, 80) === true)
check('sem medicao nao ha o que acusar', bandaConfiavel(null, 80) === true)

// 22. A régua é uma média móvel de 28 dias — três linhas de código.
//
// O primeiro retreino deu 12,36% contra 9,45% dela. Um modelo que perde não é
// inútil, mas não pode ser apresentado como base de decisão.
check('modelo que erra mais que a regua nao a supera', superaARegua(12.36, 9.45) === false)
check('modelo que erra menos supera', superaARegua(7.78, 10.4) === true)
// Empate conta como derrota: mesmo resultado, e a régua é preferível por ser
// explicável.
check('empate conta como derrota', superaARegua(10, 10) === false)
check('sem metrica a comparacao nao existe', superaARegua(null, 10) === null)

// 23. Banda em volta de uma média móvel daria ares de previsão a uma conta de
//     padaria — e meia banda mente sobre a incerteza declarada.
check(
  'sem historico nao desenha banda',
  temBanda({ fonte: 'media_movel', modelo_aplicavel: false, kwh_p10: 10, kwh_p90: 20 }) === false
)
// O caso que a coluna `fonte` existe para cobrir: o modelo CONHECE o ponto e
// mesmo assim não é usado, porque perde da régua. O número é média móvel, e
// desenhar incerteza em volta dele daria ares de previsão a uma conta.
check(
  'modelo que perde da regua nao desenha banda',
  temBanda({ fonte: 'media_movel', modelo_aplicavel: true, kwh_p10: 10, kwh_p90: 20 }) === false
)
check(
  'banda pela metade nao e desenhada',
  temBanda({ fonte: 'modelo', kwh_p10: 10, kwh_p90: null }) === false
)
check(
  'previsao do modelo com os dois extremos desenha',
  temBanda({ fonte: 'modelo', kwh_p10: 10, kwh_p90: 20 }) === true
)

// 24. A escala da barra.
const comBanda = { fonte: 'modelo', kwh_p10: 5215, kwh_p90: 10005, kwh_previsto: 8283 }
const escala = escalaDaBanda(comBanda)
check(
  'previsto cai dentro da banda desenhada',
  escala.previsto > escala.inicio && escala.previsto < escala.fim
)
check('a banda sobra dos dois lados', escala.inicio > 0 && escala.fim < 100)
check('sem banda nao ha escala', escalaDaBanda({ fonte: 'media_movel' }) === null)
// p10 == p90 seria divisão por zero e a barra sairia com NaN de largura.
check(
  'banda degenerada nao produz escala',
  escalaDaBanda({ fonte: 'modelo', kwh_p10: 100, kwh_p90: 100, kwh_previsto: 100 }) === null
)

// ---- contrato com a plataforma ----
//
// A tela precisa dizer quanto custa rescindir ANTES de o operador confirmar.
// Descobrir depois é a diferença entre uma decisão e uma surpresa — e aqui a
// surpresa tem valor em reais.

const HOJE = new Date('2026-09-10T12:00:00Z')

// 25. Prazo já vencido não pode gerar meses negativos.
//
// Sem o piso em zero a multa vira CRÉDITO: a tela ofereceria dinheiro a quem
// está saindo, que é o oposto do que um prazo mínimo existe para fazer.
check('prazo vencido nao deixa meses negativos', mesesRestantes(HOJE, '2025-01-01') === 0)
check('doze meses inteiros a frente contam doze', mesesRestantes(HOJE, '2027-09-10') === 12)

// 26. O dia importa: dia 20 até dia 10 do mês seguinte não é um mês cheio.
check(
  'mes incompleto nao conta',
  mesesRestantes(new Date('2026-09-20T12:00:00Z'), '2026-10-10') === 0
)
check('mes completo conta', mesesRestantes(HOJE, '2026-10-10') === 1)

// 27. A multa é proporcional ao que faltava.
check('multa de 6 meses a 30% sobre R$100', multaPorRescisao(100, 6, 30) === 180)
check('sem meses restantes nao ha multa', multaPorRescisao(100, 0, 30) === 0)
// Percentual zero é escolha comercial legítima, não bug.
check('percentual zero nao cobra nada', multaPorRescisao(100, 6, 0) === 0)
// Contrato já vencido combinado com a função acima: a cadeia inteira dá zero.
check(
  'prazo vencido nao produz multa pela cadeia inteira',
  multaPorRescisao(100, mesesRestantes(HOJE, '2025-01-01'), 30) === 0
)

// 28. Franquia de pontos: passar dela não é erro, é o gatilho de cobrança.
check('dentro da franquia nao ha excedente', pontosExcedentes(2, 4) === 0)
check('acima da franquia conta a diferenca', pontosExcedentes(6, 4) === 2)
check('franquia ausente trata tudo como excedente', pontosExcedentes(3, undefined) === 3)

// 29. As três parcelas separadas.
//
// Somadas num número só, "R$ 480" não permite conferência — e o lojista vai
// conferir de qualquer jeito, com ou sem a tela ajudando.
const plano = {
  preco_mensal_brl: 149,
  preco_por_ponto_brl: 35,
  pontos_inclusos: 2,
  fee_percent_transacao: 3.5
}
const conta = proximaCobranca(plano, 4, 10000)
check('assinatura entra pelo valor do plano', conta.assinatura === 149)
check('dois pontos excedentes a R$35', conta.pontos === 70)
check('taxa de 3,5% sobre R$10.000', conta.transacao === 350)
check('o total e a soma das tres parcelas', conta.total === 569)
// Site sem faturamento no mês paga só a parte fixa.
const semMovimento = proximaCobranca(plano, 2, 0)
check('sem faturamento a taxa e zero', semMovimento.transacao === 0)
check('sem faturamento resta a mensalidade', semMovimento.total === 149)

// ---- fila de reportes ----
//
// O que estas regras protegem é o tempo de quem vai até o ponto: uma categoria
// impressa como nome de coluna, ou um fechamento vazio, transformam a fila num
// botão de sumir com a reclamação.

// 20. Categoria traduzida. `cabo_danificado` na tela é nome de coluna, e o
//     recibo já cometeu esse erro uma vez.
check(
  'categoria conhecida sai em portugues',
  rotuloDaCategoria('cabo_danificado') === 'Cabo danificado',
  rotuloDaCategoria('cabo_danificado')
)

// 21. Categoria nova na API não pode apagar a linha - é justamente a que
//     ninguém viu ainda que mais interessa aparecer.
check(
  'categoria desconhecida cai no valor cru',
  rotuloDaCategoria('cabo_derretido') === 'cabo_derretido'
)
check('categoria ausente nao quebra', rotuloDaCategoria(undefined) === '—')

// 22. Fechar exige dizer o que foi feito.
check('resolucao vazia e recusada', problemaNaResolucao('   ') !== null)
check('resolucao curta e recusada', problemaNaResolucao('ok') !== null)
check('resolucao descritiva passa', problemaNaResolucao('Cabo trocado') === null)

// 23. O piso espelha o do servidor: descobrir no 422 é a mesma informação
//     chegando tarde.
check(
  'o piso e o mesmo do servidor',
  RESOLUCAO_MINIMA === 3,
  `min_length do ResolucaoIn = ${RESOLUCAO_MINIMA}`
)

// 24. Idade em palavras: a data crua obriga cada um a fazer a conta de cabeça.
const AGORA = new Date('2026-09-12T12:00:00Z')
check('hoje', idadeEmPalavras('2026-09-12T08:00:00Z', AGORA) === 'hoje')
check('ontem', idadeEmPalavras('2026-09-11T08:00:00Z', AGORA) === 'ontem')
check(
  'ha N dias',
  idadeEmPalavras('2026-09-01T12:00:00Z', AGORA) === 'há 11 dias',
  idadeEmPalavras('2026-09-01T12:00:00Z', AGORA)
)

// 25. Data futura não vira idade negativa: relógio de cliente adiantado
//     produziria "há -1 dias" na tela.
check('data futura nao fica negativa', diasEmAberto('2026-09-13T12:00:00Z', AGORA) === 0)
check('data invalida nao quebra', diasEmAberto('nao-e-data', AGORA) === null)

// ---- trilha de auditoria ----
//
// A trilha era gravada e não tinha leitor. O que estas regras protegem é a
// leitura: ação impressa como nome de evento, ou um objeto JSON despejado na
// célula, tornam a tabela ilegível para quem precisa dela.

// 26. Ação traduzida. `carteira.ajustada` é nome de evento.
check(
  'acao conhecida sai em portugues',
  rotuloDaAcao('carteira.ajustada') === 'Saldo corrigido à mão',
  rotuloDaAcao('carteira.ajustada')
)
check('acao desconhecida cai no valor cru', rotuloDaAcao('algo.novo') === 'algo.novo')

// 27. O que interessa a quem audita é o que MUDOU, não o retrato de cada lado.
//
// `mesmo` é PREDICADO, não asserção: solto, o resultado se perde e o cenário
// não verifica nada. Foi o que aconteceu na primeira versão destes três, e o
// teste de mutação pegou — remover o filtro de `mudancas` não quebrava nada.
check(
  'o diff traz so o que mudou',
  mesmo(mudancas({ saldo: 10, motivo: 'x' }, { saldo: 25, motivo: 'x' }), [
    { campo: 'saldo', de: 10, para: 25 }
  ]),
  JSON.stringify(mudancas({ saldo: 10, motivo: 'x' }, { saldo: 25, motivo: 'x' }))
)

// 28. Chave só de um lado também aparece: criar campanha não tem "antes", e é
//     exatamente isso que a linha deve mostrar.
check(
  'campo novo aparece sem antes',
  mesmo(mudancas({}, { nome: 'Setembro' }), [{ campo: 'nome', de: undefined, para: 'Setembro' }])
)

// 29. Objeto igual dos dois lados não polui a lista - comparado por VALOR, e
//     não por referência: dois objetos iguais nunca são o mesmo objeto.
check('objeto igual nao entra no diff', mesmo(mudancas({ cfg: { a: 1 } }, { cfg: { a: 1 } }), []))

// 30. Objeto diferente entra, comparado por valor e não por referência.
check('objeto alterado aparece', mudancas({ cfg: { a: 1 } }, { cfg: { a: 2 } }).length === 1)

// 31. `***` vem mascarado do servidor e passa direto: mascarar de novo
//     esconderia que houve mascaramento, e quem audita precisa ver que ali
//     existia um segredo.
check('a mascara do servidor e preservada', comoTexto('***') === '***')
check('nulo vira travessao', comoTexto(null) === '—' && comoTexto(undefined) === '—')
check('objeto vira json legivel', comoTexto({ a: 1 }) === '{"a":1}')

// 32. A aba de auditoria e' de ADMIN, e nao "de quem ve mais de uma praca". A
//     rota recusa operador, e aba que sempre volta 403 e' pior que aba nenhuma.
const MODS = [{ to: '/ev/power', label: 'Potência' }]
check(
  'operador nao ve a aba de auditoria',
  !abasDaSecao(MODS, { rede: true, isAdmin: false }).some((a) => a.to === '/ev/audit')
)
check(
  'admin ve a aba de auditoria',
  abasDaSecao(MODS, { rede: false, isAdmin: true }).some((a) => a.to === '/ev/audit')
)
check(
  'visao de rede continua sendo por numero de pracas',
  abasDaSecao(MODS, { rede: true, isAdmin: false }).some((a) => a.to === '/ev/portfolio')
)

// 33. Estornar: so' admin, e so' fatura paga. Em aberto devolveria dinheiro que
//     nunca entrou; como operador, devolveria do caixa da rede.
check('operador nao estorna', podeEstornar({ status: 'paid' }, false) === false)
check('admin estorna fatura paga', podeEstornar({ status: 'paid' }, true) === true)
check('fatura em aberto nao estorna', podeEstornar({ status: 'open' }, true) === false)
check('fatura ausente nao quebra', podeEstornar(undefined, true) === false)

// ---------------------------------------------------------------- contas
//
// 34. Operador sem praça é a regra menos óbvia desta tela e a mais cara de
//     errar: `get_scoped_site_id` devolve o PRIMEIRO site da rede para quem não
//     tem `site_id`. O operador não ficaria sem acesso — ficaria com o acesso
//     da praça de outra pessoa, e nada na tela dele diria isso.
const OPERADOR = {
  nome: 'Maria Souza',
  email: 'maria@empresa.com',
  senha: 'senha-comprida',
  papel: 'operator',
  siteId: 's1'
}
check('operador com praca pode', problemaNaConta(OPERADOR) === null)
check('operador SEM praca nao pode', problemaNaConta({ ...OPERADOR, siteId: '' }) !== null)
check('admin sem praca pode', problemaNaConta({ ...OPERADOR, papel: 'admin', siteId: '' }) === null)

// 35. Os pisos espelham o servidor, e errar para menos é melhor que para mais.
check('nome curto nao passa', problemaNaConta({ ...OPERADOR, nome: 'M' }) !== null)
check('email torto nao passa', problemaNaConta({ ...OPERADOR, email: 'maria' }) !== null)
check(
  'senha curta nao passa',
  problemaNaConta({ ...OPERADOR, senha: 'x'.repeat(SENHA_MINIMA - 1) }) !== null
)
check(
  'senha no piso passa',
  problemaNaConta({ ...OPERADOR, senha: 'x'.repeat(SENHA_MINIMA) }) === null
)

// 36. Admin é global: mandar a praça dele sugeriria que ficou restrito a ela.
check('corpo de operador leva a praca', corpoDaConta(OPERADOR).site_id === 's1')
check(
  'corpo de admin nao leva praca',
  corpoDaConta({ ...OPERADOR, papel: 'admin' }).site_id === null
)
check(
  'email vai em minusculas',
  corpoDaConta({ ...OPERADOR, email: '  Maria@Empresa.COM ' }).email === 'maria@empresa.com'
)
check('senha vai como foi digitada', corpoDaConta(OPERADOR).password === 'senha-comprida')

// 37. O servidor recusa desligar a própria conta com 409. O botão nasce apagado
//     em vez de a pessoa descobrir depois do clique.
check('nao desligo a mim mesmo', podeDesligar({ id: 'eu', is_active: true }, 'eu') === false)
check('desligo outro', podeDesligar({ id: 'outro', is_active: true }, 'eu') === true)
check(
  'ja desligado nao desliga de novo',
  podeDesligar({ id: 'outro', is_active: false }, 'eu') === false
)

// 38. Admin sem praça é o NORMAL — ele enxerga a rede inteira. Escrever "—"
//     sugeriria dado faltando, e alguém iria "corrigir".
check(
  'admin sem praca diz que ve a rede',
  pracaDaConta({ role: 'admin', site_nome: null }) === 'toda a rede'
)
check(
  'operador com praca mostra a praca',
  pracaDaConta({ role: 'operator', site_nome: 'Shopping' }) === 'Shopping'
)
check('papel desconhecido nao apaga a linha', rotuloDoPapel('auditor') === 'auditor')
check('papel conhecido e traduzido', rotuloDoPapel('operator') === 'Operador')

// 39. "nunca entrou" é a informação que esta tela existe para dar.
check('sem acesso diz nunca entrou', ultimoAcesso(null) === 'nunca entrou')
check('data invalida nao vira Invalid Date', ultimoAcesso('nao-e-data') === 'nunca entrou')
check('data valida e formatada', /\d{2}\/\d{2}\/\d{4}/.test(ultimoAcesso('2026-09-01T10:00:00Z')))

// 40. A aba de contas é de ADMIN, como a de auditoria: a rota recusa operador,
//     e aba que só devolve 403 é pior que aba nenhuma.
const abasAdmin = abasDaSecao([], { rede: false, isAdmin: true }).map((a) => a.to)
const abasOperador = abasDaSecao([], { rede: false, isAdmin: false }).map((a) => a.to)
check('admin ve a aba de contas', abasAdmin.includes('/ev/users'))
check('operador nao ve a aba de contas', !abasOperador.includes('/ev/users'))

// 40.1 Uma pendencia POR CAMPO, e nao so' a primeira. Com uma mensagem de cada
//      vez a pessoa descobre os problemas em fila — corrige o nome e aparece o
//      e-mail — e a mensagem solta nao diz a qual dos cinco campos se refere.
const VAZIA = { nome: '', email: '', senha: '', papel: 'operator', siteId: '' }
const problemasVazia = problemasDaConta(VAZIA)
check(
  'formulario vazio acusa os quatro campos de uma vez',
  Boolean(
    problemasVazia.nome && problemasVazia.email && problemasVazia.senha && problemasVazia.siteId
  )
)
check(
  'campo bom nao vira pendencia',
  problemasDaConta(OPERADOR).nome === null && problemasDaConta(OPERADOR).siteId === null
)
check(
  'so a praca pendente acusa so a praca',
  problemasDaConta({ ...OPERADOR, siteId: '' }).siteId !== null &&
    problemasDaConta({ ...OPERADOR, siteId: '' }).nome === null
)
// O mapa e a pergunta curta nao podem divergir: `problemaNaConta` e derivada.
check(
  'a primeira pendencia sai do mapa',
  problemaNaConta(VAZIA) === problemasVazia.nome &&
    problemaNaConta({ ...OPERADOR, siteId: '' }) === problemasVazia.siteId
)

// 40.2 O teto de 160 e' do servidor. Sem ele aqui, o nome comprido so' e'
//      recusado depois do POST, com um 422 que fala de `full_name`.
check(
  'nome no teto passa',
  problemasDaConta({ ...OPERADOR, nome: 'a'.repeat(NOME_MAXIMO) }).nome === null
)
check(
  'nome acima do teto nao passa',
  problemasDaConta({ ...OPERADOR, nome: 'a'.repeat(NOME_MAXIMO + 1) }).nome !== null
)

// 40.3 Botao desabilitado sem motivo visivel e' beco sem saida: o resumo diz
//      TUDO o que falta, inclusive dos campos em que ninguem mexeu ainda.
check(
  'o resumo lista as quatro pendencias',
  resumoDoQueFalta(VAZIA) === 'Ainda falta: nome, e-mail, senha e praça.'
)
check('formulario completo nao tem resumo', resumoDoQueFalta(OPERADOR) === null)
check(
  'pendencia unica sai no singular',
  resumoDoQueFalta({ ...OPERADOR, siteId: '' }) === 'Ainda falta: praça.'
)
// Admin nao tem praca: cobra-la dele seria cobrar o que a tela nem oferece.
check(
  'o resumo do admin nunca cobra praca',
  !/praça/.test(resumoDoQueFalta({ ...VAZIA, papel: 'admin' }) ?? '')
)
// A dica da senha cita o piso do servidor. Escrita a' mao, continuaria dizendo
// "8" no dia em que `SENHA_MINIMA` virasse 10 — e dica que mente e' pior que
// dica nenhuma.
check('a dica da senha cita o piso real', CAMPOS_DA_CONTA.senha.dica.includes(String(SENHA_MINIMA)))
check(
  'a dica da senha avisa que nao ha troca no primeiro acesso',
  /primeiro acesso/.test(CAMPOS_DA_CONTA.senha.dica)
)

// 40.4 O 409 e' o caso comum e o unico que a pessoa resolve sozinha: e-mail
//      repetido quase sempre e' conta DESLIGADA na lista logo abaixo. O
//      `detail` cru diz que ja' existe e para por ai'.
check('409 manda procurar na lista', /religar/i.test(mensagemDoErro({ status: 409, detail: 'x' })))
check('404 manda recarregar as pracas', /praça/i.test(mensagemDoErro({ status: 404, detail: 'x' })))
check(
  'erro sem traducao mantem o detail do servidor',
  mensagemDoErro({ status: 400, detail: 'campo invalido' }) === 'campo invalido'
)
check('erro sem detail nao mostra vazio', mensagemDoErro({ status: 500 }).length > 0)
check('sem erro, sem mensagem', mensagemDoErro(null) === null)

// 40.5 Fechar o formulario e recarregar uma lista de vinte linhas nao e' aviso
//      de sucesso: a linha nova entra no meio, em ordem alfabetica. A
//      confirmacao repete o e-mail e lembra da senha que so' o admin conhece.
const sucesso = mensagemDeSucesso({ ...OPERADOR, email: '  Maria@Empresa.COM ' })
check('o sucesso repete o e-mail normalizado', sucesso.includes('maria@empresa.com'))
check('o sucesso nomeia a pessoa', sucesso.includes('Maria Souza'))
check('o sucesso lembra que a senha nao sera trocada', /primeiro acesso/.test(sucesso))
check(
  'o sucesso diz o papel criado',
  mensagemDeSucesso({ ...OPERADOR, papel: 'admin' }).includes('administrador')
)

// 40.6 "Operador | Administrador" sozinho nao diz a ninguem qual dos dois a
//      pessoa do caixa precisa ser. O alcance e' a unica diferenca que decide.
check('operador enxerga so a praca', /praça/.test(alcanceDoPapel('operator')))
check('admin enxerga a rede', /rede/.test(alcanceDoPapel('admin')))
check('papel desconhecido nao inventa alcance', alcanceDoPapel('auditor') === null)

rmSync(saidaContas, { force: true })
// ------------------------------------------------- endereço da API por ambiente
//
// 41. Esta é a decisão mais silenciosa do projeto quando erra: o endereço vai
//     ASSADO no pacote, então um build de staging que saia apontando para
//     produção abre, carrega e mostra dados — do ambiente errado, sem nada na
//     tela indicando isso. A mutação encontrou este ponto sem guarda: desligar
//     o ramo de staging fazia `build:staging` assar produção em silêncio.
const dev = enderecoDaApi(true, 'development')
const prod = enderecoDaApi(false, 'production')
const stg = enderecoDaApi(false, 'staging')

check('dev aponta para a maquina local', /localhost|127\.0\.0\.1/.test(dev))
check(
  'producao aponta para o dominio de producao',
  /^https:\/\/api\./.test(prod) && !/staging/.test(prod)
)
check('staging aponta para o dominio de staging', /^https:\/\/api\.staging\./.test(stg))
check('staging e producao NAO sao o mesmo endereco', stg !== prod)
check('nenhum dos tres sai vazio', Boolean(dev && prod && stg))

// ---------------------------------------------------------------------------
// Analytics: o que faz um grafico afirmar o que o dado nao sustenta.

const serieZerada = [
  { dia: '2026-09-17', receita_brl: 0, energia_kwh: 0 },
  { dia: '2026-09-18', receita_brl: 0, energia_kwh: 0 }
]
const serieCheia = [
  { dia: '2026-09-12', receita_brl: 100, energia_kwh: 40 },
  { dia: '2026-09-13', receita_brl: 0, energia_kwh: 0 },
  { dia: '2026-09-14', receita_brl: 120, energia_kwh: 45 },
  { dia: '2026-09-15', receita_brl: 200, energia_kwh: 70 },
  { dia: '2026-09-16', receita_brl: 210, energia_kwh: 75 },
  { dia: '2026-09-17', receita_brl: 180, energia_kwh: 60 }
]

// Serie zerada dividindo a altura da barra por zero produz Infinity/NaN, e o
// estrago vai para ATRIBUTO de SVG - nao aparece como texto na tela, entao
// teste de renderizacao que procura 'NaN' no conteudo passa batido.
check('topo da escala nunca e zero', topoDaEscala(serieZerada, 'receita_brl') === 1)
check(
  'altura da barra continua finita com serie zerada',
  Number.isFinite((0 / topoDaEscala(serieZerada, 'receita_brl')) * 100)
)
check('topo da escala e o maior valor da serie', topoDaEscala(serieCheia, 'receita_brl') === 210)
check(
  'topo considera todos os campos pedidos',
  topoDaEscala(serieCheia, ['receita_brl', 'energia_kwh']) === 210
)

// Duas amostras de um dia cada nao sao tendencia, sao ruido - e uma seta verde
// sobre ruido e' pior que seta nenhuma.
check('tendencia recusa amostra curta', tendencia(serieCheia.slice(0, 3), 'receita_brl') === null)
check('tendencia recusa o que nao e lista', tendencia(null, 'receita_brl') === null)
check(
  'tendencia recusa primeira metade zerada (divisao por zero)',
  tendencia(
    [{ receita_brl: 0 }, { receita_brl: 0 }, { receita_brl: 50 }, { receita_brl: 50 }],
    'receita_brl'
  ) === null
)
check('tendencia sobe quando a segunda metade rende mais', tendencia(serieCheia, 'receita_brl') > 0)
check(
  'tendencia cai quando a segunda metade rende menos',
  tendencia([...serieCheia].reverse(), 'receita_brl') < 0
)

// O ultimo dia e' o que a pessoa procura primeiro: nao pode faltar no eixo.
const eixo = rotulosDoEixo(serieCheia, 3)
check('o eixo sempre inclui o ultimo dia', eixo[eixo.length - 1] === serieCheia.length - 1)
check('o eixo nao repete indice', new Set(eixo).size === eixo.length)
check('eixo de serie vazia nao estoura', mesmo(rotulosDoEixo([], 6), []))

const fatias = participacao(
  [
    { code: 'CP-02', receita_brl: 200 },
    { code: 'CP-01', receita_brl: 700 },
    { code: 'CP-03', receita_brl: 100 }
  ],
  'receita_brl'
)
check('participacao ordena do maior para o menor', fatias[0].code === 'CP-01')
check('participacao soma 100%', Math.round(fatias.reduce((s, f) => s + f.pct, 0)) === 100)
check('participacao sem receita devolve lista vazia', mesmo(participacao([], 'receita_brl'), []))
check(
  'participacao com tudo zerado nao divide por zero',
  mesmo(participacao([{ code: 'CP-01', receita_brl: 0 }], 'receita_brl'), [])
)

// ---------------------------------------------------------------------------
// Ajuste manual de saldo: o unico lancamento em que alguem escolhe o numero.

check('valor vazio e recusado', problemaNoAjuste({ valor: '', motivo: 'x' }) !== null)
check('zero e recusado', problemaNoAjuste({ valor: '0', motivo: 'correcao' }) !== null)
check('texto no valor e recusado', problemaNoAjuste({ valor: 'abc', motivo: 'x' }) !== null)
check('motivo vazio e recusado', problemaNoAjuste({ valor: '50', motivo: '   ' }) !== null)
check(
  'motivo acima de 200 e recusado',
  problemaNoAjuste({ valor: '50', motivo: 'a'.repeat(201) }) !== null
)
check('ajuste completo passa', problemaNoAjuste({ valor: '-50', motivo: 'estorno' }) === null)
check('negativo e' + ' aceito', problemaNoAjuste({ valor: '-1', motivo: 'ok' }) === null)

// Saldo devedor seria credito que ninguem autorizou - a carteira e' pre-paga.
check('debito maior que o saldo e sinalizado', deixariaNegativo({ valor: -100, saldoAtual: 50 }))
check('debito dentro do saldo nao e sinalizado', !deixariaNegativo({ valor: -50, saldoAtual: 50 }))
check('credito nunca deixa negativo', !deixariaNegativo({ valor: 100, saldoAtual: 0 }))
check('saldo desconhecido nao inventa aviso', deixariaNegativo({ valor: -1 }) === null)

// Teclado brasileiro produz virgula; manda-la crua daria 422 sobre um valor
// que a pessoa digitou certo.
check(
  'virgula vira ponto no corpo',
  corpoDoAjuste({ valor: '10,50', motivo: ' x ' }).valor === 10.5
)
check('motivo vai sem espaco sobrando', corpoDoAjuste({ valor: '1', motivo: ' x ' }).motivo === 'x')

// "-50" e "+50" diferem por um caractere: a frase e' a ultima chance de
// perceber que o lancamento saiu invertido.
check(
  'debito e anunciado como debito',
  mensagemDoAjuste({ valor: -50, saldoNovo: 10 }).startsWith('Debitado')
)
check(
  'credito e anunciado como credito',
  mensagemDoAjuste({ valor: 50, saldoNovo: 110 }).startsWith('Creditado')
)

// ---------------------------------------------------------------------------
// Cadastro de praca: o identificador e o orcamento.

// O slug e' a chave estavel entre reconstrucoes do banco, e e' por ela que o
// artefato do modelo de previsao reconhece o local. Acento e maiuscula
// produziriam duas grafias do mesmo lugar - e a segunda cai em fallback
// silencioso, sem erro nenhum.
check('slug tira acento', sugerirSlug('Praça São João') === 'praca-sao-joao')
check('slug baixa a caixa', sugerirSlug('Shopping MORUMBI') === 'shopping-morumbi')
check('slug troca pontuacao por hifen', sugerirSlug('Posto BR-101, km 68') === 'posto-br-101-km-68')
check('slug nao comeca nem termina com hifen', sugerirSlug('  --Posto--  ') === 'posto')
check('slug colapsa hifens repetidos', !sugerirSlug('a   b').includes('--'))
check('slug de nome vazio e vazio', sugerirSlug('') === '')
check('slug respeita o teto de 40', sugerirSlug('a'.repeat(60)).length <= 40)

const ok = { nome: 'Shopping X', slug: 'shopping-x', limite: '150', reserva: '30', uf: 'SP' }
check('praca completa passa', problemaNaPraca(ok) === null)
check('nome curto e recusado', problemaNaPraca({ ...ok, nome: 'X' }) !== null)
check('slug com maiuscula e recusado', problemaNaPraca({ ...ok, slug: 'Shopping-X' }) !== null)
check('slug com espaco e recusado', problemaNaPraca({ ...ok, slug: 'shopping x' }) !== null)
check('slug com hifen duplo e recusado', problemaNaPraca({ ...ok, slug: 'a--b' }) !== null)
check('uf de uma letra e recusada', problemaNaPraca({ ...ok, uf: 'S' }) !== null)
check('uf vazia e aceita', problemaNaPraca({ ...ok, uf: '' }) === null)

// Orcamento negativo nao falha: a praca fica de pe, aparece no seletor e rateia
// zero para todos os pontos - a tela parece funcionar.
check('limite zero e recusado', problemaNaPraca({ ...ok, limite: '0' }) !== null)
check('limite vazio e recusado', problemaNaPraca({ ...ok, limite: '' }) !== null)
check('reserva igual ao limite e recusada', problemaNaPraca({ ...ok, reserva: '150' }) !== null)
check('reserva maior que o limite e recusada', problemaNaPraca({ ...ok, reserva: '200' }) !== null)
check('reserva negativa e recusada', problemaNaPraca({ ...ok, reserva: '-1' }) !== null)
check('reserva zero e aceita', problemaNaPraca({ ...ok, reserva: '0' }) === null)

const corpo = corpoDaPraca({ ...ok, cidade: ' Sao Paulo ', uf: 'sp' })
check('a UF vai em maiuscula', corpo.estado === 'SP')
check('a cidade vai sem espaco sobrando', corpo.cidade === 'Sao Paulo')
check('cidade vazia vira nulo', corpoDaPraca({ ...ok, cidade: '  ' }).cidade === null)
check('o limite vai como numero', corpo.limite_da_rede_kw === 150)

// Com a segunda praca o seletor passa a existir; quem nao souber disso procura
// a praca nova numa tela que ainda mostra a antiga.
check(
  'a mensagem da segunda praca cita o seletor',
  mensagemDaPraca({ nome: 'X', total: 2 }).includes('seletor')
)
check(
  'a mensagem da primeira nao cita o seletor',
  !mensagemDaPraca({ nome: 'X', total: 1 }).includes('seletor')
)

// ---------------------------------------------------------------------------
// Todo `className` tem regra no CSS?
//
// Isto nasceu de um defeito real: a coluna de situacao da aba Contas usava
// `badge ok` e `badge warn`, e nenhuma das duas existia na folha de estilo. As
// pilulas "Ativa" e "Desligada" saiam com a MESMA aparencia - exatamente o
// oposto do que aquela coluna serve para mostrar.
//
// Classe que nao existe nao quebra nada: o navegador ignora em silencio, a tela
// carrega, e so' quem conhece o desenho pretendido percebe. Por isso e' o tipo
// de defeito que sobrevive a revisao e a teste de renderizacao - `getByText`
// acha "Ativa" do mesmo jeito.
//
// Cobre tambem className montado por template literal, que e' onde o defeito
// estava: o pedaco de texto dentro de `${cond ? 'x' : 'y'}` entra na conta.
const fontesJsx = []
const varrer = (dir) => {
  for (const entrada of readdirSync(dir, { withFileTypes: true })) {
    const caminho = join(dir, entrada.name)
    if (entrada.isDirectory()) varrer(caminho)
    else if (entrada.name.endsWith('.jsx')) fontesJsx.push(caminho)
  }
}
varrer(join(raiz, 'src'))

const css = []
const varrerCss = (dir) => {
  for (const entrada of readdirSync(dir, { withFileTypes: true })) {
    const caminho = join(dir, entrada.name)
    if (entrada.isDirectory()) varrerCss(caminho)
    else if (entrada.name.endsWith('.css')) css.push(readFileSync(caminho, 'utf8'))
  }
}
varrerCss(join(raiz, 'src'))
const definidas = new Set([...css.join('\n').matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]))

const semRegra = new Map()
for (const arquivo of fontesJsx) {
  const fonte = readFileSync(arquivo, 'utf8')
  const pedacos = []
  for (const m of fonte.matchAll(/className=["']([^"']+)["']/g)) pedacos.push(m[1])
  for (const m of fonte.matchAll(/className=\{`([^`]*)`\}/g)) {
    // fora das interpolacoes, e os literais de texto de dentro delas
    pedacos.push(m[1].replace(/\$\{[^}]*\}/g, ' '))
    for (const lit of m[1].matchAll(/['"]([\w -]+)['"]/g)) pedacos.push(lit[1])
  }
  for (const m of fonte.matchAll(/className=\{['"]([^'"]+)['"]/g)) pedacos.push(m[1])
  for (const classe of pedacos.join(' ').split(/\s+/).filter(Boolean)) {
    if (!definidas.has(classe)) {
      const onde = semRegra.get(classe) ?? new Set()
      onde.add(arquivo.split(/[\\/]/).pop())
      semRegra.set(classe, onde)
    }
  }
}
check(
  'todo className do painel tem regra no CSS',
  semRegra.size === 0,
  [...semRegra].map(([c, onde]) => `${c} (${[...onde].join(', ')})`).join('; ')
)

// ---- previsão por janela ----
//
// Cinco janelas, e elas NÃO vêm da mesma origem. A folga medida entre a melhor
// régua sem modelo e o ruído irredutível é de −0,05 ponto na hora e +3,38 no mês:
// onde a folga é zero, nenhum modelo pode ganhar, e a tela tem de dizer que
// aquilo é uma média. Apresentar média como previsão é o defeito que a coluna
// `fonte` existe para impedir.

const {
  JANELAS_DE_PREVISAO,
  rotuloDaFonte,
  rotuloDoBucket,
  temFaixaNaSerie,
  topoDaSerie,
  totaisDaSerie
} = await import(pathToFileURL(saidaJanelas).href)

// 1. As cinco janelas estão declaradas, e só elas.
check(
  'as cinco janelas de previsao estao declaradas',
  mesmo(
    JANELAS_DE_PREVISAO.map((j) => j.chave),
    ['hora', 'dia', 'semana', 'mes', 'ano']
  ),
  JSON.stringify(JANELAS_DE_PREVISAO.map((j) => j.chave))
)

// 2. Só `modelo` é modelo. Régua rotulada como modelo é exatamente o que a
//    coluna `fonte` existe para impedir.
// As fontes que o CHECK `fonte_conhecida` do banco aceita (migração 0029). A
// lista está aqui inteira de propósito: uma fonte nova ausente daqui não faria
// nenhuma verificação falhar — ela só deixaria de ser conferida, e a tela
// passaria a mostrar o valor cru do banco sem ninguém notar.
const FONTES_DO_BANCO = [
  'modelo',
  'media_movel',
  'media_dow',
  'perfil_hora',
  'tendencia',
  'ano_a_ano'
]

check(
  'so a fonte modelo conta como modelo',
  rotuloDaFonte('modelo').eModelo === true &&
    FONTES_DO_BANCO.filter((f) => f !== 'modelo').every(
      (f) => rotuloDaFonte(f).eModelo === false
    ),
  JSON.stringify(['media_dow', 'ano_a_ano'].map((f) => rotuloDaFonte(f)))
)

// 2b. Toda fonte que o banco aceita tem texto PRÓPRIO na tela. Sem isto,
//     `ano_a_ano` cairia no `?? String(fonte)` e o operador leria o nome da
//     coluna do banco — e a régua de ano-a-ano erra 8,67% contra 13,95% da
//     média móvel, então chamar as duas pelo mesmo nome esconde 3,6 pontos.
check(
  'toda fonte do banco tem texto proprio',
  FONTES_DO_BANCO.every((f) => rotuloDaFonte(f).texto !== f),
  JSON.stringify(FONTES_DO_BANCO.filter((f) => rotuloDaFonte(f).texto === f))
)

// 3. Fonte desconhecida NÃO é promovida a modelo por omissão. Um valor novo no
//    banco tem de aparecer estranho na tela, não ganhar o selo de previsão.
check(
  'fonte desconhecida nao vira modelo',
  rotuloDaFonte('chute_novo').eModelo === false &&
    rotuloDaFonte(null).eModelo === false &&
    rotuloDaFonte(undefined).eModelo === false,
  JSON.stringify(rotuloDaFonte('chute_novo'))
)

// 4. Faixa só quando TODOS os buckets a trazem. Meia curva com banda sugere que
//    a incerteza acabou no meio do caminho.
const serieComFaixa = [
  { kwh_previsto: 10, kwh_p10: 5, kwh_p90: 18 },
  { kwh_previsto: 12, kwh_p10: 6, kwh_p90: 20 }
]
const faixaPelaMetade = [serieComFaixa[0], { kwh_previsto: 12, kwh_p10: null, kwh_p90: null }]
check(
  'faixa so quando a serie inteira a declara',
  temFaixaNaSerie(serieComFaixa) === true &&
    temFaixaNaSerie(faixaPelaMetade) === false &&
    temFaixaNaSerie([]) === false,
  `${temFaixaNaSerie(serieComFaixa)} / ${temFaixaNaSerie(faixaPelaMetade)}`
)

// 5. A escala considera o p90. Escalar pelo previsto cortaria a faixa superior
//    na borda, e banda cortada mente sobre o quanto o número pode variar.
check(
  'a escala sobe ate o p90, nao ate o previsto',
  topoDaSerie(serieComFaixa) === 20,
  String(topoDaSerie(serieComFaixa))
)

// 6. Série vazia ou zerada não zera a escala: dividir por zero apaga o gráfico.
check(
  'escala nunca e zero',
  topoDaSerie([]) === 1 && topoDaSerie([{ kwh_previsto: 0 }]) === 1,
  `${topoDaSerie([])} / ${topoDaSerie([{ kwh_previsto: 0 }])}`
)

// 7. Cada janela rotula o eixo do jeito que ela pede. A hora SEM a hora é
//    inútil, e o ano com dia e mês é ruído.
const bucketDeHora = '2026-09-24T20:00:00-03:00'
const SP = 'America/Sao_Paulo'
check(
  'o rotulo da janela horaria traz a hora',
  /\dh$/.test(rotuloDoBucket(bucketDeHora, 'hora', SP)),
  rotuloDoBucket(bucketDeHora, 'hora', SP)
)

// 7b. O FUSO manda, nao o relogio da maquina. O mesmo instante rotulado em dois
//     fusos tem de dar horas diferentes - e e' o que impede a curva do dia de
//     sair deslocada para quem abre a tela fora do fuso da praca. O CI pegou
//     isso rodando em UTC.
check(
  'o rotulo horario segue o fuso declarado',
  rotuloDoBucket(bucketDeHora, 'hora', SP) === '24/09 20h' &&
    rotuloDoBucket(bucketDeHora, 'hora', 'UTC') === '24/09 23h',
  `${rotuloDoBucket(bucketDeHora, 'hora', SP)} / ${rotuloDoBucket(bucketDeHora, 'hora', 'UTC')}`
)
check(
  'o rotulo da janela anual e so o ano',
  /^\d{4}$/.test(rotuloDoBucket('2027-01-01T00:00:00-03:00', 'ano', SP)),
  rotuloDoBucket('2027-01-01T00:00:00-03:00', 'ano', SP)
)
check(
  'o rotulo semanal se distingue do diario',
  rotuloDoBucket(bucketDeHora, 'semana', SP) !== rotuloDoBucket(bucketDeHora, 'dia', SP) &&
    rotuloDoBucket(bucketDeHora, 'semana', SP).startsWith('sem '),
  `${rotuloDoBucket(bucketDeHora, 'semana', SP)} / ${rotuloDoBucket(bucketDeHora, 'dia', SP)}`
)
check(
  'rotulo de data invalida nao vira "Invalid Date" na tela',
  rotuloDoBucket('nao e data', 'dia', SP) === '' && rotuloDoBucket(null, 'hora', SP) === '',
  `"${rotuloDoBucket('nao e data', 'dia', SP)}"`
)

// 8. Faturamento da REDE vem NULO, e não zero. A rede é gravada sem reais porque
//    somar praças com tarifas diferentes daria um preço que não existe em
//    contrato nenhum - e zero afirmaria que a rede não fatura.
const serieDaRede = [{ kwh_previsto: 100 }, { kwh_previsto: 200 }]
const serieDaPraca = [
  { kwh_previsto: 100, faturamento_previsto_brl: 260 },
  { kwh_previsto: 200, faturamento_previsto_brl: 520 }
]
check(
  'faturamento ausente vira nulo, nao zero',
  totaisDaSerie(serieDaRede).brl === null && totaisDaSerie(serieDaRede).kwh === 300,
  JSON.stringify(totaisDaSerie(serieDaRede))
)
check(
  'faturamento presente e somado',
  totaisDaSerie(serieDaPraca).brl === 780,
  JSON.stringify(totaisDaSerie(serieDaPraca))
)

rmSync(saida, { force: true })
rmSync(saidaCampanha, { force: true })
rmSync(saidaManutencao, { force: true })
rmSync(saidaAuditoria, { force: true })
rmSync(saidaPrevisao, { force: true })
rmSync(saidaContrato, { force: true })
rmSync(saidaAnalytics, { force: true })
rmSync(saidaCarteira, { force: true })
rmSync(saidaPraca, { force: true })
rmSync(saidaJanelas, { force: true })
console.log(falhas === 0 ? '\nTodos os cenarios passaram.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
