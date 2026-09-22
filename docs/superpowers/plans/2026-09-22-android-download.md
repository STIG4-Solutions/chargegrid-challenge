# Android Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a página de download Android e a rota estável que encaminha o usuário ao APK correto no Cloudflare R2.

**Architecture:** O React Router mantém `/` e `/download` como páginas independentes. Uma Pages Function em `functions/download/android.js` lê `ANDROID_APK_URL` no runtime e devolve um redirecionamento temporário, permitindo valores distintos em Production e Preview sem expor configuração no repositório.

**Tech Stack:** React 19, React Router 7, Vite 8, Vitest 5, Testing Library, Cloudflare Pages Functions e CSS.

**Spec:** `docs/superpowers/specs/2026-09-22-site-download.md`

## Global Constraints

- A landing em `/` deve continuar vazia.
- Não alterar `apps/api`, `apps/dashboard` ou `apps/mobile`.
- Não registrar URLs reais de APK nem credenciais.
- O download público deve usar somente o APK de produção.
- Staging, previews e APK de staging devem exigir acesso da equipe.
- A interface deve funcionar com teclado, telas pequenas e `prefers-reduced-motion`.

## Review Focus

- Variável de APK ausente ou malformada deve produzir `503`, nunca redirecionar parcialmente.
- Uma URL `http:` deve ser recusada para evitar transporte inseguro.
- O CTA da página deve apontar apenas para `/download/android`, sem incorporar o endereço do R2.
- A rota `/` deve permanecer sem conteúdo após a adição do layout de download.
- A proteção de staging depende de Cloudflare Access e deve estar documentada para o site e para o domínio R2.

---

### Task 1: Contrato das rotas React

**Files:**
- Modify: `apps/site/package.json`
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `apps/site/src/test/setup.js`
- Create: `apps/site/src/App.test.jsx`
- Modify: `apps/site/vite.config.js`

**Interfaces:**
- Produces: suíte Vitest com `jsdom` e os contratos visíveis de `/` e `/download`.
- Consumes: `App` e as rotas registradas em `apps/site/src/App.jsx`.

- [ ] Escrever teste que confirma que `/` renderiza um contêiner vazio.
- [ ] Escrever teste que espera em `/download` o título “Sua recarga continua no bolso”, um link para `/download/android` e três passos ordenados.
- [ ] Executar `npm run test:site`; esperar falha porque `/download` ainda não existe.
- [ ] Adicionar apenas a configuração mínima de Vitest e Testing Library necessária para executar os testes.

### Task 2: Página de download

**Files:**
- Modify: `apps/site/src/App.jsx`
- Create: `apps/site/src/pages/DownloadPage.jsx`
- Create: `apps/site/src/styles/download.css`
- Copy: `apps/mobile/assets/icon.png` to `apps/site/public/chargegrid-app-icon.png`
- Modify: `apps/site/index.html`

**Interfaces:**
- Consumes: contrato visual de `apps/site/src/App.test.jsx`.
- Produces: rota `/download` e link estável para `/download/android`.

- [ ] Registrar `/download` sem adicionar layout à rota `/`.
- [ ] Implementar o hero, o cartão do aplicativo, o CTA e os três passos de instalação.
- [ ] Implementar estados de foco, responsividade e redução de movimento no CSS.
- [ ] Executar `npm run test:site`; esperar todos os testes da aplicação verdes.

### Task 3: Redirecionamento, documentação e CI

**Files:**
- Create: `apps/site/functions/download/android.js`
- Create: `apps/site/functions/download/android.test.js`
- Modify: `apps/site/README.md`
- Create: `docs/site-deployment.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `ANDROID_APK_URL` do ambiente Cloudflare Pages.
- Produces: `onRequestGet(context)` com resposta `302` ou `503` e instruções completas de publicação.

- [ ] Escrever testes para variável ausente, URL inválida, protocolo não HTTPS e redirecionamento válido.
- [ ] Executar `npm run test:site`; esperar falha porque a Function ainda não existe.
- [ ] Implementar `onRequestGet` com validação HTTPS, `302`, `Location` e `Cache-Control: no-store`.
- [ ] Executar `npm run test:site`; esperar todos os testes verdes.
- [ ] Documentar Production, Preview, domínio por branch, R2 e Cloudflare Access sem preencher URLs reais.
- [ ] Incluir `npm run test:site` no CI.
- [ ] Executar `npm run format:check`, `npm run test:site` e `npm run build:site`; esperar saída sem erros.
