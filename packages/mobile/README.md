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
emulador. O app roda no Expo Go sem build nativo: `react-native-maps` e
`AsyncStorage` já vêm embutidos nele.

### Emulador do Android Studio

O emulador não enxerga o `localhost` da sua máquina — para ele, `localhost` é o
próprio emulador. Use o apelido `10.0.2.2`, que aponta para o loopback do host:

```bash
cp .env.example .env      # aqui em packages/mobile, não na raiz
# EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
npm run mobile            # a partir da raiz do repositório; depois tecle "a"
```

O Expo instala o Expo Go no emulador sozinho (~200 MB), então o AVD precisa de
espaço livre em `/data` — confira com `adb shell df /data`. Um AVD cheio falha
com *"Requested internal only, but not enough space"*.

> **O mapa abre cinza até você configurar uma chave.** No Android o
> `react-native-maps` usa Google Maps, que exige chave própria: gere uma no
> Google Cloud (Maps SDK for Android) e preencha `android.config.googleMaps.apiKey`
> em `app.json`. Sem ela o quadro do mapa fica vazio — a lista de estações logo
> abaixo continua funcionando normalmente. No iOS o mapa usa Apple Maps e não
> precisa de chave.

> **Sem `EXPO_PUBLIC_API_URL`, o app descobre o endereço sozinho.** `localhost`
> dentro do celular é o próprio celular, nunca o seu computador. Como o Expo já
> sabe o IP da máquina que serve o bundle, `src/api.ts` reaproveita esse IP e
> troca a porta para 8000 — o que funciona com um celular na mesma rede. No
> emulador, defina a variável explicitamente (veja acima).
>
> O `.env` fica **neste diretório**, não na raiz do workspace: o Expo lê o `.env`
> do projeto do app.

Contas de motorista criadas pelo seed: `joao.silva@email.com`, `maria.souza@email.com`,
`carlos.lima@email.com`, `ana.costa@email.com`, `pedro.alves@email.com` — todas com a
senha definida em `SEED_DRIVER_PASSWORD` (ou a que o seed sorteou e imprimiu).

Para o app preencher o formulário sozinho em desenvolvimento, defina
`EXPO_PUBLIC_DEMO_DRIVER_EMAIL` e `EXPO_PUBLIC_DEMO_DRIVER_PASSWORD`.

Uma conta de `admin` ou `operator` é recusada na entrada: o app é do motorista, e
o servidor devolveria 403 nas rotas `/app/*` de qualquer forma.

## App instalável, sem o Expo Go

O Expo Go é ótimo para desenvolver, mas o app fica dentro dele. Para ter o
**ícone próprio na gaveta de apps**, gere um build nativo:

```bash
# JDK 17+ e o SDK do Android no ambiente
set JAVA_HOME=%USERPROFILE%\.jdks\temurin-21.0.10
set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk

npx expo run:android                      # debug: precisa do Metro rodando
npx expo run:android --variant release    # release: o JS vai dentro do APK
```

O release é o que roda sozinho — o APK sai em
`android/app/build/outputs/apk/release/app-release.apk` (~77 MB) e pode ser
instalado com `adb install`. A pasta `android/` é gerada a partir do `app.json`
e não é versionada; `expo prebuild --clean` a recria.

> **Em release, os atalhos de login somem.** `__DEV__` é falso, então o
> empacotador remove o ramo que lê `EXPO_PUBLIC_DEMO_*`. É o comportamento
> desejado: o APK distribuível não carrega credencial nenhuma.

### Duas armadilhas no Windows


**HTTP em texto claro.** O Android bloqueia `http://` em release. Como a API do
protótipo é HTTP, `app.json` traz o plugin `expo-build-properties` com
`usesCleartextTraffic`. Em produção, com a API atrás de HTTPS, essa entrada sai.

**Limite de 260 caracteres no caminho — o build de release não sai daqui.** O
codegen C++ da arquitetura nova gera caminhos intermediários muito longos e o
build falha com *"Filename longer than 260 characters"*.

