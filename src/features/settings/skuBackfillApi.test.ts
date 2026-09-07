import { afterEach, describe, expect, it, vi } from 'vitest'
import { previewSkuBackfill, startSkuBackfill } from './skuBackfillApi'

describe('skuBackfillApi', () => {
  afterEach(() => vi.restoreAllMocks())

  it('previews one SKU and optional start date without starting a run', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        sourceSku: 'SKU-A',
        rangeStart: '2026-01-01',
        rangeEnd: '2026-09-04',
        counts: { candidate: 1 },
        dates: [],
      }), { status: 200 }),
    )

    await previewSkuBackfill('SKU-A', '2026-01-01')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/sku-backfills/preview'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          source_sku: 'SKU-A',
          range_start: '2026-01-01',
        }),
      }),
    )
  })

  it('requires explicit confirmation when starting the backfill', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ runId: 10 }), { status: 202 }),
    )

    await startSkuBackfill('SKU-A', null)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/sku-backfills'),
      expect.objectContaining({
        body: JSON.stringify({
          source_sku: 'SKU-A',
          range_start: null,
          confirmed: true,
        }),
      }),
    )
  })
})
