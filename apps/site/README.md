# Site ChargeGrid

Aplicação React responsável pelo site institucional e pela central de download do aplicativo Android.

## Desenvolvimento local

Na raiz do monorepositório:

```bash
npm install
npm run dev:site
```

O site fica disponível em `http://localhost:5174`.

## Estrutura inicial

- `src/pages/LandingPage.jsx`: landing institucional. Permanece vazia até a implementação da equipe responsável.
- `src/pages/DownloadPage.jsx`: página pública de apresentação e instalação do aplicativo.
- `src/App.jsx`: registro das rotas públicas do site.
- `src/styles/global.css`: estilos globais compartilhados.
- `public/_redirects`: fallback de rotas para o Cloudflare Pages.
- `functions/download/android.js`: redireciona o download para o APK configurado no ambiente.

O site não contém uma URL de APK. `/download/android` lê `ANDROID_APK_URL` no runtime do Cloudflare Pages e responde `503` quando ela não está configurada corretamente.

## Verificação

Na raiz do monorepositório:

```bash
npm run test:site
npm run build:site
```

## Cloudflare Pages

- Diretório raiz: `apps/site`
- Comando de build: `npm run build`
- Diretório de saída: `dist`
- Produção: branch `main`, domínio `stig4.com`
- Homologação: branch `staging`, domínio `staging.stig4.com`

Configure `ANDROID_APK_URL` separadamente em Production e Preview. Veja `docs/site-deployment.md` para a configuração do Pages, R2 e Cloudflare Access.
