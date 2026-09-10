# Desenvolvimento local

Execute os comandos desta pagina a partir da raiz do repositorio, exceto quando houver um `cd` explicito. A API fica em `apps/api`, o dashboard em `apps/dashboard` e o app do motorista em `apps/mobile`.

## Requisitos

- Node.js compativel com a versao do Expo usada pelo mobile e npm com suporte a workspaces. Node.js 24 e a referencia para este ambiente.
- Docker com Compose v2 para PostgreSQL e API em containers.
- Python 3.11 ou superior para executar a API e seus testes fora do Docker; a imagem da API usa Python 3.12.
- Expo Go, um aparelho ou um emulador para usar o mobile. Os builds nativos seguem as instrucoes do [app](../apps/mobile/README.md).
- O job de previsao (`apps/forecast`) roda em container proprio; nao e' necessario para desenvolver a API nem os clientes.

## Preparar o clone

```bash
npm ci
cp apps/api/.env.example apps/api/.env
cp apps/dashboard/.env.example apps/dashboard/.env
cp apps/mobile/.env.example apps/mobile/.env
```

No PowerShell, `Copy-Item` pode substituir `cp`. Copie os exemplos apenas quando os arquivos locais ainda nao existirem. Preencha `POSTGRES_PASSWORD`, `SECRET_KEY` e `PAYMENT_WEBHOOK_SECRET` em `apps/api/.env` antes de iniciar a API.

Para gerar uma chave local de assinatura, por exemplo:

```bash
node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"
```

O dashboard aponta sozinho para a API local: o `vite.config.js` le o bloco `desenvolvimento` de `config/domains.json` quando o comando e' `serve`, e o de producao quando e' `build`. `VITE_API_URL` em `apps/dashboard/.env` continua tendo precedencia, e so' e' preciso para apontar para outro lugar. O mobile aceita `EXPO_PUBLIC_API_URL` em `apps/mobile/.env`; em um aparelho fisico, use um endereco da API acessivel pela rede do aparelho. As variaveis publicas dos frontends sao incorporadas ao aplicativo e nao devem receber segredos.

## Iniciar as aplicacoes

```bash
npm run infra:config
npm run infra:up
npm run dev:dashboard
```

Em outro terminal:

```bash
npm run dev:mobile
```

O ambiente expoe a API em `http://localhost:8000`, sua documentacao em `http://localhost:8000/docs` e o dashboard em `http://localhost:5173`. O Compose inicia PostgreSQL, aplica migrations, popula o cenario local e inicia a API com o driver configurado em seu ambiente.

`infra:up` executa `docker compose --env-file apps/api/.env up --build -d`. Para ver os logs:

```bash
docker compose --env-file apps/api/.env logs -f api
```

Para parar sem remover os dados:

```bash
npm run infra:down
```

O Compose le `apps/api/.env` tanto para a interpolacao das variaveis quanto para o ambiente do container. `config/domains.json` fornece os enderecos padrao no checkout; a imagem da API recebe sua configuracao por variaveis de ambiente.

## Verificar uma mudanca

```bash
npm run verify:api
npm run verify:dashboard
npm run typecheck
npm run build:dashboard
npm run bundle -w @chargegrid/mobile
```

Depois de atualizar o OpenAPI da API:

```bash
npm run gen:types
npm run typecheck
```

Para preparar o Python e executar a suite da API, siga o [README da API](../apps/api/README.md). Com as dependencias instaladas e o PostgreSQL acessivel, execute em `apps/api`:

```bash
python -m ruff check .
python -m pytest -q
```

A suite cria e usa um banco separado com sufixo `_test`. Para os cenarios de fumaca, a API tambem precisa estar no ar:

```bash
python -m scripts.smoke_test
```

Ao adicionar uma guarda, verifique que ela nao e' decorativa: reverta a condicao e confirme que
algum teste quebra. E' o padrao de aceite do projeto, e ja encontrou guardas que nao protegiam
nada — incluindo um piso `max(0, ...)` inalcancavel e uma checagem de escopo que o SQL ja fazia.

## Previsao de demanda

O job vive em `apps/forecast` e nao sobe com o Compose: roda sob demanda, doze vezes por ano.

```bash
docker build -t chargegrid-forecast apps/forecast

# treinar com os dados do banco (ao mudar a rede, ou por trimestre)
docker run --rm --network backend_default   -e POSTGRES_HOST=db -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=...   -v "$PWD/apps/forecast/modelos:/forecast/modelos"   chargegrid-forecast python treinar.py

# gerar a previsao do mes e gravar em site_forecasts
docker run --rm --network backend_default   -e POSTGRES_HOST=db -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=...   -v "$PWD/apps/forecast/modelos:/forecast/modelos"   chargegrid-forecast python exportar.py
```

Sem linha na tabela, o painel mostra "nenhuma previsao calculada" — que e' melhor que um numero
inventado. O artefato `.joblib` nao e' versionado: o seed e' deterministico, entao `treinar.py`
o reproduz em qualquer maquina.

## Atalhos

| Comando | Acao |
| --- | --- |
| `npm run dev:dashboard` | Iniciar o dashboard |
| `npm run build:dashboard` | Gerar o build do dashboard |
| `npm run preview:dashboard` | Servir localmente o build do dashboard |
| `npm run dev:mobile` | Iniciar o Expo |
| `npm run mobile:android` | Executar o build Android local |
| `npm run mobile:ios` | Executar o build iOS local com as ferramentas necessarias |
| `npm run infra:up` | Iniciar PostgreSQL e API |
| `npm run infra:down` | Parar o ambiente preservando o volume |
| `npm run infra:config` | Validar a configuracao do Compose |

Para recriar o banco do zero — o unico jeito de o seed rodar de novo, ja que ele pula quando ha
dados — remova o volume. **Isso apaga o banco local:**

```bash
npm run infra:down -- -v && npm run infra:up
```

Os comandos anteriores `dev`, `build`, `preview` e `mobile` continuam disponiveis como aliases. Para atualizar um clone anterior a esta organizacao, consulte a [orientacao de migracao](repository-structure.md#atualizacao-de-clones-anteriores).
