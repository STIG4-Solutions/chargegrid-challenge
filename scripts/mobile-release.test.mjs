import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  compareVersions,
  createReleaseMetadata,
  parseAaptBadging,
  parseEasBuild,
  readAppVersion
} from './mobile-release.mjs'

test('lê uma versão semântica do app.json', () => {
  assert.equal(readAppVersion({ expo: { version: '0.1.1' } }), '0.1.1')
  assert.throws(() => readAppVersion({ expo: { version: 'v0.1.1' } }), /formato X.Y.Z/)
})

test('compara versões semânticas numéricas', () => {
  assert.equal(compareVersions('0.1.1', '0.1.0'), 1)
  assert.equal(compareVersions('0.2.0', '0.10.0'), -1)
  assert.equal(compareVersions('1.0.0', '1.0.0'), 0)
})

test('extrai o APK de uma resposta concluída do EAS', () => {
  const result = parseEasBuild([
    {
      id: 'build-123',
      platform: 'ANDROID',
      status: 'FINISHED',
      artifacts: { buildUrl: 'https://expo.example/chargegrid.apk' }
    }
  ])

  assert.deepEqual(result, {
    id: 'build-123',
    artifactUrl: 'https://expo.example/chargegrid.apk'
  })
})

test('rejeita build EAS incompleto', () => {
  assert.throws(
    () => parseEasBuild({ id: 'build-123', status: 'ERRORED', artifacts: {} }),
    /status ERRORED/
  )
})

test('extrai package e versionName do aapt', () => {
  const output =
    "package: name='br.com.chargegrid.app' versionCode='7' versionName='0.1.1' compileSdkVersion='36'\n"

  assert.deepEqual(parseAaptBadging(output), {
    packageName: 'br.com.chargegrid.app',
    versionName: '0.1.1'
  })
})

test('gera manifesto, checksum e caminho imutável', () => {
  const release = createReleaseMetadata({
    version: '0.1.1',
    environment: 'production',
    packageName: 'br.com.chargegrid.app',
    expectedPackage: 'br.com.chargegrid.app',
    apk: Buffer.from('apk-test'),
    gitCommit: '0123456789abcdef0123456789abcdef01234567',
    easBuildId: 'build-123',
    baseUrl: 'https://downloads.stig4.com/',
    publishedAt: '2026-09-23T12:00:00.000Z'
  })

  assert.equal(release.archivePrefix, 'releases/0.1.1/0123456')
  assert.equal(
    release.manifest.archiveUrl,
    'https://downloads.stig4.com/releases/0.1.1/0123456/chargegrid.apk'
  )
  assert.equal(release.manifest.downloadUrl, 'https://downloads.stig4.com/latest/chargegrid.apk')
  assert.match(release.checksum, /^[0-9a-f]{64}  chargegrid\.apk\n$/)
})

test('rejeita APK do package errado', () => {
  assert.throws(
    () =>
      createReleaseMetadata({
        version: '0.1.1',
        environment: 'production',
        packageName: 'br.com.chargegrid.app.staging',
        expectedPackage: 'br.com.chargegrid.app',
        apk: Buffer.from('apk-test'),
        gitCommit: '0123456789abcdef0123456789abcdef01234567',
        easBuildId: 'build-123',
        baseUrl: 'https://downloads.stig4.com'
      }),
    /esperado br\.com\.chargegrid\.app/
  )
})
