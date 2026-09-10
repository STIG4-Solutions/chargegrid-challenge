# ChargeGrid — app do motorista

App multiplataforma (iOS + Android) em **React Native + Expo**. É o cliente do
usuário final do desafio ChargeGrid Intelligence: encontrar uma estação, iniciar
a recarga, acompanhar o custo e encerrar.

Consome a mesma API do dashboard comercial através do **`@chargegrid/sdk`**
(`packages/sdk`) — nenhuma chamada `fetch` mora aqui.

## Rodar

Precisa da API no ar (`apps/api/` deste repositório, veja o README de lá). Depois:

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
cp .env.example .env      # aqui em apps/mobile, não na raiz
# EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
npm run mobile            # a partir da raiz do repositório; depois tecle "a"
```

O Expo instala o Expo Go no emulador sozinho (~200 MB), então o AVD precisa de
espaço livre em `/data` — confira com `adb shell df -h /data`. Um AVD cheio falha
com *"Requested internal only, but not enough space"*, e `pm trim-caches` não
devolve espaço suficiente: o jeito é um AVD com partição maior.

> **No Git Bash, prefixe comandos `adb shell` com `MSYS_NO_PATHCONV=1`.** Sem
> isso o MSYS traduz `/data` para `C:/Program Files/Git/data` antes de o comando
> chegar ao aparelho, e o erro que aparece é um `No such file or directory` que
> não tem nada a ver com o Android.

> **O mapa só aparece com uma chave do Google Maps.** Veja a seção abaixo. Sem
> ela o app mostra um aviso no lugar do mapa e a lista de estações continua
> funcionando. No iOS o mapa usa Apple Maps e não precisa de chave.

### Quando o aparelho não alcança a API

O app mostra *"Sem conexão com a API"* mesmo com o celular na mesma Wi-Fi. Confira nesta
ordem — do mais provável ao menos:

1. **Proxy configurado no aparelho.** Um proxy nas definições de Wi-Fi do celular desvia o
   tráfego e o IP da rede local deixa de ser alcançável. Já aconteceu aqui.
2. **A API só escuta no loopback.** Use `uvicorn app.main:app --host 0.0.0.0 --port 8000`;
   com `127.0.0.1` nada de fora alcança.
3. **Firewall do Windows.** Se a rede estiver classificada como *Pública*, o perfil bloqueia
   conexões de entrada. Marque-a como *Privada* ou libere a porta.
4. **Isolamento de clientes no roteador.** Impede aparelhos de conversarem entre si. Contorno:
   USB com `adb reverse tcp:8000 tcp:8000` e a URL apontando para `localhost`.

O teste que separa app de rede: abra `http://SEU-IP:8000/health` **no navegador do celular**.
Se não responder ali, o problema não é do app.

## Chave do Google Maps

No Android o `react-native-maps` usa o Google Maps, que exige chave própria.
Precisa de uma conta no Google Cloud **com faturamento habilitado** — mesmo no
nível gratuito. Para um protótipo o consumo fica dentro da franquia mensal com
folga.

