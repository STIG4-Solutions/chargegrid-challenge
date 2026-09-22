import { describe, expect, test } from 'vitest'
import { onRequestGet } from './android.js'

async function requestDownload(androidApkUrl) {
  return onRequestGet({
    env: androidApkUrl === undefined ? {} : { ANDROID_APK_URL: androidApkUrl }
  })
}

describe('GET /download/android', () => {
  test('responde 503 quando a URL do APK não foi configurada', async () => {
    const response = await requestDownload()

    expect(response.status).toBe(503)
    await expect(response.text()).resolves.toBe('Download temporariamente indisponível.')
  })

  test('responde 503 quando a configuração não é uma URL', async () => {
    const response = await requestDownload('arquivo-aplicativo.apk')

    expect(response.status).toBe(503)
  })

  test('responde 503 quando a URL não usa HTTPS', async () => {
    const response = await requestDownload('http://downloads.example.test/chargegrid.apk')

    expect(response.status).toBe(503)
  })

  test('redireciona sem cache para o APK HTTPS configurado', async () => {
    const apkUrl = 'https://downloads.example.test/releases/chargegrid.apk'
    const response = await requestDownload(apkUrl)

    expect(response.status).toBe(302)
    expect(response.headers.get('location')).toBe(apkUrl)
    expect(response.headers.get('cache-control')).toBe('no-store')
  })
})
