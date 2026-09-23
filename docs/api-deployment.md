# Deploy: onde cada parte roda

Este documento trazia um roteiro de **Azure Container Apps + GHCR**, em 298 linhas de passo a
passo. Ele não descreve o que existe, e o próprio texto já dizia por quê: *"Nenhum recurso Azure
foi criado por este roteiro."* O workflow que ele citava (`API container image`) também não está
mais no repositório.

Documentação de infraestrutura que descreve um caminho não tomado é pior que a ausência dela:
quem precisa publicar segue o roteiro, gasta horas e descobre no fim que o ambiente é outro. O
conteúdo antigo continua no histórico do Git, que é onde ele deve estar.

## O que roda hoje

| Parte | Onde | Como se confere |
|---|---|---|
| API | **Render** | `curl -I https://api.staging.stig4.com/health` devolve `rndr-id` e `x-render-origin-server: uvicorn` |
| Banco | **Neon** (PostgreSQL 18) | a string de conexão vive no secret `STAGING_DATABASE_URL` |
| DNS e borda | **Cloudflare** | `Server: cloudflare` e `CF-RAY` em todas as respostas |
| Site institucional | **Cloudflare Pages** | `apps/site/README.md` traz o comando de build e os domínios |
| Dashboard | Cloudflare na borda | **origem não confirmada** — a resposta passa pela Cloudflare, o que não diz onde o arquivo é servido |

Os endereços vivem em `config/domains.json`, que é a fonte única. **O endereço da API vai assado
no pacote do dashboard**: o Vite o lê em tempo de build, então trocar o domínio depois de
publicado não adianta — é preciso reconstruir.

## O que é automático

Quatro workflows, e nenhum deles publica a aplicação:

| Workflow | Quando | O que faz |
|---|---|---|
| `ci` | todo push e PR | ruff, pytest, typecheck, os três `verify`, as suítes de renderização, build e bundle |
| `migrate-staging` | push em `staging` que toque `apps/api/**` | `alembic upgrade head` contra o Neon do staging |
| `migrate-production` | manual | o mesmo, contra produção |
| `forecast-staging` | dia 1 de cada mês, ou manual | treina o modelo e grava a previsão do mês |

**O deploy da API é do Render**, pelo gancho dele com o repositório — não há workflow aqui que o
dispare. Consequência que vale saber: a ordem entre a migração e o deploy não é garantida por
este repositório. Para migração aditiva isso é indiferente; uma migração destrutiva precisaria de
cuidado manual. Está anotado como limite conhecido, não como esquecimento.

## Dado de referência chega por migração, não por comando

O catálogo de planos da plataforma é publicado por `0027_catalogo_de_planos`. O motivo está
escrito na própria migração: ele nascia dentro do `seed()`, que desiste inteiro quando o banco já
tem dados — e o staging ficou sem plano nenhum, com a tela dizendo "escolha um plano abaixo" e
nada abaixo.

A consequência para quem publica: **não há passo manual de seed em staging**. Se um plano novo
entrar no catálogo, ele vem numa migração nova, e um teste compara os dois conjuntos para que
esquecer disso quebre o CI em vez de produzir outra tela vazia.

## O que ainda não está resolvido

- **`ENABLE_WORKERS=true` no Render.** Os workers de rebalanceamento e de medição não sobem: a
  instância gratuita hiberna, e com ela os workers param. Exige plano pago, e foi adiado por
  decisão.
- **Onde o dashboard é servido**, exatamente. A borda é Cloudflare; a origem não foi confirmada.
- **A ordem entre migração e deploy**, como acima.