**1. Criar e restringir a chave** em [console.cloud.google.com](https://console.cloud.google.com):

- Crie um projeto, e em *APIs e serviços → Biblioteca* habilite **Maps SDK for Android**.
- Em *Credenciais*, crie uma **chave de API**.
- Restrinja a chave — este passo não é opcional. Em *Restrições de aplicativo*
  escolha **Apps Android** e cadastre o par abaixo.
- Em *Restrições de API*, marque **apenas Maps SDK for Android**. Nem
  *Maps SDK for iOS*: no iOS o `PROVIDER_DEFAULT` usa Apple Maps, que dispensa
  chave. E nenhuma das APIs de serviço web — o app não usa Geocoding, Places nem
  Directions, e a distância até a estação é calculada por haversine no backend.

> **Por que restringir a API se já restringi o app.** São camadas independentes,
> e a primeira não cobre a segunda: a restrição por app Android vale para os SDKs
> nativos, mas as APIs de serviço web **não a aceitam** — só entendem restrição
> por IP ou referrer. Deixá-las habilitadas não dá capacidade nenhuma a mais,
> apenas amplia o estrago se a restrição de app for afrouxada. E a diferença de
> preço é grande: carregamento de mapa é barato, Places e Directions custam por
> chamada e escalam rápido.
>
> Se um dia o app precisar de busca de endereço ou rota, crie uma **chave
> separada** — os tipos de restrição não convivem bem na mesma chave, e chamadas
> de serviço web ficam melhor no backend, com chave restrita por IP do servidor.
>
> Vale também pôr um **alerta de orçamento** em *Faturamento → Orçamentos e
> alertas*. Um protótipo não chega perto da franquia; o alerta é o que avisa se
> alguém estiver usando a chave indevidamente antes de a fatura chegar.

| | |
|---|---|
| Nome do pacote | `br.com.chargegrid.app` |
| SHA-1 (builds do EAS) | `C8:3A:F5:25:64:6D:2C:78:39:6F:02:F5:0F:E4:9E:81:C5:3A:F5:00` |
| SHA-1 (builds locais de debug) | `1E:F7:90:5E:6D:11:EC:D0:05:C1:8A:C5:47:45:0C:D2:0B:4D:81:4C` |

Cadastre os dois: o primeiro assina o APK que sai da nuvem, o segundo os builds
locais. Se a keystore do EAS for trocada, o SHA-1 muda — consulte com
`eas credentials` ou extraia do APK:

```bash
apksigner verify --print-certs app-release.apk
```

**2. Guardar a chave fora do repositório.**

Toda chave de Maps para Android acaba dentro do APK e pode ser extraída de lá —
por isso a proteção real é a **restrição** acima, não o sigilo. Mas este
repositório é público, e chave exposta é raspada por robôs: a cota queimada
seria sua. Então ela não vai no `app.json`.

```bash
# local — no .env deste diretório, que o git ignora
echo GOOGLE_MAPS_API_KEY=AIza... >> .env

# nuvem — segredo do projeto no EAS, nunca no eas.json
npx eas-cli secret:create --scope project --name GOOGLE_MAPS_API_KEY --value AIza...
```

O `app.config.js` injeta a chave na configuração nativa e publica um booleano
`extra.mapaConfigurado`. O app consulta **o booleano**, não a chave: o
`android.config` é podado do manifesto público que o `Constants` lê, então
perguntar pela chave em tempo de execução devolveria vazio mesmo com ela
configurada — e o mapa ficaria escondido para sempre.

Depois de definir a variável, rode o build de novo. Nenhuma mudança de código é
necessária.

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

Uma conta de `admin` ou `operator` é recusada na entrada, e o servidor devolve
`403` nas rotas `/app/*` — a guarda `require_driver` em `app/core/deps.py`.

> Isso não era verdade até 28/08/2026, embora este README afirmasse que sim: as
> rotas usavam só `CurrentUser`, que valida o token mas não o papel, e um token
> de operador recebia `200`. Não havia vazamento, porque todas filtram por
> `user.id`, mas a escrita passava. `tests/test_http_autorizacao.py` cobre isso
> agora.

## App instalável, sem o Expo Go

O Expo Go é ótimo para desenvolver, mas o app fica dentro dele. Para ter o
**ícone próprio na gaveta de apps**, gere um build nativo.

**Neste repositório o caminho é a nuvem** — o build local não sai no Windows, e a
seção adiante explica por quê:

```bash
npx eas-cli build -p android --profile preview
```

O link devolvido, aberto no próprio Android, instala o APK. Validado em aparelho
físico: câmera, mapa, leitura de QR e sessão contra a API real.

Localmente, com JDK 17+ e o SDK do Android no ambiente (`JAVA_HOME` e
`ANDROID_HOME` apontados):

```bash
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

Cinco abas — **Mapa**, **Agenda**, **Histórico**, **Missões** e **Perfil** — com telas
empilhadas sobre elas. Uma sexta, **Frota**, aparece só para quem é gestor: a API responde 403
para os demais, e uma aba que só mostra erro é pior que aba nenhuma.

**Missões não é condicional**, e a diferença importa: todo motorista pode ter missão, e a tela
já diz o que fazer quando não há campanha vigente. Vazio explicado não é erro — é a distinção
entre "nada agora" e "o app quebrou".

| Tela | Arquivo | Endpoints (via SDK) |
|---|---|---|
| Login | `src/screens/LoginScreen.tsx` | `auth.login`, `auth.me` |
| Mapa e lista de estações | `src/screens/MapScreen.tsx` | `app.stations`, `app.activeSession` |
| Vagas da estação | `src/screens/StationScreen.tsx` | `app.stationChargePoints`, `app.startSession` |
| Minha recarga | `src/screens/SessionScreen.tsx` | `app.activeSession`, `app.sessionPreview`, `app.stopSession` |
| Agenda | `src/screens/ReservationsScreen.tsx` | `app.myReservations`, `app.cancelReservation` |
| Agendar recarga | `src/screens/NewReservationScreen.tsx` | `app.stations`, `app.stationChargePoints`, `app.myVehicles`, `app.createReservation` |
| Histórico (recargas e faturas) | `src/screens/HistoryScreen.tsx` | `app.mySessions`, `app.myInvoices` |
| Missões | `src/screens/MissionsScreen.tsx` | `app.missions`, `app.rewards` |
| Perfil (carteira, veículos e plano) | `src/screens/ProfileScreen.tsx` | `app.myVehicles`, `app.addVehicle`, `app.topUpWallet`, `app.plans`, `app.subscription`, `app.subscribe`, `app.unsubscribe` |
| Ler QR do carregador | `src/screens/ScannerScreen.tsx` | `app.chargePointByCode` |
| Frota (só gestor) | `src/screens/FleetScreen.tsx` | `app.fleetReport` |

Componentes que vivem fora das telas, porque aparecem em mais de uma:

| Componente | Arquivo | O que faz |
|---|---|---|
| Teto da recarga | `src/LimiteDaRecarga.tsx` | "pare em 30 kWh / 45 min / R$ 50" antes de iniciar |
| Quando começar | `src/QuandoComecar.tsx` | compara agora com o melhor horário à frente |
| Reportar problema | `src/ReportarProblema.tsx` | categoria fechada + detalhe opcional |
| Recibo | `src/BotaoRecibo.tsx` | busca o HTML da API, vira PDF e abre o compartilhamento |
| Push | `src/push.ts` | registra o aparelho no login, remove no logout |

Todas as operações do escopo `/app/*` têm tela ou componente.

A tela de recarga mostra a **fila de espera**: quando não há potência livre, a
sessão entra em `queued` com a posição na fila e começa sozinha assim que o
rateio do servidor liberar. O app só reflete a decisão do servidor.

O custo exibido vem de `app.sessionPreview`, que roda **o mesmo motor de
tarifação que emite a fatura** — não é uma estimativa paralela.

A aba de missões traduz cada métrica para a unidade certa: "3 de 5 recargas", "11,8 de 50 kWh
solares". Sem isso a tela diria "3 de 5 energia_verde_kwh", que é o nome da coluna e não o nome
da coisa. Missões que o motorista ainda não começou aparecem com barra zerada — quem acabou de
instalar o app é justamente quem mais precisa ver o que há para ganhar.

O bloco de plano no Perfil distingue **"assina"** de **"renova"**. Cancelada dentro do mês pago
continua dando desconto até o fim do período, e dizer só "cancelada" faria o motorista achar
que perdeu o que pagou.

## Metro em workspace

`metro.config.js` tem dois ajustes, ambos comentados no arquivo:

1. **`watchFolders`** — o SDK está fora de `apps/mobile`; sem isso o bundler
   não o enxerga nem recarrega quando ele muda.
2. **`nodeModulesPaths`** — procura dependências no app antes da raiz.

Não há resolver customizado de React ali, e isso é uma escolha: dashboard e app
declaram **a mesma versão** (`19.2.3`, exigida pelo React Native 0.86), então o
npm iça uma cópia só para a raiz do workspace e o SDK não tem como carregar
outra. Se as versões voltarem a divergir, o Metro precisará de um
`resolveRequest` fixando o React — duas cópias no mesmo bundle quebram todo hook
com *"Invalid hook call"*.

O SDK é consumido como **código-fonte TypeScript**, sem etapa de build: o Metro
o compila junto com o app, do mesmo jeito que o Vite faz no dashboard.

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

## A câmera não é uma view como as outras

O leitor de QR abriu **totalmente preto** no aparelho físico até se descobrir por quê. Não era
permissão nem falha ao abrir a câmera: o logcat trazia `Camera open completed, errorCode=null` e
a camada tinha `activeBuffer=[1024x768]`. A câmera entregava quadros o tempo todo — eles nunca
chegavam à tela.

A prévia do `expo-camera` é um `SurfaceView` composto em `z=-2`, ou seja **abaixo** da janela do
app. Ela aparece por um furo transparente que o Android recorta no lugar dela. Duas coisas
comuns de escrever destroem esse furo:

| O que se escreve | O que acontece |
|---|---|
| `borderRadius` + `overflow: 'hidden'` no container | o Android renderiza o pai num buffer à parte; o recorte deixa de valer |
| `backgroundColor` opaco no container | pinta por cima do furo |

Por isso `src/screens/ScannerScreen.tsx` mantém o visor como um retângulo de **altura fixa, sem
cantos arredondados e sem cor de fundo**. É feio de propósito — não dá para ter os dois.

Pela mesma razão a mira e a instrução ficam **abaixo** do retângulo, não sobre ele. O
`CameraView` não aceita filhos, e um irmão sobreposto depende da ordem de composição da
superfície nativa, que varia entre aparelhos. Com os controles fora do retângulo, a entrada
manual continua alcançável mesmo se a prévia falhar — e `onMountError` troca o visor por uma
explicação em vez de deixar preto.

A prévia também **desmonta quando a tela perde o foco** (`useIsFocused`): uma superfície nativa
que fica montada em segundo plano volta preta na visita seguinte.

> Para diagnosticar de novo, o comando que responde é
> `adb shell dumpsys SurfaceFlinger | grep -A4 SurfaceView`. Um `activeBuffer` com dimensões
> reais significa que a câmera está funcionando e o problema é de composição — não adianta mexer
> em permissão.
>
> `adb exec-out screencap` **não** é prova de nada aqui: superfícies de câmera saem pretas na
> captura mesmo quando estão desenhando na tela.

## Áreas seguras

O Android 16 tornou o desenho ponta a ponta obrigatório: o app pinta por baixo da barra de
status e da barra de navegação. Sem recuo, o conteúdo encosta nos ícones do sistema e o primeiro
toque cai na barra, não no botão.

Quem reserva o espaço depende de onde a tela está:

| Tela | Topo | Base |
|---|---|---|
| Abas (Mapa, Agenda, Histórico, Perfil) | `<Tela>` aplica `insets.top` | a barra de abas já reserva |
| Empilhadas (Estação, Sessão, Agendar, Escanear) | o cabeçalho do navegador segura | `useRecuoInferior()` no conteúdo rolável |
| Login | por conta própria — fica fora de qualquer navegador | idem |

Os dois utilitários estão em `src/components.tsx`. **Não use `useRecuoInferior()` numa tela de
aba**: a barra de abas já reserva a base e o recuo sairia contado duas vezes.

## Notificação push

Registro no **login**, não na abertura do app: pedir permissão de notificação para quem ainda
não entrou é pedir antes de haver o que notificar, e a recusa é permanente — o sistema não
pergunta de novo.

O logout desregistra **antes** de descartar o token, senão a chamada sai sem credencial e o
aparelho continua recebendo as notificações de quem saiu. E o token pertence ao aparelho, não à
pessoa: celular emprestado sem o reaponte faria o segundo motorista receber os avisos do
primeiro, com código da recarga e valor.

Tudo em `src/push.ts` falha em silêncio de propósito. Push é um extra: permissão negada,
emulador, serviço fora do ar — o app continua funcionando exatamente como antes. Um erro de
registro não pode impedir alguém de carregar o carro.

Três coisas que atrapalham quem for testar:

- **emulador não recebe push.** `Device.isDevice` corta antes de tentar; sem isso o console
  enche de erro toda vez que o app abre em desenvolvimento.
- **sem canal, o Android 8+ descarta a notificação** sem avisar ninguém. O canal `recargas` é
  criado no registro.
- **o servidor precisa entregar de verdade.** Com `PUSH_PROVIDER=log` ele monta a mensagem e
  registra — todo o caminho é exercitado até a borda, mas nada sai. O ambiente de
  desenvolvimento deste repositório já está com `expo`.
- **`finished` notifica; `billed` não.** A máquina de estados só permite `finished → billed`,
  então toda sessão faturada já foi avisada. Aceitar os dois mandava duas mensagens com texto
  idêntico — e duas notificações iguais são piores que uma: o motorista aprende que o app repete
  e para de ler.

### FCM

**Já está configurado** neste projeto: `challenge-chargegrid` no Firebase, chave FCM V1 no EAS e
`PUSH_PROVIDER=expo` na API. O que segue é o procedimento, para refazer noutro ambiente.

Sem ele o Android não sabe a quem pedir o token, e o app **não pede permissão** — a recusa do
sistema é permanente, e gastar a única chance num build que nunca receberia nada custa caro. O
sinal é `extra.pushConfigurado`, posto pelo `app.config.js` quando encontra o arquivo.

Quatro passos, três deles no console do Google:

1. **Projeto no Firebase** com um app Android de pacote `br.com.chargegrid.app` — o pacote tem
   de bater exatamente, ou o token é emitido para outro app.
2. **Baixe `google-services.json`** e coloque em `apps/mobile/` (o git ignora) para builds
   locais. Para a nuvem, suba como variável de ambiente do tipo *file*:
   ```bash
   npx eas-cli env:create --environment preview --name GOOGLE_SERVICES_JSON      --type file --value ./google-services.json --visibility sensitive
   ```
3. **Chave de serviço FCM V1**: no Firebase, *Configurações do projeto → Contas de serviço →
   Gerar nova chave privada*. Suba em `npx eas-cli credentials -p android`, escolhendo o perfil
   **preview** e então *Google Service Account → Manage your Google Service Account Key for Push
   Notifications (FCM V1) → Set up a new key*. É interativo, e a chave nunca passa pelo
   repositório — aponte o caminho de onde ela foi baixada, sem copiá-la para o projeto.

   Dois tropeços comuns: esse JSON **não** é o `google-services.json` do passo 2, e a opção
   *Push Notifications (Legacy)* do menu é a API antiga do FCM, desligada pelo Google em 2024.
4. **Na API**, `PUSH_PROVIDER=expo`. O código não muda: o provedor já é plugável.

Depois disso, **build novo** — `google-services.json` entra no projeto nativo, não por OTA.

## A folha de reporte não é uma tela como as outras

`ReportarProblema` é o único `Modal` do app, e por isso foi o único lugar onde o recuo de área
segura ficou de fora — todas as telas o aplicam via `Tela` ou `useRecuoInferior`. O sintoma
apareceu só no aparelho: "Cancelar" nascia debaixo dos botões de navegação do Android. Visível,
mas o toque ia para o sistema.

Três coisas que uma folha inferior precisa e uma tela normal não:

- **`statusBarTranslucent` e `navigationBarTranslucent`.** O `Modal` monta fora da hierarquia do
  app, então o inset pode vir zerado. Essas duas fazem a folha desenhar sob as barras, que é de
  onde o inset sai. Um piso de 16 cobre o caso de vir zero mesmo assim.
- **Altura por espaço reservado, não por porcentagem.** `maxHeight: '85%'` deixava as ações fora
  da tela em aparelho baixo — o mesmo sintoma do recuo ausente, por outro caminho. Quem limita
  agora é uma área com `flex: 1` acima da folha, que também fecha ao toque.
- **`KeyboardAvoidingView`.** O campo de detalhes fica no fim; sem ele o teclado cobre justamente
  o que o motorista ia escrever.

## Recibo em PDF

`expo-print` converte o HTML que a **API** devolve; o app não monta o documento. Se montasse, os
números dependeriam da versão instalada — dois motoristas com builds diferentes gerariam
documentos diferentes para a mesma fatura.

Sem app de compartilhamento (raro, mas acontece em aparelho corporativo travado) cai em
`Print.printAsync`, e o diálogo do sistema oferece "salvar como PDF". Diferente do push, aqui o
erro **aparece na tela**: o motorista pediu o documento, então precisa saber se não saiu.

## Módulos nativos

`expo-notifications`, `expo-print`, `expo-sharing` e `expo-device` entraram junto com essas
features. São nativos: exigem **build novo**, não entram por atualização OTA. Os plugins estão
declarados no `app.json`.

## O que ainda não tem

**Pagamento real.** A carteira credita direto; não há provedor. Na integração de verdade o
crédito só entra depois que o PSP confirma — a rota `POST /app/wallet/topup` representa esse
passo final.

**Ícones da barra de abas são glifos de texto.** Quatro caracteres evitam mais uma dependência
nativa. Se a barra crescer, vale trocar por `@expo/vector-icons`.
