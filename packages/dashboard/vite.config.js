import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

// Endereço da API vindo da fonte única do projeto (config/dominios.json).
//
// Entra como fallback de compilação, não como valor fixo: VITE_API_URL continua
// tendo precedência, que é como o desenvolvimento local e qualquer outro
// ambiente apontam para outro lugar sem editar arquivo versionado.
// Tolera o arquivo ausente, como o backend faz: quem empacotar
// packages/dashboard sem a raiz do repositorio merece um aviso, nao um ENOENT
// sem contexto antes de o Vite imprimir qualquer coisa.
function enderecoDaApi() {
  try {
    const d = JSON.parse(
      readFileSync(fileURLToPath(new URL('../../config/dominios.json', import.meta.url)), 'utf-8')
    )
    return `${d.protocolo}://${d.api}`
  } catch {
    console.warn(
      '[vite] config/dominios.json não encontrado — defina VITE_API_URL ou o build sairá sem endereço de API.'
    )
    return ''
  }
}
const API_PADRAO = enderecoDaApi()

// Base relativa para o build também funcionar abrindo o index.html direto
export default defineConfig({
  base: './',
  // O .env vive na raiz do workspace, não neste pacote: é um só para o painel e
  // o app do motorista. Sem isto o Vite procuraria em packages/dashboard e as
  // VITE_* ficariam indefinidas em silêncio.
  envDir: fileURLToPath(new URL('../..', import.meta.url)),
  define: {
    __API_PADRAO__: JSON.stringify(API_PADRAO)
  },
  plugins: [react()],
  server: {
    port: 5173,
    open: true
  }
})
