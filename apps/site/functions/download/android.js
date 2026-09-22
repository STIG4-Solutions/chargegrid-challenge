const unavailableMessage = 'Download temporariamente indisponível.'

function unavailableResponse() {
  return new Response(unavailableMessage, {
    status: 503,
    headers: {
      'Cache-Control': 'no-store',
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Content-Type-Options': 'nosniff'
    }
  })
}

export function onRequestGet(context) {
  const configuredUrl = context.env?.ANDROID_APK_URL

  if (!configuredUrl) return unavailableResponse()

  try {
    const apkUrl = new URL(configuredUrl)

    if (apkUrl.protocol !== 'https:') return unavailableResponse()

    return new Response(null, {
      status: 302,
      headers: {
        'Cache-Control': 'no-store',
        Location: apkUrl.href,
        'X-Content-Type-Options': 'nosniff'
      }
    })
  } catch {
    return unavailableResponse()
  }
}
