# Previsão de demanda

Job offline que prevê quanta energia cada eletroposto deve vender no próximo mês
e grava o resultado em `site_forecasts`. **A API nunca executa este código** —
ela apenas lê a tabela.

## Por que fora da API

O processo do FastAPI também roda os workers de potência. Um `import lightgbm`
que falhe, ou um artefato corrompido, derrubaria junto o `rebalance_once` — que
é o que impede o disjuntor de abrir. Previsão de faturamento não pode
compartilhar processo com controle de carga.

Além disso o modelo prevê **mês**: é um cálculo que roda doze vezes por ano.
Servir em processo seria pagar custo contínuo por isso, e `lgb.predict` é
CPU-bound numa API que é async de ponta a ponta.

## Como rodar

Um comando, da raiz do repositório, com a stack já de pé (`npm run infra:up`):

```bash
npm run forecast          # treina e exporta — é isto que um clone novo precisa
```

O modelo **não vai para o git** (2 MB por retreino, diff irrevisável), então todo
ambiente LOCAL novo passa por aqui uma vez. `exportar.py` sem artefato não diz
apenas "não encontrado": ele imprime este comando.

No staging isso é automático — veja a seção sobre o job agendado, mais abaixo.

Os passos separados, quando a diferença importa:

```bash
npm run forecast:train    # treina; imprime backtest e grava metricas_atual.json
npm run forecast:export   # grava o mês+1 de cada praça em site_forecasts
npm run forecast:janelas  # grava as outras janelas, e a previsão da REDE
npm run forecast:folga    # mede quanta folga cada janela tem; não escreve nada
npm run forecast:test     # testes do pipeline (não precisam do banco)
```

`forecast:export` e `forecast:janelas` são irmãos, e a ordem importa: o primeiro
grava **só** o mês+1 de cada praça, que é o único bucket que o modelo consegue
prever — ele é um previsor direto de um mês à frente, e para o mês+2 o histórico
que as features descrevem ainda não existe. O segundo grava as demais janelas e
pula esse bucket de propósito, para não sobrescrever previsão de modelo com régua.

`forecast:folga` é a leitura que decide o desenho: onde a distância entre a melhor
régua e o ruído irredutível é perto de zero, nenhum modelo pode ganhar.

Cadência: treinar por trimestre ou quando a rede mudar, exportar por mês.

O serviço `forecast` existe no `compose.yaml` sob `profiles: ["forecast"]` — fica
fora do `up` porque não é um processo que fica de pé, é um job. Estar no compose
em vez de numa linha de `docker run` no README economiza os três erros de sempre:
o nome da rede, o caminho do volume, e o `POSTGRES_HOST` apontando para
`localhost` de dentro do container.

Para refazer **exatamente** o artefato publicado, o comando está dentro de
`modelos/metricas_atual.json`, no campo `gerado_por`:

```bash
docker compose --env-file apps/api/.env --profile forecast run --rm forecast \
  python treinar.py --ate 2026-08-31
```

Sem linha na tabela, o painel mostra "nenhuma previsão calculada" — que é
melhor que um número inventado.

## No staging, ninguém roda nada

`forecast-staging.yml` roda **todo dia 1** e faz as duas coisas no mesmo job: treina e exporta.

Mensal, e não diário, porque o alvo é o mês seguinte e `exportar.py` grava uma linha por
competência — rodar todo dia reescreveria a mesma linha com um modelo treinado sobre quase o
mesmo histórico. Custo de CI sem informação nova.

Treinar e exportar **no mesmo job** é o que dispensa publicar o artefato: ele nasce num passo, é
lido pelo seguinte e morre com o runner. Nunca precisa atravessar o repositório, porque nunca
precisa sobreviver ao job — e é por isso que a seção abaixo continua valendo.

O job usa a **mesma** `DATABASE_URL_OVERRIDE` do workflow de migrations (`banco.py` troca o
driver para psycopg). Um segundo segredo com o mesmo conteúdo sairia de sincronia, e o sintoma
seria treinar contra um banco e gravar noutro.

O resumo da execução traz o WAPE do modelo contra o da régua — a decisão de o modelo entrar ou a
média móvel prevalecer, que é a única leitura que interessa a quem abre o job.

## O artefato não vai para o git. As métricas vão

O modelo são 2 MB de binário por retreino, com diff que ninguém revisa (o dump
em texto do LightGBM é pior: 6 MB). Já **`modelos/metricas_atual.json`** pesa
1 KB, é texto, e carrega dentro o comando que o refaz — é a *evidência* dos
números publicados aqui. Mesmo critério de `openapi.json` ser versionado: ele
**é** a afirmação, e revisar a mudança dele é exatamente o que se quer.

