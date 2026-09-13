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
const saidaCampanha = join(cache, 'campanha.mjs')
const saidaPrevisao = join(cache, 'previsao.mjs')
const saidaContrato = join(cache, 'contrato.mjs')
const saidaManutencao = join(cache, 'manutencao.mjs')
const saidaAuditoria = join(cache, 'auditoria.mjs')

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
  ['src/views/ev/auditoria.js', saidaAuditoria]
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
const {
  rotuloDaCategoria,
  problemaNaResolucao,
  idadeEmPalavras,
  diasEmAberto,
  RESOLUCAO_MINIMA
} = await import(pathToFileURL(saidaManutencao).href)
const { rotuloDaAcao, mudancas, comoTexto, abasDaSecao, podeEstornar } = await import(
  pathToFileURL(saidaAuditoria).href
)
const {
  problemasDaCampanha,
  consumoDoOrcamento,
  situacaoDaCampanha,
  alteracoesDaCampanha,
  corpoDaCampanha
} =
  await import(pathToFileURL(saidaCampanha).href)
const { bandaConfiavel, superaARegua, temBanda, escalaDaBanda } =
  await import(pathToFileURL(saidaPrevisao).href)
const { mesesRestantes, multaPorRescisao, pontosExcedentes, proximaCobranca } =
  await import(pathToFileURL(saidaContrato).href)

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
check('sem orcamento a barra fica vazia, nao cheia', consumoDoOrcamento({ orcamento_brl: 0, consumido_brl: 0 }) === 0)
check('consumo e proporcional', consumoDoOrcamento({ orcamento_brl: 200, consumido_brl: 50 }) === 25)
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
  !('orcamento_brl' in alteracoesDaCampanha({ ...baseCampanha, nome: 'Outubro' }, baseCampanha, CHAVES_CAMPANHA))
)
check(
  'string do input numerico nao vira alteracao fantasma',
  mesmo(alteracoesDaCampanha({ ...baseCampanha, orcamento_brl: '1000' }, baseCampanha, CHAVES_CAMPANHA), {})
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
check('previsto cai dentro da banda desenhada', escala.previsto > escala.inicio && escala.previsto < escala.fim)
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
check('mes incompleto nao conta', mesesRestantes(new Date('2026-09-20T12:00:00Z'), '2026-10-10') === 0)
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
  mesmo(mudancas({}, { nome: 'Setembro' }), [
    { campo: 'nome', de: undefined, para: 'Setembro' }
  ])
)

// 29. Objeto igual dos dois lados não polui a lista - comparado por VALOR, e
//     não por referência: dois objetos iguais nunca são o mesmo objeto.
check('objeto igual nao entra no diff', mesmo(mudancas({ cfg: { a: 1 } }, { cfg: { a: 1 } }), []))

// 30. Objeto diferente entra, comparado por valor e não por referência.
check(
  'objeto alterado aparece',
  mudancas({ cfg: { a: 1 } }, { cfg: { a: 2 } }).length === 1
)

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

rmSync(saida, { force: true })
rmSync(saidaCampanha, { force: true })
rmSync(saidaManutencao, { force: true })
rmSync(saidaAuditoria, { force: true })
rmSync(saidaPrevisao, { force: true })
rmSync(saidaContrato, { force: true })
console.log(falhas === 0 ? '\nTodos os cenarios passaram.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
