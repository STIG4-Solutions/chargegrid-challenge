# Site ChargeGrid

Aplicação React responsável pelo site institucional e, futuramente, pela central de download do aplicativo Android.

## Desenvolvimento local

Na raiz do monorepositório:

```bash
npm install
npm run dev:site
```

O site fica disponível em `http://localhost:5174`.

## Estrutura inicial

- `src/pages/LandingPage.jsx`: landing institucional. Nesta entrega, permanece vazia.
- `src/App.jsx`: registro das rotas públicas do site.
- `src/styles/global.css`: estilos globais compartilhados.
- `public/_redirects`: fallback de rotas para o Cloudflare Pages.

A rota de download será adicionada em uma etapa separada.

## Cloudflare Pages

- Comando de build: `npm run build:site`
- Diretório de saída: `apps/site/dist`
- Diretório raiz: raiz do monorepositório
- Produção: branch `main`, domínio `stig4.com`
- Homologação: branch `staging`, domínio `staging.stig4.com`
