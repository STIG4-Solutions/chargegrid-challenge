# Deploy da API: GHCR, Azure Container Apps e Neon

Este roteiro configura primeiro o staging do protótipo. A imagem fica no GHCR,
a API executa na Azure e o PostgreSQL 18 fica no Neon. O domínio é gerenciado
pela Cloudflare. A publicação da imagem já é automática; o deploy na Azure é manual.
O projeto é privado: mantenha o repositório e o pacote GHCR privados. A Azure
autentica no GHCR com uma credencial de leitura armazenada como secret do registry.

## O que já foi verificado

Em 05/09/2026, o workflow `API container image` terminou com sucesso no
[run 33988629062](https://github.com/STIG4-Solutions/chargegrid-challenge/actions/runs/33988629062).

Imagem publicada e confirmada pelo log:

```text
ghcr.io/stig4-solutions/chargegrid-api:sha-91a85eafa38f2e7197e45775962d29a43c2313d6
```

Digest registrado pelo build:

```text
sha256:5aae684b1123349e50fea7c22639e1f326c89d0302eb7304858843e0c5823ec2
```

O repositório foi confirmado como `PRIVATE`. O teste de acesso anônimo ao GHCR
retornou `UNAUTHORIZED`, comportamento esperado para uma imagem privada. A
credencial de inspeção não tem `read:packages`, portanto não confirmou o campo
de visibilidade do pacote pela API. Confira `Private` em Package settings.
O build confirma o empacotamento e a publicação; não executa
a suíte de testes, migrations ou conexão com o Neon. Esses últimos ainda precisam
ser validados em staging. Nenhum recurso Azure foi criado por este roteiro.

O workflow está em `main`. A referência remota de `staging` consultada ainda não
contém o arquivo. Isso não impede testar a imagem de `main` em staging: o ambiente
é determinado pela configuração do Container App. Para futuros builds por push em
`staging`, integre também o workflow nessa branch pelo fluxo de PR da equipe.

## 1. Configurar acesso ao GHCR privado

1. Abra a organização `STIG4-Solutions` no GitHub e entre em **Packages**.
2. Abra `chargegrid-api` e **Package settings**.
3. Confira que a visibilidade é **Private**. A visibilidade do pacote é independente
   da visibilidade do repositório. Não torne o pacote público.
4. Confira que o usuário que fornecerá a credencial à Azure tem leitura do pacote,
   por acesso herdado do repositório ou por permissão explícita.

No GitHub, abra **Settings > Developer settings > Personal access tokens >
Tokens (classic) > Generate new token (classic)**. Use o nome
`azure-chargegrid-ghcr-pull`, uma expiração definida (por exemplo, 90 dias) e
somente o escopo `read:packages`. O GHCR usa PAT classic para esse acesso externo.
Autorize SSO se a organização exigir. A conta proprietária do token precisa ter
acesso de leitura ao pacote; o token não concede acesso adicional à conta.

Cadastre na Azure o usuário GitHub proprietário do PAT e o PAT como senha do
registry. O token fica como secret do registry, não como variável de ambiente do
FastAPI. Não o coloque no repositório, em mensagens ou em comandos versionados.
Renove a credencial antes de expirar: reinícios e novas réplicas podem precisar
baixar a imagem novamente. Para separar revogação e rotação, podem ser usados
PATs diferentes para staging e produção.

O workflow continua publicando com o `GITHUB_TOKEN` temporário automático. O PAT
da Azure serve somente para download; não precisa de `write:packages`,
`delete:packages` ou `repo`. O `.dockerignore` da API exclui `.env` e `.env.*`,
exceto o exemplo sem credenciais.

## 2. Preparar o Neon e os segredos

Abra **Connect** no projeto `chargegrid-staging`, escolha seu banco e desligue
**Connection pooling**. Use a branch do banco existente, mesmo que ela se chame
`production`: uma branch do Neon não é uma branch Git nem define o ambiente Azure.

Para o SQLAlchemy com asyncpg desta API, use este formato:

```text
postgresql+asyncpg://USUARIO:SENHA@HOST/BANCO?ssl=verify-full
```

Copie o usuário, senha, host e banco reais do Neon. Troque o protocolo para
`postgresql+asyncpg` e substitua os parâmetros `sslmode=require&channel_binding=require`
por `ssl=verify-full`. O SQLAlchemy passa os parâmetros da URL como argumentos ao
asyncpg: `sslmode` e `channel_binding` não são argumentos aceitos nesse caminho.
`verify-full` exige TLS com validação do certificado e do hostname. Na Azure,
configure também `PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt` para usar os
certificados de confiança da imagem Linux. Sem isso, asyncpg procura um arquivo
`~/.postgresql/root.crt` que não existe nessa imagem.

Preserve a codificação da senha na URL. Não use o nome sugerido do banco se o banco
que você criou tiver outro nome. Não acrescente aspas ao colar valores no portal.

Gere cada segredo novo no seu computador com:

```bash
node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"
```

Execute separadamente para a chave JWT, segredo de webhook e senhas das contas de
demonstração. Guarde os valores em um gerenciador de senhas.

## 3. Criar o Container App de staging

No Azure Portal, procure **Container Apps** e clique em **Create**.

| Campo | Valor inicial |
| --- | --- |
| Subscription | Assinatura estudantil com créditos |
| Resource group | `rg-chargegrid-staging` |
| Container app name | `chargegrid-api-staging` |
| Deployment source | Container image |
| Region | Brazil South, se disponível para sua assinatura |
| Container Apps environment | Criar `cae-chargegrid-staging` |
| Workload profile | Consumption |
| Image source | Docker Hub or other registries |
| Image type | Private |
| Registry server | `ghcr.io` |
| Registry username | Usuário GitHub proprietário do PAT, por exemplo `Merlottera` |
| Registry password | PAT classic com `read:packages`, armazenado como secret do registry |
| Image | `stig4-solutions/chargegrid-api` |
| Image tag | `sha-91a85eafa38f2e7197e45775962d29a43c2313d6` |
| CPU / Memory | 0.5 vCPU / 1 GiB |
| Command / Arguments | Deixar vazios; usar o comando do Dockerfile |
| Ingress | Enabled, HTTP, external / accepting traffic from anywhere |
| Target port | `8000` |
| Transport | Auto |
| Allow insecure connections | Desligado |
| Minimum / Maximum replicas | `1` / `1` durante a configuração |
| Revision mode | Single |

Se a tela pedir uma referência única de imagem, cole o endereço completo da seção
"O que já foi verificado". Para um Container App existente, configure as credenciais
do registry antes de criar a revisão com essa imagem privada.
A Azure termina o HTTPS na porta pública 443 e encaminha para o Uvicorn na porta
interna 8000. Não é preciso expor PostgreSQL, configurar VM ou instalar Docker na Azure.

## 4. Variáveis e secrets

Configure os valores abaixo no contêiner. Se a criação não disponibilizar todos os
campos, adicione os secrets em **Security > Secrets** e use **Create new revision**
para configurar as variáveis. Uma revisão criada sem os campos obrigatórios falhará
na inicialização até receber essa configuração.

| Variável | Valor de staging | Origem |
| --- | --- | --- |
| `ENV` | `staging` | Valor literal |
| `DEBUG` | `false` | Valor literal |
| `CORS_ORIGINS` | `["https://dashboard.staging.stig4-solutions.com"]` | Valor literal |
| `DATABASE_URL_OVERRIDE` | URL adaptada do Neon de staging | Secret `database-url` |
| `PGSSLROOTCERT` | `/etc/ssl/certs/ca-certificates.crt` | Valor literal |
| `POSTGRES_PASSWORD` | Senha real do Neon, sem codificação de URL | Secret `postgres-password` |
| `SECRET_KEY` | Segredo aleatório para assinar JWT | Secret `jwt-secret` |
| `PAYMENT_WEBHOOK_SECRET` | Outro segredo aleatório para o mock | Secret `payment-webhook-secret` |
| `CHARGER_DRIVER` | `simulator` | Valor literal |
| `METER_SOURCE` | `virtual` | Valor literal |
| `ENABLE_WORKERS` | `false` inicialmente | Valor literal |
| `PAYMENT_PROVIDER` | `mock` | Valor literal |
| `PUSH_PROVIDER` | `log` sem FCM; `expo` para entregar de verdade | Valor literal |
| `SEED_ADMIN_PASSWORD` | Senha escolhida para a conta de demonstração | Secret `seed-admin-password` |
| `SEED_OPERATOR_PASSWORD` | Outra senha | Secret `seed-operator-password` |
| `SEED_DRIVER_PASSWORD` | Outra senha | Secret `seed-driver-password` |

Crie os secrets com os nomes da terceira coluna e selecione **Secret reference**
como origem das variáveis correspondentes. `POSTGRES_PASSWORD` continua obrigatório
no modelo de configuração mesmo usando `DATABASE_URL_OVERRIDE`.

O dashboard não precisa existir ainda para configurar CORS. Swagger no mesmo domínio
da API funciona. Não use `localhost` nessa lista: a guarda de staging rejeita isso.
O modo `mock` simula pagamentos; não processa cobranças reais.

## 5. Criar as tabelas e os dados de staging

Mantenha `ENABLE_WORKERS=false` e uma réplica ligada enquanto prepara o banco.
O Dockerfile inicia somente a API. O Compose local aplica migrations e seed, mas
esse comando do Compose não é executado pela Azure.

Abra **Monitoring > Console** no Container App, selecione a revisão/réplica atual
e o shell `sh`. Execute um comando por vez e só avance se o anterior terminar bem:

```sh
cd /app
alembic upgrade head
alembic current
```

Confirme que `alembic current` exibe a revisão atual com `(head)`.
Para o cenário de demonstração de staging:

```sh
python -m app.seed
```

As senhas vêm dos três secrets configurados. Sem eles, o seed sorteia e imprime
senhas no console. Não execute a suíte pytest contra o banco de staging/produção.

Em **Revisions and replicas**, crie uma revisão alterando `ENABLE_WORKERS` para
`true`. Mantenha uma réplica para validar a simulação. Pode retirar as variáveis
`SEED_*` dessa revisão após popular o banco: isso não apaga as contas.

## 6. Validar antes de adicionar o domínio

Copie **Application URL** da visão geral do Container App e abra:

```text
https://DOMINIO-GERADO.azurecontainerapps.io/health
https://DOMINIO-GERADO.azurecontainerapps.io/docs
```

O health esperado inclui `status: ok`, `database: up`, `env: staging` e `workers: true`.
O endpoint atual retorna HTTP 200 mesmo se o banco estiver degradado: confira o JSON.
Ele testa conexão, mas não prova que as migrations foram aplicadas.

No Swagger, execute `POST /api/v1/auth/login` com `operador@chargegrid.com.br` e a
senha escolhida no seed. Use o token para uma leitura do dashboard e confira os
logs do contêiner. As migrations, login e uma leitura autenticada validam pontos
que o build da imagem e o `/health` isoladamente não cobrem.

## 7. Domínio na Cloudflare

Na Azure, abra **Networking > Custom domains > Add custom domain**, escolha
**Managed certificate** e informe `api.staging.stig4-solutions.com`.

Crie na zona `stig4-solutions.com` da Cloudflare os registros exibidos pela Azure:

| Tipo | Nome | Conteúdo |
| --- | --- | --- |
| CNAME | `api.staging` | Domínio gerado do Container App, sem `https://` |
| TXT | `asuid.api.staging` | Código de validação mostrado pela Azure |

Mantenha esse CNAME em **DNS only** para a emissão e renovação do certificado
gerenciado. Se houver registros CAA restritivos, autorize também `digicert.com`.
Volte à Azure, valide e aguarde o domínio ficar **Secured**.

Teste `/health` e `/docs` novamente no domínio próprio. O dashboard usará
`VITE_API_URL=https://api.staging.stig4-solutions.com`, sem `/api/v1` no final.

## 8. Produção e próximos deploys

Depois de validar staging, repita com:

| Item | Produção |
| --- | --- |
| Resource group | `rg-chargegrid-prod` |
| Environment | `cae-chargegrid-prod` |
| Container App | `chargegrid-api-prod` |
| Neon | Projeto `chargegrid` e seu banco real |
| `ENV` | `prod` |
| `CORS_ORIGINS` | `["https://dashboard.stig4-solutions.com"]` |
| Domínio | `api.stig4-solutions.com` |
| DNS | CNAME `api` e TXT `asuid.api` |
| Réplicas | Mínimo 1, máximo 1 |

Use outros segredos e dados. Promova a mesma imagem testada em staging, idealmente
pelo digest do build. Não use `latest` para identificar uma versão estável nem
reconstrua o mesmo commit esperando bytes idênticos: as dependências ainda não estão
fixadas em um lockfile Python.

Para uma demonstração do challenge, o seed pode popular também o ambiente de
apresentação com senhas próprias. Para atender clientes reais, prepare cadastro
inicial e integrações reais: o seed é um cenário fictício, não um cadastro comercial.

Publicar nova imagem no GHCR não atualiza automaticamente o Container App. Após
um build, selecione explicitamente a nova imagem em uma revisão na Azure.
Planeje uma pequena janela de manutenção nesta fase: pare/desative a revisão antiga
com workers antes de ativar a nova. `Single` e `max replicas=1` não impedem sobreposição
temporária entre revisões durante um rollout. Execute migrations uma vez por ambiente
e valide antes de reabrir o tráfego. Voltar à imagem antiga não reverte migrations;
alterações no banco precisam manter compatibilidade ou ter um plano de restauração.

Depois, evolua para um Container Apps Job manual de migrations e autenticação OIDC
do GitHub para automatizar o deploy. Isso não é necessário para este primeiro acesso.

Staging pode usar mínimo 0 depois da validação, aceitando cold start e interrupção
dos workers enquanto dorme. Com mínimo 1 e workers contínuos, Azure e Neon permanecem
ativos: acompanhe os créditos e a franquia do banco; scale-to-zero do Neon pode não
ocorrer enquanto os workers consultam o banco periodicamente.

## Problemas comuns

| Sintoma | Verificação |
| --- | --- |
| Imagem não inicia / unauthorized | Registry `ghcr.io`, tag completa, usuário proprietário do PAT, `read:packages`, acesso ao pacote, validade e SSO |
| `unexpected keyword argument 'sslmode'` ou `channel_binding` | Usar a URL com `?ssl=verify-full` |
| `root certificate file ... does not exist` | Configurar `PGSSLROOTCERT` com o caminho dos certificados Linux acima |
| Configuração insegura / campo obrigatório ausente | Secrets, `POSTGRES_PASSWORD`, `DEBUG=false` e CORS sem localhost |
| Health `database: down` | URL, nome real do banco, credenciais, TLS e logs |
| `relation does not exist` | Aplicar `alembic upgrade head` no banco correto |
| Login falha num banco novo | Seed de staging executado e senha do `SEED_OPERATOR_PASSWORD` |
| Dashboard falha, Swagger funciona | CORS deve conter exatamente a origem do dashboard |
| Dados não atualizam | `ENABLE_WORKERS=true`, réplica ativa e logs dos workers |

## Referências oficiais

- [Visibilidade de pacotes GitHub](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)
- [Criar Container App com imagem existente](https://learn.microsoft.com/en-us/azure/container-apps/get-started-existing-container-image-portal)
- [Secrets](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)
- [Console do contêiner](https://learn.microsoft.com/en-us/azure/container-apps/container-console)
- [Domínios e certificados gerenciados](https://learn.microsoft.com/en-us/azure/container-apps/custom-domains-managed-certificates)
- [SQLAlchemy asyncpg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)
