import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Cada teste monta do zero. Sem isto, dois testes que renderizam o mesmo
// componente disputam o mesmo DOM e `getByText` acha dois nos - uma falha que
// aponta para o teste errado.
afterEach(cleanup)
