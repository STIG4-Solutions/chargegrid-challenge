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

Quatro abas — **Mapa**, **Agenda**, **Histórico** e **Perfil** — com telas empilhadas sobre elas.

| Tela | Arquivo | Endpoints (via SDK) |
|---|---|---|
| Login | `src/screens/LoginScreen.tsx` | `auth.login`, `auth.me` |
| Mapa e lista de estações | `src/screens/MapScreen.tsx` | `app.stations`, `app.activeSession` |
| Vagas da estação | `src/screens/StationScreen.tsx` | `app.stationChargePoints`, `app.startSession` |
| Minha recarga | `src/screens/SessionScreen.tsx` | `app.activeSession`, `app.sessionPreview`, `app.stopSession` |
| Agenda | `src/screens/ReservationsScreen.tsx` | `app.myReservations`, `app.cancelReservation` |
| Agendar recarga | `src/screens/NewReservationScreen.tsx` | `app.stations`, `app.stationChargePoints`, `app.myVehicles`, `app.createReservation` |
| Histórico (recargas e faturas) | `src/screens/HistoryScreen.tsx` | `app.mySessions`, `app.myInvoices` |
| Perfil (carteira e veículos) | `src/screens/ProfileScreen.tsx` | `app.myVehicles`, `app.addVehicle`, `app.topUpWallet` |

Todos os catorze endpoints do escopo `/app/*` têm tela.

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

**Leitura de QR code no ponto.** Precisaria de um `GET /app/charge-points/by-code/{código}`
no backend e de acesso à câmera (`expo-camera`). Hoje o motorista escolhe a vaga na tela da
estação, que resolve o mesmo problema sem módulo nativo a mais.

**Pagamento real.** A carteira credita direto; não há provedor. Na integração de verdade o
crédito só entra depois que o PSP confirma — a rota `POST /app/wallet/topup` representa esse
passo final.

**Ícones da barra de abas são glifos de texto.** Quatro caracteres evitam mais uma dependência
nativa. Se a barra crescer, vale trocar por `@expo/vector-icons`.
