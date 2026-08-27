# ChargeGrid — app do motorista

App multiplataforma (iOS + Android) em **React Native + Expo**. É o cliente do
usuário final do desafio ChargeGrid Intelligence: encontrar uma estação, iniciar
a recarga, acompanhar o custo e encerrar.

Consome a mesma API do painel comercial através do **`@chargegrid/sdk`**
(`packages/sdk`) — nenhuma chamada `fetch` mora aqui.

## Rodar

Precisa da API no ar (`backend/` deste repositório, veja o README de lá). Depois:

```bash
npm run mobile           # a partir da raiz do repositório
# ou: npm start -w @chargegrid/mobile
```

Leia o QR code com o **Expo Go** (Android/iOS) ou pressione `a` / `i` para
emulador.

> **O app descobre o endereço da API sozinho.** `localhost` dentro do celular é
> o próprio celular, nunca o seu computador. Como o Expo já sabe o IP da máquina
> que serve o bundle, `src/api.ts` reaproveita esse IP e troca a porta para 8000.
> Para apontar para outro lugar, defina `EXPO_PUBLIC_API_URL`.

Contas de motorista criadas pelo seed: `joao.silva@email.com`, `maria.souza@email.com`,
`carlos.lima@email.com`, `ana.costa@email.com`, `pedro.alves@email.com` — todas com a
senha definida em `SEED_DRIVER_PASSWORD` (ou a que o seed sorteou e imprimiu).

Para o app preencher o formulário sozinho em desenvolvimento, defina
`EXPO_PUBLIC_DEMO_DRIVER_EMAIL` e `EXPO_PUBLIC_DEMO_DRIVER_PASSWORD`.

Uma conta de `admin` ou `operator` é recusada na entrada: o app é do motorista, e
o servidor devolveria 403 nas rotas `/app/*` de qualquer forma.

## Telas

| Tela | Arquivo | Endpoints (via SDK) |
|---|---|---|
| Login | `src/screens/LoginScreen.tsx` | `auth.login`, `auth.me` |
| Mapa e lista de estações | `src/screens/MapScreen.tsx` | `app.stations`, `app.activeSession` |
| Vagas da estação | `src/screens/StationScreen.tsx` | `app.stationChargePoints`, `app.startSession` |
| Minha recarga | `src/screens/SessionScreen.tsx` | `app.activeSession`, `app.sessionPreview`, `app.stopSession` |

A tela de recarga mostra a **fila de espera**: quando não há potência livre, a
sessão entra em `queued` com a posição na fila e começa sozinha assim que o
rateio do servidor liberar. O app só reflete a decisão do servidor.

O custo exibido vem de `app.sessionPreview`, que roda **o mesmo motor de
tarifação que emite a fatura** — não é uma estimativa paralela.

## Metro em workspace

`metro.config.js` tem dois ajustes, ambos comentados no arquivo:

1. **`watchFolders`** — o SDK está fora de `packages/mobile`; sem isso o bundler
   não o enxerga nem recarrega quando ele muda.
2. **`nodeModulesPaths`** — procura dependências no app antes da raiz.

Não há resolver customizado de React ali, e isso é uma escolha: painel e app
declaram **a mesma versão** (`19.2.3`, exigida pelo React Native 0.86), então o
npm iça uma cópia só para a raiz do workspace e o SDK não tem como carregar
outra. Se as versões voltarem a divergir, o Metro precisará de um
`resolveRequest` fixando o React — duas cópias no mesmo bundle quebram todo hook
com *"Invalid hook call"*.

O SDK é consumido como **código-fonte TypeScript**, sem etapa de build: o Metro
o compila junto com o app, do mesmo jeito que o Vite faz no painel.

Para conferir que o bundle fecha nas duas plataformas sem precisar de aparelho:

```bash
npx expo export --platform android --output-dir .expo-bundle
npx expo export --platform ios --output-dir .expo-bundle
```

## O que ainda não tem

Escopo deixado de fora de propósito nesta etapa, tudo já suportado pela API:
agendamento (`app.createReservation`), veículos (`app.myVehicles`), faturas
(`app.myInvoices`), recarga de carteira (`app.topUpWallet`) e leitura de QR code
no ponto — esta última ainda precisa de um `GET /app/charge-points/by-code/{código}`
no backend.
