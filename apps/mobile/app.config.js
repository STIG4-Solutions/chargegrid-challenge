// Configuracao dinamica do app.
//
// O app.json continua sendo a fonte de tudo que e' estatico. Este arquivo
// existe por um motivo so': a chave do Google Maps nao pode ser versionada.
//
// Ela nao e' exatamente um segredo - toda chave de Maps para Android acaba
// dentro do APK, e qualquer um consegue extrai-la de la'. A protecao real e' a
// **restricao** da chave no Google Cloud (pacote + impressao digital do
// certificado), nao o sigilo. Mas deixa-la num repositorio publico e' convite
// para raspagem automatizada, e cota queimada por terceiros e' cota sua.
//
// De onde vem o valor:
//   local  -> GOOGLE_MAPS_API_KEY no .env deste diretorio (ignorado pelo git)
//   nuvem  -> segredo do projeto no EAS:
//             eas secret:create --scope project --name GOOGLE_MAPS_API_KEY --value ...
//
// Sem a chave o app abre normalmente: a tela do mapa mostra um aviso no lugar
// e a lista de estacoes continua entregando o essencial.
const fs = require('node:fs')
const path = require('node:path')

const base = require('./app.json')
// Fonte unica dos enderecos do projeto. Aqui o valor e' EMBUTIDO no APK no
// momento do build - um app instalado nao le arquivo de configuracao do
// servidor -, entao trocar de dominio exige gerar o pacote de novo.
const dominios = require('../../config/domains.json')

// google-services.json: identifica o app no Firebase, e sem ele o Android nao
// sabe para onde pedir o token de push.
//
// Nao e' segredo - vai dentro do APK e qualquer um extrai. Mas, como a chave do
// Maps, nao entra num repositorio publico: identificador de projeto colhido em
// massa vira cota queimada e ruido de abuso. O caminho pode vir por variavel
// (o EAS materializa arquivos de env em disco e exporta o caminho) ou do
// proprio diretorio, para quem builda local.
function arquivoDoFirebase() {
  const candidatos = [
    process.env.GOOGLE_SERVICES_JSON,
    path.join(__dirname, 'google-services.json')
  ].filter(Boolean)
  return candidatos.find((caminho) => fs.existsSync(caminho)) ?? null
}

module.exports = () => {
  const chaveDoMapa = process.env.GOOGLE_MAPS_API_KEY ?? ''
  const googleServices = arquivoDoFirebase()
    const apiPadrao = `${dominios.protocolo}://${dominios.api}`

  return {
    ...base.expo,
    android: {
      ...base.expo.android,
      // Ausente, a chave nem aparece: declarar o caminho de um arquivo que nao
      // existe faz o prebuild falhar, e o app funciona sem push.
      ...(googleServices ? { googleServicesFile: googleServices } : {}),
      config: {
        ...base.expo.android.config,
        googleMaps: { apiKey: chaveDoMapa }
      }
    },
    // O app precisa saber SE o mapa pode funcionar, nunca o valor da chave. E
    // precisa dessa resposta em tempo de execucao: o `android.config` e' podado
    // do manifesto publico que o Constants le, entao consultar a chave por la'
    // devolveria vazio mesmo com ela configurada - e o mapa ficaria escondido
    // para sempre. Um booleano em `extra` sobrevive a poda.
    extra: {
      ...(base.expo.extra ?? {}),
      mapaConfigurado: chaveDoMapa.length > 0,
        // O app precisa saber SE pode registrar para push, para nao pedir
        // permissao num build que nunca vai receber nada - e a recusa de
        // notificacao e' permanente, entao gastar a unica chance a toa custa caro.
        pushConfigurado: googleServices !== null,
        // Endereco de producao, congelado no pacote. EXPO_PUBLIC_API_URL ainda
        // ganha dele em tempo de build, que e' como o emulador e o aparelho na
        // rede local apontam para a maquina de desenvolvimento.
        apiPadrao,
        // Base das URLs impressas nos adesivos de QR.
        siteUrl: `${dominios.protocolo}://${dominios.site}`
    }
  }
}
