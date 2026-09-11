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

```bash
docker build -t chargegrid-forecast apps/forecast

# Treinar com os dados do banco (uma vez por trimestre, ou quando a rede mudar)
docker run --rm --network backend_default \
  -e POSTGRES_HOST=db -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=... \
  -v "$PWD/apps/forecast/modelos:/forecast/modelos" \
  chargegrid-forecast python treinar.py

# Gerar a previsão do mês e gravar no banco (uma vez por mês)
docker run --rm --network backend_default \
  -e POSTGRES_HOST=db -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=... \
  -v "$PWD/apps/forecast/modelos:/forecast/modelos" \
  chargegrid-forecast python exportar.py
```

Sem linha na tabela, o painel mostra "nenhuma previsão calculada" — que é
melhor que um número inventado.

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
o painel mostra:

| métrica | valor |
|---|---|
| WAPE mensal do modelo | **9,05%** |
| WAPE mensal da média móvel de 28 dias | **7,61%** |
| Cobertura da faixa p10–p90 | **62,3%** (deveria ser ~80%) |

Três meses são doze estação-meses, e a diferença caberia no ruído de amostragem —
por isso a derrota foi remedida em 3, 6 e 12 meses. Ela se repete nos três
(8,31/7,61 · 8,11/7,75 · 11,95/9,61), e nas três estações. Não é azar de recorte.

**O modelo não supera a régua no MENSAL — mas ganha no DIÁRIO**, e a diferença
explica tudo:

| granularidade | modelo | régua |
|---|---|---|
| diário | **29,4%** | 34,3% |
| mensal | 12,0% | **9,6%** |

Medido sobre 36 estação-meses fora da amostra — a janela de doze meses, que é por
que estes números não são os da tabela acima. O modelo aprende o dia a dia — no
`lab-fiap-eco-station`, onde o fim de semana é 4× mais fraco, ele erra 33,6%
contra 52,8% da régua. Mas no total do mês essa vantagem se dissolve: somando 30
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
