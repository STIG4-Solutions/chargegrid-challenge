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

## O que cada lado faz

A seção **Recarga EV** tem nove abas. As três primeiras operam o presente; as demais decidem o
futuro — é onde o painel deixa de relatar e passa a recomendar.

| Aba | Pergunta que responde |
|---|---|
| Gerenciamento de Potência | quanto cada ponto pode puxar agora, sem estourar o padrão |
| Ciclo da Sessão | o que está acontecendo em cada recarga, com timeline auditável |
| Tarifação & Pagamento | quanto custa, por janela horária, e como se cobra |
| Demanda Contratada | qual demanda contratar — e quanto o rateio já poupou de multa |
| Ocupação & Retorno | qual ponto se paga, e qual está ocupado sem faturar |
| Regras de Prioridade | quem carrega quando falta potência, e por quê |
| Visão de Rede | qual praça segura a operação (aparece com mais de um site) |
| Campanhas | quanto custa comprar comportamento do motorista, e se comprou |
| Plano & Contrato | o que a praça paga à GoodWe, e quanto custa sair antes do prazo |

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

**O modelo ganha no diário e perde no mensal**, que é a granularidade que a tela mostra:

| granularidade | modelo | régua (média móvel de 28 dias) |
|---|---|---|
| diário | **29,4%** | 34,3% |
| mensal | 12,0% | **9,6%** |

Medido sobre 36 estação-meses fora da amostra. Ele aprende o dia a dia — no ponto corporativo,
onde o fim de semana é 4× mais fraco, erra 33,6% contra 52,8% da régua. Mas somando 30 dias
esse padrão quase se cancela, e sobra a variância que o modelo adiciona.

Combinar os dois foi testado e não resolve: a correlação entre os erros mensais é **0,944** —
eles erram junto, porque no agregado ambos são essencialmente "nível × dias".

Então o job grava **o preditor que mede melhor**, e a coluna `fonte` diz qual foi. Não é
desistir do modelo: quando ele passar a ganhar — com operação real, com mais estações —, o
próprio backtest inverte a escolha sem ninguém mexer em código.
`apps/forecast/README.md` detalha.

## Rodar

**Backend** (sobe Postgres, migra, popula e serve):

O seed gera **dois anos de histórico**: 4 sites, ~17.800 sessões faturadas, campanha com
missões já em progresso, planos de assinatura e um contrato de plataforma. Não é enfeite —
o modelo de previsão descarta local com menos de 150 dias de energia, os relatórios de ocupação
medem janelas de 30 dias, e uma missão de "recarregue 5 vezes este mês" é indemonstrável com
uma semana de dados. Com poucos dias no banco, as três entregam tela vazia e parecem quebradas.

É determinístico por semente fixa: duas máquinas produzem o mesmo banco, e um artefato de
previsão treinado numa continua valendo na outra.


```bash
cp apps/api/.env.example apps/api/.env
# Preencha os valores de apps/api/.env antes de continuar.
npm run infra:up          # API em http://localhost:8000
```

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

## Verificação

```bash
npm run verify:api                         # 17 cenários do SDK com fetch simulado
npm run verify:dashboard                   # 62 cenários da lógica do painel, sem navegador
npm run test:dashboard                     # 21 testes de renderização (vitest + jsdom)
npm run typecheck                          # tipos do SDK e do app contra o contrato
npm run build                              # dashboard
cd apps/api && python -m pytest -q          # 538 testes (precisa do Postgres)
cd apps/api && python -m ruff check .
cd apps/api && python -m scripts.smoke_test # 116 cenários ponta a ponta (API no ar)
cd apps/mobile && npx expo export --platform android --output-dir .expo-bundle
```

O `verify:api` roda contra um armazenamento **assíncrono de propósito** — o do React Native.
Se passa nele, passa no `localStorage` síncrono da web.

O `verify:dashboard` é Node puro mais esbuild, sem runner, e cobre a lógica que decide **o
que vai para o servidor**: o diff do editor de orçamento, a validação do formulário de
campanha, a calibração da faixa de previsão e o cálculo da multa de rescisão.

O `test:dashboard` cobre o que aquele não alcança — **o que o operador lê**. As funções puras
podiam estar todas certas e a tela ainda mentir: bastava o card ignorar `fonte` e chamar de
"energia prevista" um número que é média móvel. São 21 testes em `apps/dashboard/tests`, com
vitest e jsdom.

A divisão não é arbitrária: lógica pura no `verify`, decisão de apresentação no `test`. Só o
segundo precisa de DOM, e é por isso que ele veio depois.

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
