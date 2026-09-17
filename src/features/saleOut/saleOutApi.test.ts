import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchSaleOutReport } from './saleOutApi'

describe('fetchSaleOutReport', () => {
  afterEach(() => vi.restoreAllMocks())

  it('serializes years, basis, metric, cutoff, and repeated MT filters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ meta: {} }), { status: 200 }),
    )

    await fetchSaleOutReport({
      baseYear: 2025,
      comparisonYear: 2026,
      cutoff: '2026-08-03',
      salesBasis: 'gross',
      metric: 'amount',
      mtCodes: ['TWD', 'HP'],
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const url = String(fetchMock.mock.calls[0]?.[0])
    const params = new URL(url, 'http://localhost').searchParams
    expect(params.get('base_year')).toBe('2025')
    expect(params.get('comparison_year')).toBe('2026')
    expect(params.get('cutoff')).toBe('2026-08-03')
    expect(params.get('sales_basis')).toBe('gross')
    expect(params.get('metric')).toBe('amount')
    expect(params.getAll('mt_code')).toEqual(['TWD', 'HP'])
  })

  it('surfaces the backend detail when the request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Cut-off is outside the available period' }), { status: 422 }),
    )

    await expect(fetchSaleOutReport({
      baseYear: 2025,
      comparisonYear: 2026,
      salesBasis: 'gross',
      metric: 'amount',
    })).rejects.toThrow('Cut-off is outside the available period')
  })
})
