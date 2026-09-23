const fs = require('node:fs')
const path = require('node:path')

const dominios = require('../../config/domains.json')

const variante = process.env.APP_VARIANT ?? 'production'
const ehStaging = variante === 'preview'

function arquivoDoFirebase() {
  const candidatos = [
    process.env.GOOGLE_SERVICES_JSON,
    path.join(__dirname, 'google-services.json')
  ].filter(Boolean)

  return candidatos.find((caminho) => fs.existsSync(caminho)) ?? null
}

module.exports = ({ config }) => {
  const chaveDoMapa = process.env.GOOGLE_MAPS_API_KEY ?? ''
  const googleServices = arquivoDoFirebase()

  const apiPadrao = process.env.EXPO_PUBLIC_API_URL ?? `${dominios.protocolo}://${dominios.api}`

  return {
    ...config,

    name: ehStaging ? 'ChargeGrid Staging' : 'ChargeGrid',

    scheme: ehStaging ? 'chargegrid-staging' : 'chargegrid',

    ios: {
      ...config.ios,

      bundleIdentifier: ehStaging ? 'br.com.chargegrid.app.staging' : 'br.com.chargegrid.app'
    },

    android: {
      ...config.android,

      package: ehStaging ? 'br.com.chargegrid.app.staging' : 'br.com.chargegrid.app',

      ...(googleServices
        ? {
            googleServicesFile: googleServices
          }
        : {}),

      config: {
        ...config.android?.config,

        googleMaps: {
          apiKey: chaveDoMapa
        }
      }
    },

    extra: {
      ...(config.extra ?? {}),

      mapaConfigurado: chaveDoMapa.length > 0,

      pushConfigurado: googleServices !== null,

      apiPadrao,

      siteUrl: `${dominios.protocolo}://${dominios.site}`,

      appVariant: variante
    }
  }
}
