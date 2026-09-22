# ChargeGrid Android Download

## Escopo

- Manter a rota `/` sem conteúdo, layout ou elementos compartilhados.
- Criar `/download` como página pública e responsiva para apresentar o aplicativo ChargeGrid, iniciar o download do APK e explicar a instalação no Android.
- Criar `/download/android` como uma Cloudflare Pages Function que redireciona para uma URL HTTPS configurada no ambiente.
- Usar a mesma variável `ANDROID_APK_URL` com valores diferentes nos ambientes Production e Preview do Cloudflare Pages.
- Manter `stig4.com` público e proteger `staging.stig4.com`, os previews e o domínio R2 de homologação com Cloudflare Access.
- Não registrar no repositório URLs reais dos APKs, credenciais ou objetos do R2.
- Não alterar dashboard, API ou aplicativo mobile.

## Direção visual

O assunto é o aplicativo Android usado por motoristas para encontrar estações e acompanhar recargas. A página deve conduzir uma única ação: obter o APK oficial e instalá-lo com segurança.

- **Carbono:** `#0b0c0f`
- **Grafite:** `#17191f`
- **Vermelho de carga:** `#ff3445`
- **Coral de pulso:** `#ff725c`
- **Névoa:** `#f2f4ef`
- **Aço:** `#a9aeb8`

Títulos usam uma pilha condensada e industrial; texto corrido usa a pilha do sistema; etiquetas usam monoespaçada. A assinatura visual é uma linha de energia que conecta o cartão do aplicativo aos três passos reais de instalação.

## Comportamento de falha

Se `ANDROID_APK_URL` estiver ausente, inválida ou não usar HTTPS, `/download/android` deve responder `503` com uma mensagem curta, sem revelar configuração interna. Redirecionamentos válidos devem usar `302` e `Cache-Control: no-store`.