Isso só vale se o treino for reproduzível, e ele não era. Três coisas faltavam:

| o que faltava | por quê |
|---|---|
| versões **exatas** em `requirements.txt` | `lightgbm>=4.0` treina árvores diferentes em clones construídos com meses de diferença — e o artefato é um *pickle*, que nem carrega entre versões |
| `--ate` explícito | o histórico do seed é ancorado em `now()`, então a janela de treino escorrega com o calendário |
| `num_threads` fixo | a ordem em que as somas parciais se juntam depende da contagem de threads, e ponto flutuante não é associativo |

Verificado: treinos independentes com `--ate 2026-08-31`, na mesma máquina e no
mesmo banco, produzem árvores com o **mesmo SHA-256** e métricas idênticas.

**E um limite que apareceu na prática, vale registrar em vez de esconder.** O
WAPE mensal saiu **8,31%** de manhã e **9,94%** à tarde do mesmo dia — com a
mesma janela, as mesmas 1.647 linhas de treino, os mesmos parâmetros, a mesma
versão de cada biblioteca e a **mesma régua** (7,61% nas duas). Ficou provado
que o treino é determinístico (execuções seguidas batem) e que a ordem das
categorias não influi; **não** ficou provado o que mudou. O banco de
desenvolvimento não guarda versão, então a pergunta virou irrespondível depois
do fato.

**Reinvestigado depois, com o pipeline já estável, e três explicações foram
descartadas** — o episódio continua aberto, mas o espaço de causas é menor:

| hipótese | como foi testada | veredito |
|---|---|---|
| treino não-determinístico | dois treinos seguidos, métricas idênticas ao byte | descartada |
| sensibilidade a threads | `num_threads` 1, 2, 4 e 8 → WAPE 9,26 nos quatro | descartada |
| mudança no código do pipeline | à época `pipeline/train.py` tinha **um único commit**, anterior às duas corridas. Hoje tem três — as réguas do backtest e a perda em `PARAMS` — mas ambos posteriores a este episódio | descartada |
| procedência registrada errada | `--ate` e `reproduzir_com` nasceram às 03:50, antes da corrida das 06:41 | descartada |
| o banco mudou entre as corridas | deslocar a janela em 2 dias move a régua (9,06 → 9,45 → 9,07): régua idêntica em 7,61% **prova dado idêntico** | descartada |

Sobra um episódio cujas premissas verificáveis todas se sustentam e cuja
observação as contradiz — e a razão de ser irrespondível agora é precisa: o seed
consome **um único `random.Random(42)` em sequência**, com a janela ancorada em
`now()`. O banco daquela manhã não é reconstruível nem re-executando o mesmo
seed, porque `now()` andou. A instrumentação abaixo existe para que isso não se
repita, não para explicar o que passou.

Por isso `treinar.py` passou a gravar `impressao_do_treino` — um SHA-256 das
features e do alvo — junto da métrica. Na próxima vez que o número se mexer, a
comparação responde sozinha: hash igual aponta para o ambiente, hash diferente
aponta para o banco. É instrumentação nascida de uma pergunta que não soube
responder.

**E já serviu.** No reseed que trouxe a frota para o seed, a métrica mudou de
novo (9,94% → 9,26%, com a régua indo a 9,07%) — e o hash mudou junto. Pergunta
respondida em dois segundos: o banco é outro, porque o histórico do seed é
ancorado em `now()` e ganhou uma campanha nova. Não há mistério a investigar.

Sobre `deterministic=True` e `force_row_wise=True`, que acompanham o
`num_threads`: são **preventivos, não demonstrados**. A documentação do LightGBM
é explícita quanto ao contrato, mas a divergência por número de threads não foi
reproduzida aqui — `tests/test_determinismo.py` tentou com 900, 8.000 e 30.000
linhas, em máquina de 20 núcleos, e os modelos saíram iguais com e sem as flags.
O teste registra o resultado negativo para ninguém refazer o experimento.

## O que veio do repositório de modelagem

`pipeline/` é cópia de `src/` do projeto original, sem alterações, para poder ser
reatualizado sem conflito. **Não** vieram:

- `simulate/gerador_cdr.py` — o seed do próprio ChargeGrid já gera o histórico.
- `src/ingest/modbus.py` — os endereços de registrador ali são inventados; os
  dados vêm do banco, não do medidor.

`banco.py`, `treinar.py` e `exportar.py` são deste projeto: leem Postgres em vez
de CSV e escrevem na tabela em vez de um arquivo.

Essa divisão é a mesma que o `ruff.toml` daqui usa: **`pipeline/` fica fora do
lint**. Reformatar a cópia produziria exatamente o conflito que ela existe para
evitar, e o diff seria contra código que não é nosso para corrigir — o mesmo
motivo pelo qual o `apps/api` deixa `alembic/versions` de fora. Medido: sob a
régua do projeto o `pipeline/` tem duas violações (`E741` e `I001`), então a
exclusão evita divergir do upstream por duas linhas, não esconde bagunça.

