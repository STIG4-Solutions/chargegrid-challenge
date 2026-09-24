import { createHash } from 'node:crypto'
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/

export function readAppVersion(appJson) {
  const version = appJson?.expo?.version

  if (typeof version !== 'string' || !VERSION_PATTERN.test(version)) {
    throw new Error('apps/mobile/app.json deve conter expo.version no formato X.Y.Z')
  }

  return version
}

export function compareVersions(left, right) {
  const parse = (value) => {
    if (!VERSION_PATTERN.test(value)) throw new Error(`Versão inválida: ${value}`)
    return value.split('.').map(Number)
  }

  const leftParts = parse(left)
  const rightParts = parse(right)

  for (let index = 0; index < 3; index += 1) {
    if (leftParts[index] !== rightParts[index]) {
      return leftParts[index] > rightParts[index] ? 1 : -1
    }
  }

  return 0
}

export function parseEasBuild(payload) {
  const builds = Array.isArray(payload) ? payload : [payload]
  const build = builds.find((candidate) => candidate?.platform === 'ANDROID') ?? builds[0]

  if (!build?.id) throw new Error('A resposta do EAS não contém o identificador do build')
  if (build.status !== 'FINISHED') {
    throw new Error(`O build EAS ${build.id} terminou com status ${build.status ?? 'desconhecido'}`)
  }

  const artifactUrl = build.artifacts?.buildUrl ?? build.artifacts?.applicationArchiveUrl
  if (!artifactUrl || !artifactUrl.startsWith('https://')) {
    throw new Error(`O build EAS ${build.id} não contém uma URL HTTPS para o APK`)
  }

  return { id: build.id, artifactUrl }
}

export function parseAaptBadging(output) {
  const packageLine = output.split(/\r?\n/).find((line) => line.startsWith('package:'))

  if (!packageLine) throw new Error('O aapt não encontrou os metadados do pacote Android')

  const packageName = packageLine.match(/\bname='([^']+)'/)?.[1]
  const versionName = packageLine.match(/\bversionName='([^']+)'/)?.[1]

  if (!packageName || !versionName) {
    throw new Error('O aapt não informou package name e versionName do APK')
  }

  return { packageName, versionName }
}

export function createReleaseMetadata({
  version,
  environment,
  packageName,
  expectedPackage,
  apk,
  gitCommit,
  easBuildId,
  baseUrl,
  publishedAt = new Date().toISOString()
}) {
  if (!['staging', 'production'].includes(environment)) {
    throw new Error(`Ambiente inválido: ${environment}`)
  }
  if (packageName !== expectedPackage) {
    throw new Error(`APK usa ${packageName}; esperado ${expectedPackage}`)
  }
  if (!/^[0-9a-f]{40}$/i.test(gitCommit)) {
    throw new Error('O commit do release deve ser um SHA Git completo')
  }

  const normalizedBaseUrl = baseUrl.replace(/\/+$/, '')
  if (!normalizedBaseUrl.startsWith('https://')) {
    throw new Error('R2_BASE_URL deve ser uma URL HTTPS')
  }

  const shortCommit = gitCommit.slice(0, 7)
  const archivePrefix = `releases/${version}/${shortCommit}`
  const sha256 = createHash('sha256').update(apk).digest('hex')

  return {
    archivePrefix,
    checksum: `${sha256}  chargegrid.apk\n`,
    manifest: {
      schemaVersion: 1,
      app: 'ChargeGrid',
      version,
      environment,
      packageName,
      gitCommit,
      easBuildId,
      sha256,
      sizeBytes: apk.byteLength,
      archiveUrl: `${normalizedBaseUrl}/${archivePrefix}/chargegrid.apk`,
      downloadUrl: `${normalizedBaseUrl}/latest/chargegrid.apk`,
      publishedAt
    }
  }
}

function parseOptions(args) {
  const options = {}

  for (let index = 0; index < args.length; index += 2) {
    const name = args[index]
    const value = args[index + 1]
    if (!name?.startsWith('--') || value === undefined) {
      throw new Error(`Argumentos inválidos perto de ${name ?? '(fim)'}`)
    }
    options[name.slice(2)] = value
  }

  return options
}

function required(options, name) {
  const value = options[name]
  if (!value) throw new Error(`Argumento obrigatório ausente: --${name}`)
  return value
}

function writeGithubOutput(file, values) {
  if (!file) return
  const lines = Object.entries(values)
    .map(([key, value]) => `${key}=${value}\n`)
    .join('')
  appendFileSync(file, lines)
}

function loadJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'))
}

function runVersion(options) {
  const version = readAppVersion(loadJson(required(options, 'app-json')))
  console.log(version)
  writeGithubOutput(options['github-output'], { version })
}

function runEasBuild(options) {
  const build = parseEasBuild(loadJson(required(options, 'input')))
  console.log(`Build EAS ${build.id} concluído`)
  writeGithubOutput(options['github-output'], {
    eas_build_id: build.id,
    artifact_url: build.artifactUrl
  })
}

function runAssertNewer(options) {
  const candidate = required(options, 'candidate')
  const current = loadJson(required(options, 'current-manifest')).version

  if (compareVersions(candidate, current) <= 0) {
    throw new Error(`Produção já está em ${current}; a nova versão ${candidate} precisa ser maior`)
  }

  console.log(`${candidate} é posterior à versão publicada ${current}`)
}

function runPrepare(options) {
  const version = readAppVersion(loadJson(required(options, 'app-json')))
  const easBuild = parseEasBuild(loadJson(required(options, 'eas-json')))
  const apkMetadata = parseAaptBadging(readFileSync(required(options, 'aapt-output'), 'utf8'))

  if (apkMetadata.versionName !== version) {
    throw new Error(`APK usa a versão ${apkMetadata.versionName}; app.json usa ${version}`)
  }

  const outputDirectory = required(options, 'output-dir')
  mkdirSync(outputDirectory, { recursive: true })

  const release = createReleaseMetadata({
    version,
    environment: required(options, 'environment'),
    packageName: apkMetadata.packageName,
    expectedPackage: required(options, 'expected-package'),
    apk: readFileSync(required(options, 'apk')),
    gitCommit: required(options, 'git-commit'),
    easBuildId: easBuild.id,
    baseUrl: required(options, 'base-url')
  })

  writeFileSync(
    path.join(outputDirectory, 'release.json'),
    `${JSON.stringify(release.manifest, null, 2)}\n`
  )
  writeFileSync(path.join(outputDirectory, 'chargegrid.apk.sha256'), release.checksum)

  console.log(`APK ${version} validado: ${apkMetadata.packageName}`)
  writeGithubOutput(options['github-output'], {
    version,
    archive_prefix: release.archivePrefix,
    archive_url: release.manifest.archiveUrl,
    latest_url: release.manifest.downloadUrl,
    sha256: release.manifest.sha256
  })
}

export function main(argv) {
  const [command, ...args] = argv
  const options = parseOptions(args)

  if (command === 'version') return runVersion(options)
  if (command === 'eas-build') return runEasBuild(options)
  if (command === 'assert-newer') return runAssertNewer(options)
  if (command === 'prepare') return runPrepare(options)

  throw new Error(`Comando desconhecido: ${command ?? '(ausente)'}`)
}

const isDirectExecution =
  process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])

if (isDirectExecution) {
  try {
    main(process.argv.slice(2))
  } catch (error) {
    console.error(process.env.GITHUB_ACTIONS ? `::error::${error.message}` : error.message)
    process.exitCode = 1
  }
}
