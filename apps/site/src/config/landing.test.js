import { describe, expect, test } from 'vitest'
import { dashboardUrlForHostname } from './landing.js'

describe('endereco do painel na landing', () => {
  test.each(['stig4.com', 'www.stig4.com', 'chargegrid-site.pages.dev'])(
    'usa producao em %s',
    (hostname) => {
      expect(dashboardUrlForHostname(hostname)).toBe('https://dashboard.stig4.com')
    }
  )

  test.each([
    'staging.stig4.com',
    'staging.chargegrid-site.pages.dev',
    '42a7f10b.chargegrid-site.pages.dev'
  ])('usa staging em %s', (hostname) => {
    expect(dashboardUrlForHostname(hostname)).toBe('https://dashboard.staging.stig4.com')
  })

  test.each(['localhost', '127.0.0.1'])('usa desenvolvimento em %s', (hostname) => {
    expect(dashboardUrlForHostname(hostname)).toBe('http://localhost:5173')
  })
})
