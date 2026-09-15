# Estrutura do repositorio

O ChargeGrid usa um monorepo com aplicacoes independentes e um SDK compartilhado. O npm gerencia os workspaces JavaScript; a API possui seu proprio projeto Python. A publicacao de uma aplicacao nao exige publicar todas as outras.

## Responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| `apps/api` | API FastAPI, migrations, testes, scripts Python e Dockerfile |
| `apps/dashboard` | Dashboard comercial e operacional React + Vite; `scripts/` traz a verificacao da logica pura e `tests/` a de renderizacao (vitest). `README.md` descreve as abas, os perfis de acesso e a troca de praca |
| `apps/forecast` | Job offline de previsao de demanda; `pipeline/` e' o modelo vendorizado |
| `apps/mobile` | Aplicativo do motorista React Native + Expo |
| `packages/sdk` | Cliente da API, autenticacao e utilitarios compartilhados pelos clientes |
| `config/domains.json` | Enderecos publicos usados como padrao pelas aplicacoes |
| `docs/challenge` | Escopo e materiais da mentoria FIAP |
| `docs/references/goodwe` | Datasheet, manual e mapa MODBUS do hardware |
| `.github` | Modelo de PR e futuras automacoes do GitHub |
| `compose.yaml` | Coordenacao do ambiente local PostgreSQL + API |

Os diretorios internos de cada aplicacao seguem sua organizacao atual. O SDK e importado por `@chargegrid/sdk`; aplicacoes nao importam arquivos internos umas das outras.

`apps/forecast` fica FORA dos workspaces npm: e' Python, tem `requirements.txt` proprio e roda
em container separado. A separacao e' deliberada e nao apenas de linguagem — o processo da API
tambem roda os workers de potencia, e um `import lightgbm` quebrado nao pode derrubar o
rebalanceamento junto. O diretorio `pipeline/` e' copia do projeto de modelagem, mantida sem
alteracao para poder ser reatualizada sem conflito; `banco.py`, `treinar.py` e `exportar.py`
sao deste projeto.

## Nomes

- Diretorios e arquivos gerais: ingles, minusculas e `kebab-case`, sem espacos ou acentos.
- Nomes convencionais de ferramentas: preservar `README.md`, `CONTRIBUTING.md`, `Dockerfile`, `package.json` e outros nomes reconhecidos.
- Pacotes JavaScript: `@chargegrid/dashboard`, `@chargegrid/mobile` e `@chargegrid/sdk`.
- Projeto Python: `chargegrid-api`.
- Repositorio: `chargegrid-challenge`; produto: ChargeGrid Intelligence.

`config/domains.json` separa os enderecos publicos da API, do dashboard comercial e do site. Identificadores de distribuicao mobile e o projeto EAS permanecem os mesmos.

## Configuracoes e ambiente

Cada aplicacao tem seu proprio `.env.example` e carrega seu `.env` local. A raiz nao possui um arquivo de ambiente compartilhado pelos frontends. O Compose recebe explicitamente `apps/api/.env` por `--env-file`; o dashboard le `apps/dashboard/.env` e o Expo le `apps/mobile/.env`.

Mantenha Vite, Metro, Expo, TypeScript e Python junto dos respectivos projetos. Configuracoes de editor e finais de linha ficam na raiz em `.editorconfig` e `.gitattributes`. O arquivo de dominios contem configuracao publica, nunca segredos.

O Dockerfile da API usa contexto `apps/api`. O arquivo `.dockerignore` impede que arquivos de ambiente reais e caches entrem na imagem.

## Crescimento

A landing page sera criada em `apps/landing` e registrada nos workspaces quando sua implementacao comecar. `infra`, `tooling` e `scripts` na raiz serao adicionados quando existirem, respectivamente, definicoes de infraestrutura, configuracoes compartilhadas de ferramentas ou automacoes do repositorio. Bibliotecas novas entram em `packages` quando houver compartilhamento real.

## Atualizacao de clones anteriores

Arquivos locais ignorados pelo Git nao acompanham automaticamente as movimentacoes. Preserve seus valores e mova-os para os destinos correspondentes, sem sobrescrever configuracoes ja existentes:

| Local anterior | Local atual |
| --- | --- |
| `.env` na raiz | `apps/dashboard/.env` |
| `backend/.env` | `apps/api/.env` |
| `packages/mobile/.env` | `apps/mobile/.env` |

Depois, execute `npm ci` na raiz e recrie o ambiente virtual Python em `apps/api`, caso use um. Ajuste configuracoes locais da IDE e integracoes externas que apontem para os diretorios anteriores.

O Compose fixa `name: backend` para manter o nome de projeto usado anteriormente pelo diretorio do backend. A imagem do PostgreSQL 18 usa o novo volume `backend_chargegrid_pgdata_v18`, montado em `/var/lib/postgresql`. Um eventual volume antigo `backend_chargegrid_pgdata`, criado pelo PostgreSQL 16, permanece intacto para recuperacao ou migracao. Se voce utilizava `-p` ou `COMPOSE_PROJECT_NAME`, continue usando o mesmo valor.

Veja [desenvolvimento local](development.md) para os comandos atuais e [como contribuir](../CONTRIBUTING.md) para o fluxo de trabalho.
