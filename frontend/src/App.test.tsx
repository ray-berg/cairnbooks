import { describe, it, expect } from 'vitest'

/**
 * Smoke test — no DOM rendering needed; just confirm the module loads
 * and the default export is a function (React component).
 */
describe('App smoke test', () => {
  it('App component is a function', async () => {
    const mod = await import('./App')
    expect(typeof mod.default).toBe('function')
  })
})
