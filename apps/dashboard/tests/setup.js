import * as matchers from '@testing-library/jest-dom/matchers'
import { cleanup } from '@testing-library/react'
import { afterEach, expect } from 'vitest'

// `expect.extend` em vez de `import '@testing-library/jest-dom/vitest'`.
//
// Aquele atalho faz o próprio jest-dom importar `vitest`, e ele é hoisted para
// o node_modules da RAIZ enquanto o vitest fica no do workspace — a resolução
// falha com "Cannot find package 'vitest'". Aqui quem importa vitest é este
// arquivo, que está dentro do workspace, então o layout do node_modules deixa
// de importar.
expect.extend(matchers)

// Cada teste monta do zero. Sem isto, dois testes que renderizam o mesmo
// componente disputam o mesmo DOM e `getByText` acha dois nós - uma falha que
// aponta para o teste errado.
afterEach(cleanup)
