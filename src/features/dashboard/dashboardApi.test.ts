import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadDashboard } from './dashboardApi'

describe('downloadDashboard', () => {
  afterEach(() => vi.restoreAllMocks())

  it('downloads the active MT, year, period, and metric', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Blob(['xlsx']), {
        status: 200,
        headers: {
          'Content-Disposition': "attachment; filename*=UTF-8''TWD_Dashboard_2026_H1_Qty.xlsx",
        },
      }),
    )

    const result = await downloadDashboard('TWD', 'h1', 'qty', 2026)
    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')

    expect(url.pathname).toBe('/api/dashboards/twd/export')
    expect(url.searchParams.get('year')).toBe('2026')
    expect(url.searchParams.get('period')).toBe('h1')
    expect(url.searchParams.get('metric')).toBe('qty')
    expect(result.filename).toBe('TWD_Dashboard_2026_H1_Qty.xlsx')
  })
})
