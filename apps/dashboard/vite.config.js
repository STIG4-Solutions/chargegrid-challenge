import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

// Endereço da API vindo da fonte única do projeto (config/domains.json).
//
// Entra como fallback de compilação, não como valor fixo: VITE_API_URL continua
// tendo precedência, que é como qualquer outro ambiente aponta para outro lugar
// sem editar arquivo versionado.
//
// SERVIDOR DE DESENVOLVIMENTO USA O BLOCO `desenvolvimento`, e o build usa o de
// produção. O arquivo sempre teve `desenvolvimento.api`, e o backend já o
// honrava - `config.py` lê `desenvolvimento.dashboard` para liberar o CORS.
// Só este lado não lia, e o resultado era um `npm run dev` que subia apontando
// para o domínio de produção: sem DNS configurado, o painel abria e não
// carregava nada, com um erro de rede que não explica a causa.
//
// Tolera o arquivo ausente, como o backend faz: quem empacotar apps/dashboard
// sem a raiz do repositório merece um aviso, não um ENOENT sem contexto antes
// de o Vite imprimir qualquer coisa.
function enderecoDaApi(desenvolvimento) {
  try {
    const d = JSON.parse(
      readFileSync(fileURLToPath(new URL('../../config/domains.json', import.meta.url)), 'utf-8')
    )
    if (desenvolvimento) {
      return d.desenvolvimento?.api || 'http://localhost:8000'
    }
    return `${d.protocolo}://${d.api}`
  } catch {
    console.warn(
      '[vite] config/domains.json não encontrado — defina VITE_API_URL ou o build sairá sem endereço de API.'
    )
    return desenvolvimento ? 'http://localhost:8000' : ''
  }
}

// Base relativa para o build também funcionar abrindo o index.html direto
export default defineConfig(({ command }) => ({
  base: './',
  // Cada aplicacao carrega seu proprio arquivo de ambiente.
  envDir: fileURLToPath(new URL('.', import.meta.url)),
  define: {
    // `serve` é o dev server; `build` é o pacote que vai para produção.
    __API_PADRAO__: JSON.stringify(enderecoDaApi(command === 'serve'))
  },
  plugins: [react()],
  server: {
    port: 5173,
    open: true
  }
}))
