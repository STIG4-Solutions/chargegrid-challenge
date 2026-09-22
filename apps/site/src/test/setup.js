import * as matchers from '@testing-library/jest-dom/matchers'
import { expect } from 'vitest'

// O jest-dom fica hoisted na raiz, enquanto o Vitest pertence ao workspace.
// Estender o expect daqui preserva a resolução de módulos usada no monorepo.
expect.extend(matchers)
