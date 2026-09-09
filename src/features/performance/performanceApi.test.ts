import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadPerformanceReport, fetchPerformance, fetchPerformanceItemDetail, fetchSkuOptions, updateSkuAnalysisFlag } from './performanceApi'

describe('fetchPerformance', () => {
  afterEach(() => vi.restoreAllMocks())

  it('serializes non-overlapping ranges and requests turnover in Inventory mode', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '2026-06-01',
      dateTo: '2026-09-08',
      dateRanges: [
        { from: '2026-06-01', to: '2026-06-30' },
        { from: '2026-08-01', to: '2026-09-08' },
      ],
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 1,
      dimension: 'day',
      mode: 'inventory',
      branchMonth: 'latest',
      branchPeriod: 'month',
    })

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.searchParams.getAll('date_range')).toEqual([
      '2026-06-01,2026-06-30',
      '2026-08-01,2026-09-08',
    ])
    expect(url.searchParams.has('date_from')).toBe(false)
    expect(url.searchParams.has('date_to')).toBe(false)
    expect(url.searchParams.get('include_turnover')).toBe('true')
  })

  it('always refreshes SKU options instead of reusing a cached response', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    )

    await fetchSkuOptions()

    expect(fetchMock).toHaveBeenCalledWith('/api/performance/sku-options?mt_code=TWD', {
      signal: undefined,
      cache: 'no-store',
    })
  })
  it('lets the backend apply the MT page-size setting', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '',
      dateTo: '',
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 3,
      dimension: 'branch',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'month',
    })

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.searchParams.get('page')).toBe('3')
    expect(url.searchParams.has('page_size')).toBe(false)
    expect(url.searchParams.get('grain')).toBe('branch_month')
    expect(url.searchParams.get('period_month')).toBe('latest')
    expect(url.searchParams.get('sales_basis')).toBe('net')
  })

  it('passes the selected Gross Sale Out basis to matrix, detail, and export', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    )
    const query = {
      dateFrom: '2026-07-01',
      dateTo: '2026-07-31',
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 1,
      dimension: 'branch' as const,
      mode: 'sales' as const,
      salesBasis: 'gross' as const,
      branchMonth: 'latest',
      branchPeriod: 'day' as const,
    }

    await fetchPerformance(query)
    await fetchPerformanceItemDetail(query, 'SKU-A')
    fetchMock.mockResolvedValueOnce(new Response(new Blob(['xlsx']), { status: 200 }))
    await downloadPerformanceReport(query, 'amount', true)

    for (const call of fetchMock.mock.calls) {
      const url = new URL(String(call[0]), 'http://localhost')
      expect(url.searchParams.get('sales_basis')).toBe('gross')
    }
  })

  it.each(['all', 'flagged', 'sho', 'pro', 'both', 'none'] as const)(
    'serializes the %s Sho/Pro filter for matrix and export',
    async (skuFlag) => {
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
        new Response(JSON.stringify({ items: [] }), { status: 200 }),
      )
      const query = {
        dateFrom: '',
        dateTo: '',
        branchIds: [],
        monthFrom: '',
        monthTo: '',
        search: '',
        page: 1,
        dimension: 'month' as const,
        mode: 'sales' as const,
        skuFlag,
        branchMonth: 'latest',
        branchPeriod: 'month' as const,
      }

      await fetchPerformance(query)
      fetchMock.mockResolvedValueOnce(new Response(new Blob(['xlsx']), { status: 200 }))
      await downloadPerformanceReport(query, 'amount', true)

      for (const call of fetchMock.mock.calls) {
        const url = new URL(String(call[0]), 'http://localhost')
        expect(url.searchParams.get('sku_flag')).toBe(skuFlag)
      }
    },
  )

  it('updates one Sho/Pro flag without sending the other flag', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        mtCode: 'TWD',
        sku: 'SKU/A',
        isSho: true,
        isPro: false,
        updatedAt: '2026-09-09T07:00:00+07:00',
      }), { status: 200 }),
    )

    const result = await updateSkuAnalysisFlag('TWD', 'SKU/A', 'sho', true)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/performance/sku-flags/TWD/SKU%2FA',
      expect.objectContaining({
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flag: 'sho', enabled: true }),
      }),
    )
    expect(result.isSho).toBe(true)
    expect(result.isPro).toBe(false)
  })

  it('requests all available history aggregated by month', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '',
      dateTo: '',
      branchIds: [],
      monthFrom: '2025-01',
      monthTo: '2026-08',
      search: '',
      page: 1,
      dimension: 'month',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'month',
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('grain=month')
    expect(url).toContain('date_from=2025-01-01')
    expect(url).toContain('date_to=2026-08-31')
  })

  it('marks an Inventory Month request for snapshot semantics', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '',
      dateTo: '',
      branchIds: [],
      monthFrom: '2026-07',
      monthTo: '2026-08',
      search: '',
      page: 1,
      dimension: 'month',
      mode: 'inventory',
      branchMonth: 'latest',
      branchPeriod: 'month',
      mtCode: 'HP',
    })

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.searchParams.get('grain')).toBe('month')
    expect(url.searchParams.get('report_mode')).toBe('inventory')
    expect(url.searchParams.get('include_turnover')).toBe('true')
  })

  it('requests date totals aggregated by the backend', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '',
      dateTo: '',
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 1,
      dimension: 'day',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'month',
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('grain=day_total')
    expect(url).not.toContain('date_from')
    expect(url).not.toContain('date_to')
  })

  it('requests a date range and selected branches while keeping Branch as the matrix dimension', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateFrom: '2026-08-05',
      dateTo: '2026-08-13',
      branchIds: ['60016', '60923'],
      skuIds: ['60406627', 'ABCDE'],
      search: '',
      monthFrom: '',
      monthTo: '',
      page: 1,
      dimension: 'branch',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'day',
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('grain=branch_range')
    expect(url).toContain('date_from=2026-08-05')
    expect(url).toContain('date_to=2026-08-13')
    expect(url).toContain('branch_ids=60016%2C60923')
    expect(url).toContain('sku_ids=60406627%2CABCDE')
    expect(url).not.toContain('period_month')
  })

  it('keeps raw daily points available only when an item detail is opened', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    )

    await fetchPerformanceItemDetail({
      dateFrom: '2026-08-05',
      dateTo: '2026-08-13',
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 1,
      dimension: 'branch',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'day',
    }, '60406627')

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.searchParams.get('grain')).toBe('day')
    expect(url.searchParams.get('sku_ids')).toBe('60406627')
    expect(url.searchParams.get('page')).toBe('1')
  })

  it('requests only the latest inventory snapshot while keeping detail history raw', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    )
    const query = {
      dateFrom: '',
      dateTo: '',
      branchIds: [],
      monthFrom: '',
      monthTo: '',
      search: '',
      page: 1,
      dimension: 'branch' as const,
      mode: 'inventory' as const,
      branchMonth: 'latest',
      branchPeriod: 'month' as const,
    }

    await fetchPerformance(query)
    await fetchPerformanceItemDetail(query, '60406627')

    const matrixUrl = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    const detailUrl = new URL(String(fetchMock.mock.calls[1][0]), 'http://localhost')
    expect(matrixUrl.searchParams.get('grain')).toBe('day')
    expect(matrixUrl.searchParams.get('latest_only')).toBe('true')
    expect(detailUrl.searchParams.get('grain')).toBe('day')
    expect(detailUrl.searchParams.has('latest_only')).toBe(false)
  })

  it('downloads every matching row without pagination parameters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Blob(['xlsx']), {
        status: 200,
        headers: { 'Content-Disposition': "attachment; filename*=UTF-8''TWD_Report.xlsx" },
      }),
    )

    const result = await downloadPerformanceReport({
      dateFrom: '2026-08-17',
      dateTo: '2026-08-17',
      branchIds: ['60920'],
      skuIds: ['60406627', 'ABCDE'],
      search: '',
      page: 5,
      monthFrom: '',
      monthTo: '',
      dimension: 'branch',
      mode: 'sales',
      branchMonth: 'latest',
      branchPeriod: 'day',
    }, 'amount', false)

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.pathname).toBe('/api/performance/export')
    expect(url.searchParams.get('date_from')).toBe('2026-08-17')
    expect(url.searchParams.has('mapping_status')).toBe(false)
    expect(url.searchParams.has('search')).toBe(false)
    expect(url.searchParams.get('sku_ids')).toBe('60406627,ABCDE')
    expect(url.searchParams.get('metric')).toBe('amount')
    expect(url.searchParams.get('show_descriptions')).toBe('false')
    expect(url.searchParams.has('page')).toBe(false)
    expect(url.searchParams.get('branch_ids')).toBe('60920')
    expect(url.searchParams.has('page_size')).toBe(false)
    expect(result.filename).toBe('TWD_Report.xlsx')
  })
})