Medindo o caminho que falha:

```
completo:            401 caracteres   (limite 260)
  diretório do ninja: 130
  caminho relativo:   270   <- sozinho já passa de 260
```

Três coisas que **não** resolvem, todas testadas:

- **Habilitar caminhos longos no Windows** (`LongPathsEnabled=1`). A chave só vale
  para programas cujo manifesto declara suporte a caminhos longos, e o `ninja.exe`
  do NDK não declara.
- **Desligar a arquitetura nova.** O React Native 0.86 roda o codegen de qualquer
  forma; `newArchEnabled: false` não pula a etapa.
- **Mapear uma unidade curta com `subst`.** O autolinking do Expo resolve os
  caminhos com `require.resolve`, que devolve o caminho real — o Gradle passa a
  misturar as duas raízes e quebra.

Encurtar o repositório também não basta sozinho: a raiz aparece duas vezes no
caminho (no diretório de build e embutida no nome do arquivo objeto), e mesmo em
`C:\g` o total ainda estoura por 23 caracteres.

**O que funciona: compilar fora do Windows.** O `eas.json` já está configurado
com um perfil `preview` que gera APK instalável:

```bash
npx eas-cli login                              # conta gratuita da Expo
npx eas-cli build -p android --profile preview
```

O build roda em Linux, onde esse limite não existe, e devolve um link para baixar
o APK.

> **Duas coisas para acertar antes de gerar o APK.**
>
> O APK sai da nuvem com o endereço da API **embutido**, vindo de
> `build.preview.env.EXPO_PUBLIC_API_URL` no `eas.json`. Ele precisa apontar para
> uma máquina que o aparelho alcance — não adianta `localhost` nem `10.0.2.2`.
> Ajuste para o IP da sua máquina na rede (`ipconfig`) sempre que ele mudar.
>
> E a API tem que escutar **fora do loopback**, senão nada na rede a alcança:
>
> ```bash
> uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```
>
> Com esse par no lugar, o mesmo APK serve tanto o emulador quanto um celular na
> mesma Wi-Fi.

Para insistir no build local, é preciso combinar **duas** mudanças: mover o
repositório para um caminho curto (`C:\cg`) **e** apontar o `buildStagingDirectory`
do CMake para algo como `C:\b`. Isso deixa o caminho em 258 de 260 — funciona,
mas por dois caracteres de margem.

> Nada disso afeta o desenvolvimento: o Expo Go não compila nada, e o APK de
> **debug** (que precisa do Metro) monta normalmente.

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
| Ler QR do carregador | `src/screens/ScannerScreen.tsx` | `app.chargePointByCode` |

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

## Leitura de QR

O adesivo do carregador pode trazer três formatos, e `src/qr.ts` normaliza os três:

```
CP-01                                 código puro
chargegrid://cp/CP-01                 deeplink do app
https://chargegrid.com.br/cp/CP-01    URL — o formato recomendado
```

A URL é preferível: quem não tem o app instalado cai numa página em vez de num texto sem
sentido. `conteudoDoQr(codigo)` gera o conteúdo a imprimir.

Depois de ler, o app resolve o código pela API e abre a estação **com o ponto lido no topo**,
marcado — escanear e depois procurar a vaga numa lista anularia o ganho.

> **Há sempre a digitação manual.** Adesivo em carregador de rua fica sujo, riscado e
> vandalizado; sem essa saída o motorista fica preso. É também por ela que o fluxo é testável
> sem câmera.

## O que ainda não tem

**Pagamento real.** A carteira credita direto; não há provedor. Na integração de verdade o
crédito só entra depois que o PSP confirma — a rota `POST /app/wallet/topup` representa esse
passo final.

**Ícones da barra de abas são glifos de texto.** Quatro caracteres evitam mais uma dependência
nativa. Se a barra crescer, vale trocar por `@expo/vector-icons`.
