import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadDataCoverage } from './twdSettingsApi'

describe('downloadDataCoverage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('downloads the selected year for one Modern Trade', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Blob(['xlsx']), {
        status: 200,
        headers: {
          'Content-Disposition': "attachment; filename*=UTF-8''TWD_Data_Coverage_2025.xlsx",
        },
      }),
    )

    const result = await downloadDataCoverage('TWD', 2025)
    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')

    expect(url.pathname).toBe('/api/data-coverage/export')
    expect(url.searchParams.get('mt_code')).toBe('TWD')
    expect(url.searchParams.get('year')).toBe('2025')
    expect(result.filename).toBe('TWD_Data_Coverage_2025.xlsx')
  })
})
