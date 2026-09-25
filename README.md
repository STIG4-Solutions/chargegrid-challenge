# ChargeGrid Intelligence

Plataforma de orquestração de recarga EV para **estabelecimentos comerciais**
(FIAP × GoodWe, EV Challenge 2026).

O desafio aponta três lacunas nos eletropostos de hoje, e a linha GoodWe HCA G2 confirma
cada uma: o carregador só protege o próprio disjuntor, o SEMS+ não expõe API de EV Charger,
e sem OCPP não existe cobrança. A plataforma cobre esses três vazios.

| Parte | Onde | Stack | Para quem |
|---|---|---|---|
| API | `apps/api/` | Python · FastAPI · PostgreSQL | — |
| Dashboard comercial | `apps/dashboard/` | React 19 · Vite | operador do estabelecimento |
| App do motorista | `apps/mobile/` | React Native · Expo (iOS + Android) | usuário final |
| Cliente compartilhado | `packages/sdk/` | TypeScript | os dois clientes |
| Previsão de demanda | `apps/forecast/` | Python · LightGBM | job offline, fora da API |
| Site institucional | `apps/site/` | React 19 · Vite | visitante — **andaime**, sem conteúdo ainda |

## O que cada lado faz

A seção **Recarga EV** tem doze abas. A primeira resume; as três seguintes operam o presente;
as demais decidem o futuro — é onde o painel deixa de relatar e passa a recomendar.

| Aba | Pergunta que responde |
|---|---|
| Analytics | como a operação está indo — receita e energia dia a dia, e de quem ela depende |
| Gerenciamento de Potência | quanto cada ponto pode puxar agora, sem estourar o padrão |
| Ciclo da Sessão | o que está acontecendo em cada recarga, com timeline auditável |
| Tarifação & Pagamento | quanto custa, por janela horária, e como se cobra |
| Demanda Contratada | qual demanda contratar — e quanto o rateio já poupou de multa |
| Ocupação & Retorno | qual ponto se paga, e qual está ocupado sem faturar |
| Regras de Prioridade | quem carrega quando falta potência, e por quê |
| Visão de Rede | qual praça segura a operação (aparece com mais de um site) |
| Campanhas | quanto custa comprar comportamento do motorista, e se comprou |
| Plano & Contrato | o que a praça paga à GoodWe, e quanto custa sair antes do prazo |
| Contas | quem opera a rede — criar, listar, ligar e desligar (**admin**) |
| Auditoria | quem fez o quê, com dinheiro e com permissão (**admin**) |

### App do motorista

O básico já estava lá: encontrar estação, ler o QR do carregador, iniciar e acompanhar a
recarga, agendar vaga, ver faturas e gerenciar veículos e carteira. O que veio depois usa dados
que a API já produzia e ninguém mostrava:

| Recurso | O que muda para quem dirige |
|---|---|
| Teto da recarga | "carregue até 30 kWh / 45 min / R$ 50" — o servidor já parava sozinho, faltava a tela |
| Quando começar | "comece às 21h e pague 33% menos", pelo mesmo motor que vai faturar |
| Notificação push | recarga concluída, vez na fila, parada por falha — sem precisar do app aberto |
| Recibo em PDF | o documento que vai para a prestação de contas da empresa |
| Reportar problema | cabo cortado e vaga ocupada não têm sensor; o motorista vê antes |
| Modo frota | gasto por centro de custo, para quem paga a conta de vários carros |
| Missões | o que falta para o próximo cashback, com o progresso real de cada meta |
| Plano de recarga | assinatura mensal: desconto em toda recarga e franquia de kWh |

Dois deles fecham ciclo com o painel: o reporte alimenta a manutenção preditiva — um ponto com
duas reclamações e nenhum sinal de sensor sobe para prioridade alta —, e o conselho de horário
sai das mesmas janelas tarifárias que o operador configura.

As missões fecham um terceiro: o operador cria a campanha numa aba, e é ela que aparece como
meta no app. O que ele gasta ali volta como número na tela dele — quantas pessoas alcançou,
quantas cumpriram, quanto do orçamento saiu.

## Retenção: quem paga o quê

