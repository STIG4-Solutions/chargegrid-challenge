import dominios from '../../../../config/domains.json'

const dominioPages = 'chargegrid-site.pages.dev'

function urlHttps(hostname) {
  return `${dominios.protocolo}://${hostname}`
}

export function dashboardUrlForHostname(hostname = '') {
  const host = hostname.trim().toLowerCase()

  if (host === 'localhost' || host === '127.0.0.1') {
    return dominios.desenvolvimento.dashboard
  }

  const ehDominioDeStaging = host === dominios.staging.site
  const ehPreviewDoPages = host.endsWith(`.${dominioPages}`)

  return urlHttps(
    ehDominioDeStaging || ehPreviewDoPages ? dominios.staging.dashboard : dominios.dashboard
  )
}

export const DASHBOARD_URL = dashboardUrlForHostname(globalThis.location?.hostname)
// Opcional: com usuario preenchido, o fechamento mostra o acesso de demonstracao.
export const DEMO_USER = ''
export const DEMO_PASSWORD = ''
