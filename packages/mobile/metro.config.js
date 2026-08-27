// Metro em workspace npm: o app vive em packages/mobile, mas importa
// @chargegrid/sdk, que e' codigo-fonte TypeScript em packages/sdk. Sem estas
// duas linhas o bundler nao enxerga nem observa aquele diretorio.
const { getDefaultConfig } = require('expo/metro-config')
const path = require('path')

const projeto = __dirname
const workspace = path.resolve(projeto, '../..')

const config = getDefaultConfig(projeto)

// Observar a raiz do workspace: e' onde packages/sdk esta, e e' o que faz o
// hot reload disparar quando o SDK muda.
config.watchFolders = [workspace]

// Procurar dependencias no app e depois na raiz do workspace.
config.resolver.nodeModulesPaths = [
  path.resolve(projeto, 'node_modules'),
  path.resolve(workspace, 'node_modules')
]

// Nao ha pino de React aqui de proposito: painel e app declaram a MESMA versao
// (19.2.3, exigida pelo React Native 0.86), entao o npm ica uma copia so' para
// a raiz e o SDK nao tem como carregar outra. Versoes diferentes voltariam a
// exigir um resolver customizado — e duas copias de React no mesmo bundle
// quebram todo hook com "Invalid hook call".

module.exports = config