Três mecanismos, e trocar o bolso de qualquer um produz um modelo que não se sustenta.

| Mecanismo | Quem paga | Quando o motorista sente |
|---|---|---|
| Desconto na fatura | o estabelecimento | na hora de decidir onde carregar |
| Cashback na carteira | a rede | depois, e por isso ele volta |
| Plano de recarga | o próprio motorista | em toda recarga, por assinatura |

Desconto sai da margem do estabelecimento naquela sessão — é comercial clássico, e se consome
onde nasce. Cashback vira crédito de carteira, que só vale **dentro da plataforma** e é
resgatável em qualquer site: um estabelecimento que o bancasse estaria financiando uma recarga
que amanhã acontece no concorrente. Por isso quem banca é a rede.

Quando assinatura e campanha valem juntas, o motorista recebe **o melhor de cada componente,
nunca a soma**. Somar produziria desconto sem teto que ninguém orçou; deixar a campanha vencer
tiraria de quem pagou o que ele comprou.

Do outro lado, o estabelecimento assina a plataforma com prazo mínimo. `minimo_ate` **não
avança na renovação automática** — prender por mais doze meses quem apenas deixou o contrato
correr é abusivo. A cobrança é emitida, não liquidada: não há integração bancária, e a baixa é
manual, feita por admin. Isso está declarado na tela e na resposta da API.

## Previsão de demanda, e por que ela mora fora

`apps/forecast/` prevê quanto cada eletroposto deve vender no próximo mês. É um job offline, e
a API apenas **lê** a tabela que ele escreve.

A separação não é estética. O processo do FastAPI também roda os workers de potência: um
`import lightgbm` que falhe derrubaria junto o rebalanceamento — que é o que impede o disjuntor
de abrir. Previsão de faturamento não pode compartilhar processo com controle de carga.

**Hoje o modelo perde das réguas**, no diário e no mensal — e o mensal é a granularidade que a
tela mostra. WAPE, de `apps/forecast/modelos/metricas_atual.json`:

| granularidade | modelo | média móvel de 28 dias | média por dia da semana |
|---|---|---|---|
| diário | 29,42% | 36,26% | **28,79%** |
| mensal | 16,45% | 16,04% | **14,08%** |

Medido em três meses fora da amostra (jun–ago/2026, 21 estação-meses). A faixa p10–p90 cobre
61,5% dos dias, contra os 80% que anuncia. O arquivo traz o comando que o refaz; se esta tabela
divergir dele, o arquivo manda.

Então o job grava **o preditor que mede melhor**, e a coluna `fonte` diz qual foi. Não é
desistir do modelo: quando ele passar a ganhar — com operação real, com mais estações —, o
próprio backtest inverte a escolha sem ninguém mexer em código.
`apps/forecast/README.md` detalha.

## Assistente do operador

Um botão no canto do painel abre um assistente (Azure OpenAI) que responde perguntas de
operação em português: "vou estourar a demanda nas próximas horas?", "qual ponto se paga?",
"tenho cobrança em atraso?". Ele não é uma interface a mais sobre os dados: é a camada que
traduz o que as nove abas já calculam — potência, rateio, receita, ocupação, previsão,
manutenção — em resposta gerencial, que é o papel de NLP que o desafio pede.

**Todo número vem de uma ferramenta, e toda ferramenta é a rota GET da aba.** O modelo não
consulta o banco e não recebe uma cópia dos dados: ele escolhe entre 24 ferramentas, e cada uma
chama a mesma rota que a aba correspondente chama. Uma consulta "equivalente" escrita de novo
divergiria na primeira correção que só uma das duas recebesse, e o assistente passaria a
responder um número que a aba não mostra.

As guardas que valem mesmo se o modelo desobedecer ficam no código, não no prompt:

