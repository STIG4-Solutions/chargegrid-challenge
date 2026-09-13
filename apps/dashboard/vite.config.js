import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { enderecoDaApi } from './scripts/dominios.mjs'

// Base relativa para o build também funcionar abrindo o index.html direto
export default defineConfig(({ command, mode }) => ({
  base: './',
  // Cada aplicacao carrega seu proprio arquivo de ambiente.
  envDir: fileURLToPath(new URL('.', import.meta.url)),
  define: {
    // `serve` é o dev server; `build` é o pacote que vai para produção.
    __API_PADRAO__: JSON.stringify(enderecoDaApi(command === 'serve', mode))
  },
  plugins: [react()],
  server: {
    port: 5173,
    open: true
  }
}))
