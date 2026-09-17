/**
 * Qual endereço de API vai para dentro do pacote.
 *
 * Mora fora do `vite.config.js` para o `verify:dashboard` alcançar. O teste
 * de mutação mostrou por que: desligando o ramo de staging, o
 * `build:staging` passou a assar o endereço de PRODUÇÃO e nenhum teste
 * acusou — a decisão que mais importa nesta configuração era a única sem
 * guarda. Importar o `vite.config.js` de dentro do verify não serve: ele
 * arrasta o plugin do React para o Node.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

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
export function enderecoDaApi(desenvolvimento, modo) {
  try {
    const d = JSON.parse(
      readFileSync(fileURLToPath(new URL('../../../config/domains.json', import.meta.url)), 'utf-8')
    )
    if (desenvolvimento) {
      return d.desenvolvimento?.api || 'http://localhost:8000'
    }
    // `vite build --mode staging` assa o endereço de staging no pacote.
    //
    // O endereço vai para dentro do bundle e não sai mais: trocá-lo depois exige
    // rebuild. Sem este ramo, um build feito a partir da branch `staging` sairia
    // apontando para PRODUÇÃO — e a tela abriria, carregaria, e mostraria os
    // dados do ambiente errado sem nada indicando isso.
    if (modo === 'staging' && d.staging?.api) {
      return `${d.protocolo}://${d.staging.api}`
    }
    return `${d.protocolo}://${d.api}`
  } catch {
    console.warn(
      '[vite] config/domains.json não encontrado — defina VITE_API_URL ou o build sairá sem endereço de API.'
    )
    return desenvolvimento ? 'http://localhost:8000' : ''
  }
}
