import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadPerformanceReport, fetchPerformance, fetchPerformanceItemDetail, fetchSkuOptions } from './performanceApi'

describe('fetchPerformance', () => {
  afterEach(() => vi.restoreAllMocks())

  it('always refreshes SKU options instead of reusing a cached response', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    )

    await fetchSkuOptions()

    expect(fetchMock).toHaveBeenCalledWith('/api/performance/sku-options', {
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
