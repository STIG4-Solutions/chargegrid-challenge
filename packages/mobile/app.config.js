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
const base = require('./app.json')

module.exports = () => {
  const chaveDoMapa = process.env.GOOGLE_MAPS_API_KEY ?? ''

  return {
    ...base.expo,
    android: {
      ...base.expo.android,
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
      mapaConfigurado: chaveDoMapa.length > 0
    }
  }
}