| Guarda | Onde |
|---|---|
| A praça vem do token (`ScopedSiteId`); nenhuma ferramenta aceita `site_id`, e argumento desconhecido é erro | `tools.py` |
| Ferramenta roda em savepoint `READ ONLY` com `statement_timeout`: escrever falha no Postgres | `guardrails.py` |
| Ferramenta de rede (`visao_da_rede`) só existe para admin — nem aparece na lista do operador | `tools.py` |
| Cota por usuário (minuto e dia), contada no banco | `guardrails.py` |
| Canário no system prompt: se aparecer na saída, a resposta é barrada | `guardrails.py` |
| Filtro de conteúdo e Prompt Shields do deployment Azure, traduzidos em evento `bloqueado` | `client.py` |
| Teto de rodadas de ferramenta; a última vai sem ferramentas e obriga a responder | `orchestrator.py` |
| Conversa presa à praça em que nasceu; trocar de praça abre outra | `api/v1/assistant.py` |

**Especificação técnica vem da documentação, não da memória do modelo.** A ferramenta
`buscar_documentacao` faz busca textual (BM25) no manual, no datasheet e no mapa Modbus do HCA G2,
na mentoria da GoodWe e nas regras de negócio deste README. A imagem Docker só leva `apps/api`,
então os documentos têm uma cópia gerada em `app/services/assistant/conhecimento/`
(`python -m scripts.exportar_conhecimento`), e `test_conhecimento.py` recusa a cópia desatualizada
— o mesmo arranjo do `openapi.json`.

**Custo, medido no `gpt-5.4-mini`:** uma pergunta típica usa ~5,8 mil tokens de entrada, dos quais
~78% saem do cache de prompt do Azure (a parte fixa — ferramentas e instruções — vem primeiro de
propósito), e ~100 de saída: cerca de US$ 0,002 por pergunta. Três tetos em tokens protegem o
crédito da conta: por resposta (`ASSISTANT_MAX_INPUT_TOKENS_PER_ANSWER`, a rodada seguinte vai
sem ferramentas), por usuário e por instalação a cada 24 h (`ASSISTANT_DAILY_TOKENS_PER_USER`,
`ASSISTANT_DAILY_TOKENS_TOTAL`, 429 na pergunta seguinte).

Cada pergunta, cada chamada de ferramenta (com argumentos e resultado) e cada resposta ficam em
`assistant_messages`, com tokens e latência — é o rastro de onde saiu cada número. Mensagem
barrada sai do histórico que volta ao modelo; senão a conversa inteira seria recusada dali em
diante.

Desligado por padrão (`ASSISTANT_ENABLED=false`): a API sobe sem Azure nenhum e o widget não
aparece. O SDK do `openai` só é importado na primeira conversa, pelo mesmo motivo que o
LightGBM mora fora — o processo da API também roda o rebalanceamento de potência.

`pytest` cobre o código com um modelo roteirizado. O que o modelo **de verdade** faz diante de
jailbreak, pedido do prompt, injeção escondida num reporte de motorista e perguntas-ouro (o
número tem de bater com a aba) é medido por `python -m scripts.redteam_assistente`, fora do CI:
custa tokens e não é determinístico. Rode ao trocar de deployment, de modelo ou de prompt.

## Rodar

**Backend** (sobe Postgres, migra, popula e serve):

O seed gera **dois anos de histórico**: 4 sites, ~17.800 sessões faturadas, campanhas com
missões já em progresso — uma delas dirigida a uma frota, com dois dos cinco motoristas
dentro dela —, planos de assinatura e um contrato de plataforma. Não é enfeite —
o modelo de previsão descarta local com menos de 150 dias de energia, os relatórios de ocupação
medem janelas de 30 dias, e uma missão de "recarregue 5 vezes este mês" é indemonstrável com
uma semana de dados. Com poucos dias no banco, as três entregam tela vazia e parecem quebradas.

A **forma** é determinística por semente fixa: mesma quantidade de sessões, mesmos perfis
semanais, mesmos valores. As **datas** não — o histórico é ancorado em `now()`, então máquinas
que semeiam em dias diferentes têm janelas diferentes. Para previsão isso importa: o artefato é
reproduzível com `--ate` explícito e o mesmo banco, não entre bancos semeados em dias distintos.
`apps/forecast/README.md` detalha, incluindo um caso em que a métrica se mexeu e não deu para
provar por quê.


```bash
cp apps/api/.env.example apps/api/.env
# Preencha os valores de apps/api/.env antes de continuar.
npm run infra:up          # API em http://localhost:8000
npm run forecast          # treina o modelo e grava a previsão do mês
```