O arquivo de configuração não é cosmético. Sem ele o ruff não encontrava
configuração nenhuma neste diretório e usava o conjunto padrão da **versão
instalada**, que cresce a cada release. Medido no mesmo código, sem config:
**1 erro** com ruff 0.6.8 (o piso que o `apps/api` pede) e **48** com a 0.16.7.
O lint não estava frouxo nem rigoroso — estava indefinido. Com `select` explícito e a versão presa
em `requirements.txt`, duas máquinas cobram a mesma coisa.

    npm run forecast:lint

## Estado atual do modelo — leia antes de confiar no número

Todos os números saem de **`modelos/metricas_atual.json`**, que é versionado e traz
dentro o comando que o refaz. Se a tabela divergir do arquivo, **o arquivo manda**.

| métrica | valor |
|---|---|
| WAPE mensal do modelo | 16,45% |
| WAPE mensal da média móvel de 28 dias | 16,04% |
| WAPE mensal da média por dia da semana | **14,08%** |
| WAPE diário do modelo | 29,42% |
| WAPE diário da melhor régua | **28,79%** |
| Cobertura da faixa p10–p90 | **61,5%** (deveria ser ~80%) |

**O modelo perde das réguas por 2,37 pontos no mensal.** `exportar.py` grava a
régua e `fonte` diz isso. O portão está funcionando: nenhum número pior chega à
tela.

### A vantagem existiu, e era frágil — vale registrar como se perdeu

Por um momento o modelo ganhou: **11,98% contra 13,63%**, a primeira vez na
história do projeto que o portão promoveu o modelo. Aquele número é real e está
no histórico do Git.

Ele desapareceu quando o hardware do seed passou a variar por arquétipo — uma
mudança de **realismo**, feita porque o arquétipo deixou de vir de um mapa de
slugs e passou a ser inferido do equipamento. Sem ela, um shopping e um
condomínio nasciam com o mesmo equipamento de um escritório e eram lidos como
corporativos.

O erro subiu para todos (a melhor régua foi de 13,63% para 14,08%), e para o
modelo subiu muito mais. O diagnóstico por praça mostra onde: as duas praças
**corporativas** erram 29,4% e 17,6% contra 19,5% e 10,1% das réguas. E o
coeficiente de variação diário explica por quê — corporativo e condomínio ficam
em 0,85 contra 0,64 de rodovia e shopping, porque o perfil semanal de escritório
cai a 22% no domingo. Série mais barulhenta, e a vantagem do modelo é a primeira
coisa que o ruído come.

**A leitura honesta não é "o modelo piorou".** É que a vantagem dele era
específica de um recorte do gerador, e uma mudança plausível de hardware a
removeu. Num dado sintético, "o modelo ganha" é propriedade do gerador antes de
ser propriedade do modelo — e essa frase vale para os 11,98% tanto quanto para
os 16,45%.

Não houve ajuste do gerador para recuperar o número. Perseguir acurácia contra
dado inventado é exatamente o que produz um resultado que não se reproduz em
operação real.

### As três mudanças que já foram medidas, e o que cada uma valeu

Partindo de 9,26% contra 9,07% da média móvel, medidas uma a uma. Elas continuam
valendo mesmo com o veredito atual: a perda certa e um gerador mais rico são
melhorias independentes de quem ganha o portão.

**1. A perda estava errada para o alvo.** `treinar_um` usava `objective="l1"`, que
ajusta a **mediana** condicional de um dia — e o número da tela é uma **soma** de
trinta dias. Somar medianas subestima o total, porque energia diária é assimétrica
à direita. `objective="tweedie"` com potência 1,2 é a perda para dado não-negativo
com massa em zero e cauda à direita: **Poisson composto**, que é exatamente o
processo aqui (contagem de sessões × energia lognormal por sessão).

Medido em dois painéis independentes, com o mesmo walk-forward:

| painel | l1 | l2 | tweedie |
|---|---|---|---|
| ChargeGrid | 15,52% | 12,80% | **11,98%** |
| projeto de origem, intocado | 7,78% | 7,79% | **7,24%** |

`l2` melhorou só no primeiro — era artefato do dado. Tweedie melhora nos dois,
inclusive num painel onde o modelo **já** batia a régua, e é isso que justifica a
troca. A perda mora em `PARAMS` e o valor é definido em `treinar.py` (`PERDA`),
pelo mesmo mecanismo com que o determinismo já sobrepõe os parâmetros — a cópia de
`pipeline/` fica configurável em vez de bifurcada.

