import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// Base relativa para o build também funcionar abrindo o index.html direto
export default defineConfig({
  base: './',
  // O .env vive na raiz do workspace, não neste pacote: é um só para o painel e
  // o app do motorista. Sem isto o Vite procuraria em packages/dashboard e as
  // VITE_* ficariam indefinidas em silêncio.
  envDir: fileURLToPath(new URL('../..', import.meta.url)),
  plugins: [react()],
  server: {
    port: 5173,
    open: true
  }
})