O `forecast` é **uma vez por ambiente local**: o modelo não vai para o git (2 MB por retreino,
diff irrevisável), então um clone novo mostra "nenhuma previsão calculada" até esse comando rodar.

**No staging isso é automático.** O workflow `forecast-staging.yml` roda todo dia 1 e faz as duas
coisas no MESMO job — treina e exporta. É por isso que o `.joblib` nunca precisa atravessar o
repositório: ele nasce num passo, é lido pelo seguinte e morre com o runner. O resumo da execução
traz o WAPE do modelo contra o da régua, que é a decisão de o modelo entrar ou a média móvel
prevalecer.

**Dashboard:**

```bash
npm install
npm run dev                        # http://localhost:5173
```

O servidor de desenvolvimento aponta sozinho para `http://localhost:8000`: ele lê o bloco
`desenvolvimento` de `config/domains.json`, enquanto o build usa o de produção. Só é preciso
`VITE_API_URL` em `apps/dashboard/.env` para apontar para outro lugar.

**App do motorista:**

```bash
npm run mobile                     # ou mobile:android / mobile:ios
```

Isso abre no **Expo Go** — escaneie o QR do terminal, ou tecle `a`/`i` para
emulador. Para o app com ícone próprio na gaveta, sem o Expo Go no meio, o
build sai pela nuvem (`apps/mobile/README.md` explica por que não sai
localmente no Windows):

```bash
cd apps/mobile && npx eas-cli build -p android --profile preview
```

Contas criadas pelo seed:

| Perfil | E-mail | Senha |
|---|---|---|
| Operador | `operador@chargegrid.com.br` | `SEED_OPERATOR_PASSWORD` |
| Admin | `admin@chargegrid.com.br` | `SEED_ADMIN_PASSWORD` |
| Motorista | `joao.silva@email.com` | `SEED_DRIVER_PASSWORD` |

**Não há senha escrita no repositório.** Deixe essas variáveis em branco no
`apps/api/.env` e o seed sorteia uma senha para cada perfil, imprimindo-as **uma única
vez** ao rodar — anote. Preencha-as se quiser senhas estáveis entre recriações do banco.

Para o dashboard oferecer os atalhos de login em desenvolvimento, repita as senhas em
`VITE_DEMO_*_PASSWORD` no `apps/dashboard/.env`; sem isso os botões não aparecem e você digita.

### Medição do site

Não há smart meter físico ligado a esta instalação, então um worker sintetiza a curva do dia
na mesma tabela que um medidor real alimentaria: geração solar em meia senoide entre 6h e 18h,
consumo do prédio maior em horário comercial, bateria descarregando na ponta (18h–21h).
Nada mais no sistema sabe que a origem é sintética — trocar por um coletor Modbus é substituir
`apps/api/app/workers/virtual_meter.py`, sem tocar no domínio.

Controlado por `METER_SOURCE`: `virtual` (padrão) ou `push`, que só aceita o que chegar por
`POST /power/meter-readings`.

Os comandos acima partem da raiz do repositorio. Veja [desenvolvimento local](docs/development.md),
[estrutura do repositorio](docs/repository-structure.md), [deploy da API](docs/api-deployment.md)
e [como contribuir](CONTRIBUTING.md).

> No Windows, use `POSTGRES_HOST=127.0.0.1` e não `localhost`: o nome resolve para `::1` e o
> asyncpg morre na negociação SSL.

## Endereços: um arquivo só

`config/domains.json` é a fonte única. Mudar o domínio ali muda backend,
dashboard e app:

```json
{
  "protocolo": "https",
  "api": "api.stig4.com",
  "dashboard": "dashboard.stig4.com",
  "site": "stig4.com"
}
```

Cada consumidor aceita **variável de ambiente por cima**, porque em produção o
endereço costuma vir do ambiente e não do repositório:

| Onde | Variável | Sem ela |
|---|---|---|
| Backend (CORS) | `CORS_ORIGINS` | domínio do dashboard + `localhost:5173` — mas ver abaixo |
| Dashboard | `VITE_API_URL` | domínio da API, embutido no build |
| App | `EXPO_PUBLIC_API_URL` | máquina do bundle em dev; domínio no APK |