**2. O gerador não tinha o sinal que o pipeline foi desenhado para achar.** As duas
causas prováveis que este README listava estavam certas, e as duas foram
corrigidas em `app/seed.py`:

- `PESO_DO_MES` era **uma tupla única** para todas as praças. No gerador de origem
  a sazonalidade mensal varia **por arquétipo, com sinais opostos** — uma rodovia
  sobe 30% em janeiro enquanto um corporativo cai 20%. Uma média móvel não tem como
  capturar isso; um modelo com `archetype` como feature tem. Virou `PESOS_MENSAIS`.
- A energia por sessão tinha **mediana e dispersão únicas** (18 kWh, σ 0,55). Um DC
  de 60 kW na estrada não entrega o mesmo que um AC de 22 kW num escritório, e
  local de rotina dispersa menos. Virou `ENERGIA_POR_SESSAO` por arquétipo. Sigma
  alto em local de rotina inventava ruído que não existe — e ruído inventado é erro
  que modelo nenhum remove.
- E havia **uma praça por arquétipo**, o que tornava `archetype` colinear com
  `location_id`: o modelo aprendia "esta praça tem este padrão", nunca "rodovias
  têm este padrão". Agora são duas de cada, oito no total.
- E o **hardware passou a variar por arquétipo** (`PONTOS_POR_CARATER`): DC de
  150 kW na rodovia, DC de 60 kW no shopping, AC trifásico de 22 kW no
  corporativo, AC monofásico de 7,4 kW no condomínio. Não é enfeite: é o que
  permite ao modelo **inferir** o arquétipo do equipamento em vez de lê-lo de uma
  lista de slugs escrita à mão — e foi esta mudança que custou a vantagem
  descrita acima.

**3. Quatro anos em vez de dois.** O backtest treina só com meses anteriores ao mês
de teste; com dois anos, prever julho significava ter visto julho **uma vez**. Isso
sozinho **não resolveu** — a régua também melhorou e o modelo continuou perdendo.
Fica registrado para ninguém refazer a hipótese isolada.

### A folga: onde um modelo pode ganhar, e onde não

`python medir_janelas.py` mede, para cada janela, a distância entre a melhor régua
sem modelo e uma referência **centrada que usa o futuro de propósito**. O que fica
abaixo dela é variação de contagem, não erro de modelo:

| janela | melhor régua | erro | folga |
|---|---|---|---|
| hora (rede) | dow × hora | 50,17% | **−0,05** |
| dia (rede) | dia da semana | 14,91% | +0,30 |
| semana (rede) | média móvel | 7,46% | +0,84 |
| **mês (rede)** | dia da semana | 7,64% | **+3,38** |
| ano | — | — | n=2, não mensurável |

É por isso que **quatro das cinco janelas são servidas por régua**, e `fonte` diz
qual em cada linha gravada. Onde a folga é zero, nenhum modelo pode ganhar —
insistir ali seria gastar complexidade para piorar a tela.

Na janela de **hora** o número honesto não é um ponto: é a faixa p10–p90, e o
critério de aceite dela é **cobertura**, não WAPE.

### O que continua aberto

- **A faixa cobre 61,5% e anuncia 80%** (`metricas_atual.json`). Já mediu 65,2%
  num artefato anterior; os modelos de quantil continuam sub-dispersos: tratar o extremo inferior como pior caso é
  otimismo. A tela mostra o número medido ao operador em vez de escondê-lo.
- **A janela de ano tem n=2.** Quatro anos de histórico dão duas observações anuais
  completas. Ela é servida por extrapolação de tendência e rotulada como tal.
- **Todo o histórico é sintético**, nos dois projetos. O README do repositório de
  origem diz isso em caixa de destaque e manda não usar as métricas como estimativa
  de produção. Vale igual aqui, e com uma consequência específica: **um modelo que
  aprende sazonalidade mensal neste dado está recuperando `PESOS_MENSAIS`.** O
  mecanismo é real para uma rede real; a evidência é circular. Só as comparações
  relativas — modelo contra régua, no mesmo dado — se sustentam.

O caminho honesto segue sendo retreinar quando houver operação real. `treinar.py` é
um comando, e as guardas já apontam quando o resultado não se sustenta.

## A armadilha que nenhum teste unitário pega

`location_id` é o **slug** do site, nunca o `id`. O UUID é sorteado a cada reseed
do banco; o slug é escrito à mão no seed e sobrevive.

Se os slugs do banco divergirem de `estacoes_treinadas` do artefato, o modelo cai
no fallback de média móvel **em silêncio** — sem erro, com a tela continuando a
parecer correta. Por isso `exportar.py` compara os dois conjuntos e imprime os
locais que ficaram de fora.
