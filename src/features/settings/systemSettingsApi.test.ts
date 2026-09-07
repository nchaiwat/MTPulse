import { afterEach, describe, expect, it, vi } from 'vitest'
import { checkTechnicalHealth } from './systemSettingsApi'

describe('checkTechnicalHealth', () => {
  afterEach(() => vi.restoreAllMocks())

  it('requests a fresh health check without changing settings', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        status: 'sent',
        message: 'sent',
        checkedAt: '2026-09-07T09:30:00+07:00',
        overallStatus: 'healthy',
        metrics: [],
      }), { status: 200 }),
    )

    const result = await checkTechnicalHealth()

    expect(result.overallStatus).toBe('healthy')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/technical-notifications/check'),
      { method: 'POST' },
    )
  })
})