> **Em `staging` e `prod`, `CORS_ORIGINS` é obrigatória.** O padrão inclui
> `localhost` para o desenvolvimento funcionar sem configuração, e a aplicação
> **recusa subir** com qualquer endereço local nesses ambientes. Sem isso ela
> subiria deixando `localhost` liberado em produção — ou, na imagem Docker
> (que não carrega `config/domains.json`), com CORS só local e o dashboard real
> bloqueado.

O app resolve em três degraus: `EXPO_PUBLIC_API_URL`, depois o IP da máquina que
serve o bundle (só existe com servidor de desenvolvimento), depois o domínio.
É o `hostUri` nulo que distingue um APK instalado de uma sessão de
desenvolvimento — não há flag para manter em dia.

> **No APK o endereço é congelado no build.** Um app instalado não lê
> configuração de servidor, então trocar de domínio exige gerar o pacote de
> novo. Isso só mudaria com um app que buscasse a configuração ao abrir — o que
> troca uma dependência de build por uma de rede no arranque.

A base das URLs impressas nos adesivos de QR sai do mesmo arquivo. Sem isso, um
adesivo já colado apontaria para o domínio antigo depois de qualquer troca.

## Por que um repositório só

As features atravessam a fronteira o tempo todo nesta fase. Adicionar um campo costuma
significar, de uma vez: schema do backend, `openapi.json`, tipos do SDK, endpoint do SDK e a
tela que o consome. Aqui isso é **um commit atômico**, verificável de uma vez — separado,
seriam dois ou três commits em repositórios diferentes, com uma janela em que ficam
inconsistentes.

O backend continua fazendo deploy sozinho: o Docker constrói com contexto `./apps/api` e não
arrasta `node_modules`. Vale dividir quando o backend tiver cadência própria de release, ou
quando mais de uma pessoa passar a mexer só num lado.

