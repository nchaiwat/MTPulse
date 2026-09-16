import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  confirmDhPriceMaster,
  downloadDhPriceTemplate,
  fetchDhPrices,
  previewDhPriceMaster,
} from './dhPriceMasterApi'

const preview = {
  row_count: 3,
  candidate_count: 3,
  inserted: 1,
  updated: 1,
  unchanged: 1,
  source_checksum_sha256: 'a'.repeat(64),
  preview_fingerprint: 'b'.repeat(64),
  errors: [],
}

describe('DH Price Master API', () => {
  afterEach(() => vi.restoreAllMocks())

  it('downloads the workbook template with the server filename', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Blob(['xlsx']), {
        status: 200,
        headers: {
          'Content-Disposition': "attachment; filename*=UTF-8''DH_Price_Master_Template.xlsx",
        },
      }),
    )

    const result = await downloadDhPriceTemplate()

    expect(fetchMock).toHaveBeenCalledWith('/api/dh-prices/template')
    expect(result.filename).toBe('DH_Price_Master_Template.xlsx')
  })

  it('previews and confirms the exact selected workbook', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(preview), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...preview,
        confirmed_by: 'data-operator@test',
        confirmed_at: '2026-09-16T10:15:00+07:00',
      }), { status: 200 }))
    const file = new File(['price'], 'dh-prices.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })

    await previewDhPriceMaster(file)
    await confirmDhPriceMaster(file, preview.preview_fingerprint)

    const previewRequest = fetchMock.mock.calls[0][1]
    const confirmRequest = fetchMock.mock.calls[1][1]
    expect(fetchMock.mock.calls[0][0]).toBe('/api/dh-prices/preview')
    expect(previewRequest?.method).toBe('POST')
    expect((previewRequest?.body as FormData).get('file')).toBe(file)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/dh-prices/confirm')
    expect((confirmRequest?.body as FormData).get('file')).toBe(file)
    expect((confirmRequest?.body as FormData).get('preview_fingerprint')).toBe(preview.preview_fingerprint)
  })

  it('lists prices with search, status and pagination', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 2, page_size: 25 }), { status: 200 }),
    )

    await fetchDhPrices({ query: '00123', status: 'current', page: 2, pageSize: 25 })

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.pathname).toBe('/api/dh-prices')
    expect(url.searchParams.get('q')).toBe('00123')
    expect(url.searchParams.get('status')).toBe('current')
    expect(url.searchParams.get('page')).toBe('2')
    expect(url.searchParams.get('page_size')).toBe('25')
  })
})
