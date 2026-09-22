# Deploy do site e do APK Android

Este documento registra os pontos de configuração externos ao repositório. Nenhuma URL real de APK, chave ou credencial deve ser versionada.

## Arquitetura

- `stig4.com`: site de produção, público.
- `staging.stig4.com`: site de homologação, restrito à equipe pelo Cloudflare Access.
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
| Production | `<URL HTTPS do APK de produção no domínio personalizado do R2>` |
| Preview | `<URL HTTPS do APK de staging no domínio personalizado do R2>` |

Os valores precisam ser URLs HTTPS completas. A Function recusa valor ausente, inválido ou iniciado com `http:`.

Não reutilize o endereço de staging em Production. O caminho público `https://stig4.com/download/android` deve sempre terminar no APK de produção.

Depois de alterar uma variável, execute um novo deploy do ambiente correspondente.

## Domínios e branches

1. Adicione `stig4.com` como domínio personalizado do projeto Pages. Ele acompanha a branch `main`.
2. Faça ao menos um deploy bem-sucedido da branch `staging`.
3. Adicione `staging.stig4.com` como domínio personalizado.
4. No DNS do domínio, mantenha o registro com proxy ativado e altere o destino do CNAME para o alias da branch `staging` mostrado pelo Pages.

Não registre no repositório o nome gerado do projeto `pages.dev`; ele pertence à configuração da conta Cloudflare.

## R2 de produção

1. Envie o APK de produção ao bucket escolhido.
2. Conecte ao bucket um domínio personalizado de produção.
3. Mantenha esse domínio público.
4. Desative o endereço público `r2.dev` do bucket.
5. Copie a URL HTTPS completa do objeto para `ANDROID_APK_URL` no ambiente Production do Pages.

Use um nome de objeto versionado, por exemplo com a versão do aplicativo no nome. O padrão exato deve ser decidido no processo de release, sem ser fixado no código do site.

## R2 de staging

1. Defina o domínio personalizado que será usado pelo bucket de staging.
2. Antes de conectar esse domínio ao bucket, crie uma aplicação **Self-hosted** no Cloudflare Zero Trust para esse hostname.
3. Adicione uma política Allow limitada aos e-mails ou ao provedor de identidade da equipe.
4. Conecte o domínio protegido ao bucket.
5. Desative o endereço público `r2.dev` do bucket.
6. Copie a URL HTTPS completa do objeto para `ANDROID_APK_URL` no ambiente Preview do Pages.

Proteger somente `staging.stig4.com` não protege o objeto após o redirecionamento. O domínio personalizado do R2 de staging também precisa da própria aplicação e política do Cloudflare Access.

## Restringir a página de staging

No Cloudflare Zero Trust:

1. Crie uma aplicação Self-hosted para `staging.stig4.com/*`.
2. Adicione uma política Allow exclusiva para a equipe.
3. No projeto Pages, habilite a política de acesso para Preview Deployments, impedindo que os endereços de preview gerados fiquem públicos.

Com essas duas proteções, a página de staging e os previews exigem autenticação. A proteção do domínio R2 descrita anteriormente impede acesso direto ao APK de staging.

## Publicar uma nova versão do APK

1. Gere e valide o APK do ambiente correto.
2. Envie o arquivo ao bucket R2 correspondente usando um objeto versionado.
3. Atualize `ANDROID_APK_URL` somente no ambiente Pages correspondente.
4. Faça um novo deploy do Pages.
5. Abra `/download/android` no domínio correspondente e confirme o destino do redirecionamento.

Não é necessário alterar o React nem criar um commit apenas para trocar o APK.

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
- `staging.stig4.com` exige Cloudflare Access.
- O domínio R2 de staging exige Cloudflare Access mesmo quando acessado diretamente.
- Os endereços `r2.dev` dos buckets estão desativados.
- Nenhuma URL real do objeto ou credencial entrou no Git.