Uma demonstração autônoma do dashboard — que roda sem backend nenhum, com um servidor falso em
memória — vive à parte, em
[`demo-charge-grid`](https://github.com/STIG4-Solutions/demo-charge-grid).

## O SDK é o acoplamento entre os clientes

Nenhuma tela faz `fetch`. Tudo passa pelo `@chargegrid/sdk`, que concentra renovação de
token, tradução de erro, formatação e os hooks de dados. O que difere entre web e mobile cabe
em uma linha, no arranque de cada app:

```js
configureSdk({ baseUrl, storage: localStorage })   // dashboard
configureSdk({ baseUrl, storage: AsyncStorage })   // app do motorista
```

`TokenStorage` tem a mesma assinatura do `localStorage` e aceita retorno síncrono ou
`Promise` — por isso o `AsyncStorage` entra sem adaptador. Como o armazenamento pode ser
assíncrono, o SDK mantém um cache em memória: `hydrateTokens()` lê o disco uma vez no
bootstrap e `accessToken()` responde de forma síncrona depois (a URL do WebSocket precisa do
token na hora).

O SDK é consumido como **código-fonte TypeScript, sem etapa de build**: Vite e Metro compilam
o mesmo arquivo, e não existe artefato intermediário para ficar desatualizado.

Os tipos vêm do contrato, não de cópia manual:

```bash
npm run gen:types      # apps/api/openapi.json -> packages/sdk/src/schema.ts
npm run typecheck      # onde a incompatibilidade aparece
```

## Uma versão de React, cravada

`dashboard` e `mobile` declaram **exatamente** `react@19.2.3` — a versão que o React Native
0.86 exige.

Não é preciosismo. Com versões diferentes o npm aninha uma delas, e qual sobe para a raiz do
workspace é imprevisível; como `packages/sdk` fica ao lado dos dois, um `import ... from
'react'` feito lá dentro podia acabar carregando o React do outro app. Duas cópias no mesmo
bundle quebram todo hook com *"Invalid hook call"*. Ao mexer nessas versões, confira:

```bash
npm ls react           # tem que aparecer uma única
```

## Quem vê o quê no painel

Três papéis, e só dois entram no painel comercial:

| Papel | No painel | Escopo |
|---|---|---|
| `admin` | Tudo, incluindo **Contas** (`/ev/users`) e **Auditoria** (`/ev/audit`) | A rede inteira — escolhe qualquer praça pelo seletor |
| `operator` | Tudo menos essas duas abas | Uma praça só, a do próprio `site_id` |
| `driver` | Só o app | — |

**O front esconde, o servidor recusa.** Um motorista consegue fazer login no painel — o
emissor de token é o mesmo do app —, e encontra um painel que responde 403 em cada chamada.
Esconder a aba de Auditoria de um operador é conveniência, não permissão: a rota recusaria
de qualquer jeito. Uma aba que só devolve 403 é pior que aba nenhuma.

O admin não precisa de conta de operador para ver uma praça pelos olhos dela: o seletor de
praça injeta `site_id` em toda requisição, e cada aba passa a responder como se ele fosse o
operador daquele estabelecimento. `apps/dashboard/README.md` detalha as abas, os perfis e a
troca de praça.

## Verificação

```bash
npm run verify:api                         # 17 cenários do SDK com fetch simulado
npm run verify:dashboard                   # 206 cenários da lógica do painel, sem navegador
npm run verify:mobile                      # 49 cenários da lógica do app, sem simulador
npm run test:dashboard                     # 124 testes de renderização (vitest + jsdom)
npm run test:mobile                        # 13 testes de renderização do app (jest-expo + RNTL)
npm run typecheck                          # tipos do SDK e do app contra o contrato
npm run format:check                       # Prettier no lado JS (`npm run format` corrige)
npm run build                              # dashboard
npm run build:staging                      # dashboard apontando para api.staging.stig4.com
cd apps/api && python -m pytest -q          # 757 testes (precisa do Postgres)
cd apps/api && python -m ruff check .
cd apps/api && python -m ruff format --check .
cd apps/api && python -m scripts.smoke_test # 117 cenários ponta a ponta (API no ar)
cd apps/api && python -m scripts.redteam_assistente # ataque e perguntas-ouro contra o Azure real
npm run gen:contrato                       # regera openapi.json e os tipos do SDK
npm run forecast:test                      # 4 testes do pipeline de previsão
npm run forecast:lint                      # regra e forma no código de previsão que é deste projeto
npm run bundle -w @chargegrid/mobile       # empacota o app (Metro + Hermes), como o CI faz
```

**O contrato é gerado, não editado.** `openapi.json` é a fonte de
`packages/sdk/src/schema.ts` — e portanto dos tipos com que o painel e o app
foram escritos. Havia `gen:types` para ir do JSON aos tipos e **nada** para ir
do app ao JSON: o arquivo era mantido à mão, e chegou a divergir em 30 rotas sem
que nada acusasse. Uma das divergências não era cosmética: `RatingOut.desconto`
existia na API e não no contrato, então o desconto da prévia era invisível para
todo cliente tipado. `npm run gen:contrato` refaz os dois elos, e
`test_contrato_openapi.py` recusa o arquivo fora de sincronia.

O `format:check` é a contraparte JS do `ruff format --check`, e a configuração
**ratifica** o estilo em vez de trocá-lo: os padrões do Prettier iriam contra o
código em três pontos, então foram medidos antes de configurar — 0 linhas com
ponto-e-vírgula, 49 aspas simples contra 0 duplas, 62 literais sem vírgula final
contra 0 com. Ficam de fora o que é **gerado** (`schema.ts`, `openapi.json` — este
último tem os bytes assertados por teste, e reindentá-lo quebraria a suíte da API
a partir do painel), o Markdown (prosa quebrada à mão) e o YAML.

O `ruff format --check` entrou depois do `ruff check`, e não junto com ele por
acaso: o projeto passou muito tempo com o primeiro limpo e o segundo nunca
executado — 63 arquivos divergiam do formatador sem que nada reclamasse. As
exclusões valem para os dois (`alembic/versions` e `apps/forecast/pipeline`).

As duas linhas de previsão existem porque o `apps/forecast` ficava **fora
do alcance de qualquer comando daqui**. Elas levam `--build` como o
`forecast:train` sempre levou, e isso não é detalhe de desempenho: o serviço
copia o código na construção da imagem, então sem `--build` o comando verifica a
cópia do último build e **passa sobre código que você acabou de quebrar** — um
portão que diz "tudo certo" é pior que portão nenhum. Foi assim que a primeira
versão destes dois comandos nasceu, e foi um teste de mutação que pegou. O lint era o caso pior: sem `ruff.toml`
no diretório, o ruff caía no conjunto padrão da versão instalada — que cresce de
versão para versão —, então o escopo do lint dependia de qual ruff a máquina
tinha. Agora a régua é a mesma do `apps/api` (`select = ["E", "F", "I", "UP",
"B"]`), e `pipeline/` fica de fora por ser cópia literal do projeto de modelagem.

O `verify:api` roda contra um armazenamento **assíncrono de propósito** — o do React Native.
Se passa nele, passa no `localStorage` síncrono da web.

O `verify:dashboard` é Node puro mais esbuild, sem runner, e cobre a lógica que decide **o
que vai para o servidor**: o diff do editor de orçamento, a validação do formulário de
campanha, a calibração da faixa de previsão e o cálculo da multa de rescisão.

O `verify:mobile` é o mesmo formato aplicado ao app do motorista, que até então não tinha
verificação automática nenhuma — `tsc --noEmit` era tudo. Typecheck garante que `corpoDaEdicao`
devolve um objeto; não garante que ele devolve **vazio** quando nada mudou, que é a regra que
impede uma correção de placa de reescrever o cadastro inteiro.

O `test:dashboard` cobre o que aqueles não alcançam — **o que o operador lê**. As funções puras
podiam estar todas certas e a tela ainda mentir: bastava o card ignorar `fonte` e chamar de
"energia prevista" um número que é média móvel. São 124 testes em `apps/dashboard/tests`, com
vitest e jsdom.

O `test:mobile` fecha o que era o último buraco: renderização no app. Ele roda **jest-expo mais
RNTL** sobre as telas de verdade, e a combinação React 19 + RN 0.86 + Expo 57 funciona — com uma
diferença que custa tempo de quem não souber: na **RNTL 14 o `render` e o `fireEvent` devolvem
Promise**. Sem `await`, a asserção roda antes do re-render e o teste falha dizendo que o botão
continua apagado, o que é verdade naquele instante. `tests/util.tsx` registra isso e monta o
`SafeAreaProvider` que o app tem na raiz.

A divisão não é arbitrária: lógica pura no `verify`, decisão de apresentação no `test`. Só o
segundo precisa de DOM, e é por isso que ele veio depois.

Desde `ci.yml`, tudo isto roda em **PR e push para `staging` e `main`** — em dois
jobs, API (com Postgres 18 de serviço) e web. Antes dele o repositório tinha só
workflows de migration: as verificações existiam e nada as cobrava, num fluxo em
que o merge em `staging` aplica migration em banco real.

**Teste de mutação é o padrão de aceite**: reverter a guarda e confirmar que o teste quebra.
Não é cerimônia — ele já encontrou quatro guardas decorativas neste projeto, incluindo um
`max(0, ...)` que era código morto e uma checagem de escopo duplicada que o SQL já fazia.

## Estrutura

```text
apps/
  api/                    API FastAPI, migrations, testes e Dockerfile
  dashboard/              dashboard comercial React + Vite
  forecast/               job de previsão de demanda (LightGBM), fora da API
  mobile/                 app do motorista React Native + Expo
packages/
  sdk/                    cliente TypeScript compartilhado pelos dois apps
config/
  domains.json            enderecos publicos compartilhados
docs/
  challenge/              escopo e materiais da mentoria
  references/goodwe/      datasheet, manual e mapa MODBUS do HCA G2
.github/                  modelo de pull request
compose.yaml              ambiente local PostgreSQL + API
```

A landing page, quando iniciada, fica em `apps/landing`. As convencoes estao em
[docs/repository-structure.md](docs/repository-structure.md).

## Paleta

Extraída por inspeção do CSS do SEMS+ original: fundo `#1F2123`, fundo profundo `#0D0D0F`,
acento `#FF323A`, cabeçalho de tabela `#3A3A3C`, texto `#F5F6F8`, fonte Poppins.
