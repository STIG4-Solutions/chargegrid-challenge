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

## O que o painel faz

A seção **Recarga EV** tem sete abas. As três primeiras operam o presente; as quatro últimas
decidem o futuro — é onde o painel deixa de relatar e passa a recomendar.

| Aba | Pergunta que responde |
|---|---|
| Gerenciamento de Potência | quanto cada ponto pode puxar agora, sem estourar o padrão |
| Ciclo da Sessão | o que está acontecendo em cada recarga, com timeline auditável |
| Tarifação & Pagamento | quanto custa, por janela horária, e como se cobra |
| Demanda Contratada | qual demanda contratar — e quanto o rateio já poupou de multa |
| Ocupação & Retorno | qual ponto se paga, e qual está ocupado sem faturar |
| Regras de Prioridade | quem carrega quando falta potência, e por quê |
| Visão de Rede | qual praça segura a operação (aparece com mais de um site) |

O app do motorista cobre o outro lado: encontrar estação, ler o QR do carregador, iniciar e
acompanhar a recarga, agendar vaga, ver faturas e gerenciar veículos e carteira.

## Rodar

**Backend** (sobe Postgres, migra, popula e serve):

```bash
cp apps/api/.env.example apps/api/.env
# Preencha os valores de apps/api/.env antes de continuar.
npm run infra:up          # API em http://localhost:8000
```

**Dashboard:**

```bash
npm install
cp apps/dashboard/.env.example apps/dashboard/.env  # VITE_API_URL=http://localhost:8000
npm run dev                        # http://localhost:5173
```

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
  "api": "api.stig4-solutions.com",
  "dashboard": "dashboard.stig4-solutions.com",
  "site": "stig4-solutions.com"
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
npm run typecheck                          # tipos do SDK e do app contra o contrato
npm run build                              # dashboard
cd apps/api && python -m pytest -q          # 394 testes (precisa do Postgres)
cd apps/api && python -m ruff check .
cd apps/api && python -m scripts.smoke_test # 57 cenários ponta a ponta (API no ar)
cd apps/mobile && npx expo export --platform android --output-dir .expo-bundle
```

O `verify:api` roda contra um armazenamento **assíncrono de propósito** — o do React Native.
Se passa nele, passa no `localStorage` síncrono da web.

## Estrutura

```text
apps/
  api/                    API FastAPI, migrations, testes e Dockerfile
  dashboard/              dashboard comercial React + Vite
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
