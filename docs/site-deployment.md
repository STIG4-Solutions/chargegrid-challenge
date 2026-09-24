# Deploy do site e do APK Android

Este documento registra os pontos de configuração externos ao repositório. Os
endereços estáveis podem ser documentados; URLs de builds individuais, chaves e
credenciais não devem ser versionadas.

## Arquitetura

- `stig4.com`: site de produção, público.
- `staging.stig4.com`: site de homologação público.
- `/download`: página estática que explica o aplicativo e a instalação.
- `/download/android`: Pages Function que responde `302` para a variável `ANDROID_APK_URL` do ambiente.
- APK de produção: objeto no R2 acessível por um domínio personalizado público.
- APK de staging: objeto no R2 acessível por outro domínio personalizado, protegido pelo Cloudflare Access.

O arquivo `apps/site/public/_routes.json` limita a execução da Function a `/download/android`. As demais páginas continuam sendo entregues como arquivos estáticos.

## Projeto no Cloudflare Pages

Conecte o repositório do ChargeGrid e use:

| Campo | Valor |
|---|---|
| Framework preset | Nenhum |
| Diretório raiz | `apps/site` |
| Comando de build | `npm run build` |
| Diretório de saída | `dist` |
| Branch de produção | `main` |

Usar `apps/site` como raiz é necessário porque o diretório `functions` precisa estar na raiz do projeto Pages. Isso também impede que a Function de download seja anexada aos projetos Cloudflare do dashboard.

## Variável do APK

Em **Settings → Variables and Secrets**, crie `ANDROID_APK_URL` nos dois ambientes:

| Ambiente Pages | Valor |
|---|---|
| Production | `https://downloads.stig4.com/latest/chargegrid.apk` |
| Preview | `https://downloads.staging.stig4.com/latest/chargegrid.apk` |

Os valores precisam ser URLs HTTPS completas. A Function recusa valor ausente, inválido ou iniciado com `http:`.

Não reutilize o endereço de staging em Production. O caminho público `https://stig4.com/download/android` deve sempre terminar no APK de produção.

Esses dois valores são estáveis. Cada release substitui o objeto `latest/chargegrid.apk`
no bucket correto, portanto não é necessário alterar a variável nem executar um novo
deploy do Pages a cada APK.

## Domínios e branches

1. Adicione `stig4.com` como domínio personalizado do projeto Pages. Ele acompanha a branch `main`.
2. Faça ao menos um deploy bem-sucedido da branch `staging`.
3. Adicione `staging.stig4.com` como domínio personalizado.
4. No DNS do domínio, mantenha o registro com proxy ativado e altere o destino do CNAME para o alias da branch `staging` mostrado pelo Pages.

O projeto atual usa `chargegrid-site.pages.dev`. Configure um Bulk Redirect desse
hostname exato para `https://stig4.com`, preservando caminho e query string, mas sem
incluir subdomínios. Assim o alias `staging.chargegrid-site.pages.dev` continua disponível.

Para `www`, crie outro Bulk Redirect de `www.stig4.com` para `https://stig4.com`,
também preservando caminho e query. O hostname `www` precisa de um registro `A`
proxied para `192.0.2.1`, usado apenas para que a regra passe pela borda Cloudflare.

## R2 de produção

1. Conecte o domínio personalizado `downloads.stig4.com` ao bucket de produção.
2. Mantenha esse domínio público, sem Cloudflare Access.
3. Desative o endereço público `r2.dev` do bucket.
4. Configure `ANDROID_APK_URL` uma única vez com a URL `latest` da tabela anterior.

## R2 de staging

1. Use o domínio personalizado `downloads.staging.stig4.com`.
2. Antes de conectá-lo ao bucket, crie uma aplicação **Self-hosted** no Cloudflare Zero Trust para esse hostname.
3. Adicione uma política Allow limitada aos e-mails ou ao provedor de identidade da equipe.
4. Conecte o domínio protegido ao bucket.
5. Desative o endereço público `r2.dev` do bucket.
6. Configure `ANDROID_APK_URL` uma única vez com a URL `latest` da tabela anterior.

Proteger o site não protegeria o objeto após o redirecionamento. A fronteira de acesso
fica no domínio R2: as páginas de staging são públicas, enquanto o APK exige login.

## Publicar uma nova versão do APK

1. Altere `expo.version` em `apps/mobile/app.json` no PR do release.
2. No GitHub Actions, execute **Publish Android APK** para `staging`.
3. Instale e valide o APK protegido de staging.
4. Depois que o mesmo código estiver em `main`, execute o workflow para `production`.
5. Aprove o GitHub Environment `mobile-production`.

O workflow gera o APK no EAS, valida package e versão, calcula SHA-256 e publica:

```text
releases/<versão>/<commit>/chargegrid.apk
releases/<versão>/<commit>/chargegrid.apk.sha256
releases/<versão>/<commit>/release.json
latest/chargegrid.apk
latest/chargegrid.apk.sha256
latest/release.json
```

Produção recusa versão igual ou inferior à última publicada. Staging permite novos
builds da mesma versão, pois o commit também faz parte do caminho imutável.

### Configuração única do GitHub

Crie os Environments `mobile-staging` e `mobile-production`. Em produção, configure
um required reviewer. Em ambos, adicione:

| Tipo | Nome | Valor |
|---|---|---|
| Variable | `R2_ACCOUNT_ID` | ID da conta Cloudflare |
| Variable | `R2_BUCKET` | bucket do ambiente |
| Variable | `R2_BASE_URL` | domínio HTTPS do bucket, sem barra final |
| Secret | `R2_ACCESS_KEY_ID` | credencial S3 restrita ao bucket |
| Secret | `R2_SECRET_ACCESS_KEY` | segredo da mesma credencial |

Crie também o repository secret `EXPO_TOKEN`. As duas credenciais R2 devem ter
**Object Read & Write** e acesso somente ao bucket do próprio ambiente.

## Desenvolvimento local

A interface roda normalmente com:

```bash
npm run dev:site
```

O servidor Vite não executa Pages Functions. Para validar o redirecionamento localmente, gere o site e inicie o runtime do Pages a partir de `apps/site`:

```bash
npm run build
npx wrangler pages dev dist --binding ANDROID_APK_URL=<URL_HTTPS_DE_TESTE>
```

O valor local deve ser descartável e nunca deve ser salvo em um arquivo versionado.

## Checklist antes de produção

- `npm run test:site` passou.
- `npm run build:site` passou.
- `stig4.com/download` abre sem autenticação.
- `stig4.com/download/android` redireciona somente para o APK de produção.
- `staging.stig4.com/download` abre sem autenticação.
- O domínio R2 de staging exige Cloudflare Access mesmo quando acessado diretamente.
- `downloads.stig4.com/latest/chargegrid.apk` baixa sem autenticação.
- Os endereços `r2.dev` dos buckets estão desativados.
- Nenhuma URL de build individual ou credencial entrou no Git.
