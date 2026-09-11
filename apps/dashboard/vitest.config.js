import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

/**
 * Configuração separada do `vite.config.js`, de propósito.
 *
 * Aquele arquivo lê `config/domains.json` e decide o endereço da API pelo
 * comando (`serve` contra `build`). Sob teste não existe nenhum dos dois, e
 * herdar aquela lógica faria a suíte depender de um arquivo da raiz do
 * repositório para responder perguntas que não têm nada a ver com rede.
 *
 * `__API_PADRAO__` continua precisando existir: o SDK o lê no import. Aqui ele
 * é uma string inerte — nenhum teste de renderização faz requisição.
 */
export default defineConfig({
  plugins: [react()],
  define: {
    __API_PADRAO__: JSON.stringify('http://localhost:8000')
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [fileURLToPath(new URL('./tests/setup.js', import.meta.url))],
    include: ['tests/**/*.test.jsx']
  }
})
