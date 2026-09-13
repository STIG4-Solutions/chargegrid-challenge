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
ambiente novo passa por aqui uma vez. `exportar.py` sem artefato não diz apenas
"não encontrado": ele imprime este comando.

Os passos separados, quando a diferença importa:

```bash
npm run forecast:train    # treina; imprime backtest e grava metricas_atual.json
npm run forecast:export   # grava a previsão do mês em site_forecasts
npm run forecast:test     # testes do pipeline (não precisam do banco)
```

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
| mudança no código do pipeline | `pipeline/train.py` tem **um único commit**, anterior às duas corridas | descartada |
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

## Estado atual do modelo — leia antes de confiar no número

O backtest que o artefato carrega — três meses, e é de onde saem os números que
o painel mostra. Todos saem de **`modelos/metricas_atual.json`**, que é versionado
e traz dentro o comando que o refaz:

| métrica | valor |
|---|---|
| WAPE mensal do modelo | **9,26%** |
| WAPE mensal da média móvel de 28 dias | **9,07%** |
| WAPE diário do modelo | 25,94% |
| Cobertura da faixa p10–p90 | **65,2%** (deveria ser ~80%) |

Estes números mudam quando o banco muda — e é para isso que a evidência é
versionada. Se a tabela divergir de `metricas_atual.json`, o arquivo manda.

Três meses são doze estação-meses, e a diferença caberia no ruído de amostragem —
por isso a derrota foi remedida em 3, 6 e 12 meses. Ela se repete nos três
(9,26/9,07 · 9,52/8,97 · 11,03/9,85), e nas três estações. Não é azar de recorte.

**O modelo não supera a régua no MENSAL — mas ganha no DIÁRIO**, e a diferença
explica tudo:

| granularidade | modelo | régua |
|---|---|---|
| diário | **28,9%** | 34,7% |
| mensal | 11,03% | **9,85%** |

Medido sobre 36 estação-meses fora da amostra — a janela de doze meses, que é por
que estes números não são os da tabela acima. O modelo aprende o dia a dia — no
`lab-fiap-eco-station`, onde o fim de semana é 4× mais fraco, ele erra 37,3%
contra 51,0% da régua. Mas no total do mês essa vantagem se dissolve: somando 30
dias, o padrão semanal quase se cancela, e sobra a variância que o modelo
adiciona.

**Combinar os dois não resolve**, e isso foi testado: a correlação entre os erros
mensais é **0,944** — eles erram junto, porque no agregado ambos são
essencialmente "nível × dias". Qualquer peso dado ao modelo piora o WAPE mensal
monotonicamente, em todas as três estações.

Por isso `exportar.py` grava o preditor que **mede melhor**, e a coluna `fonte`
diz qual foi. Não é desistir do modelo: quando ele passar a ganhar — com operação
real, com mais estações —, o próprio backtest inverte a escolha sem ninguém
mexer em código.

Duas causas prováveis para a derrota no mensal, nenhuma investigada a fundo
porque perseguir acurácia contra dado gerado não significa nada:

1. **Três estações treinadas.** O pipeline foi desenhado para oito, e
   `location_id`, `archetype` e `power_type` são features categóricas — com três
   locais elas carregam pouco sinal e sobra espaço para sobreajuste.
2. **Variância diária alta no seed.** Contagem de Poisson multiplicada por
   energia lognormal produz um dia a dia mais ruidoso que o do gerador original,
   e o alvo em razão amplifica isso.

Uma hipótese foi testada e **descartada**: o backtest incluía o mês corrente, que estava pela
metade, e prever um mês inteiro contra nove dias infla o erro. O corte no último mês completo
é correto e ficou — mas não explicava o resultado. Com ele o WAPE piorou de 11,1% para 12,36%
na primeira rodada. Fica registrado para ninguém refazer a hipótese.

O caminho honesto é retreinar quando houver operação real. `treinar.py` é um
comando, e as guardas já apontam quando o resultado não se sustenta.

## A armadilha que nenhum teste unitário pega

`location_id` é o **slug** do site, nunca o `id`. O UUID é sorteado a cada reseed
do banco; o slug é escrito à mão no seed e sobrevive.

Se os slugs do banco divergirem de `estacoes_treinadas` do artefato, o modelo cai
no fallback de média móvel **em silêncio** — sem erro, com a tela continuando a
parecer correta. Por isso `exportar.py` compara os dois conjuntos e imprime os
locais que ficaram de fora.
