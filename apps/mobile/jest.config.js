/**
 * Runner de renderizacao do app.
 *
 * `preset: 'jest-expo'` traz o transform de RN, o mapeamento de assets e os
 * mocks dos modulos nativos - sem ele, o primeiro `import` de `react-native`
 * quebra em Node.
 */
module.exports = {
  preset: 'jest-expo',
  testMatch: ['<rootDir>/tests/**/*.test.tsx']
}
