import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchPerformance } from './performanceApi'

describe('fetchPerformance', () => {
  afterEach(() => vi.restoreAllMocks())

  it('sends the cell-budget page size to the backend', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateRange: 'all',
      branchId: 'all',
      mappingStatus: 'all',
      hideUnmapped: true,
      search: '',
      page: 3,
      pageSize: 25,
      dimension: 'branch',
      mode: 'sales',
      branchMonth: 'latest',
    })

    expect(String(fetchMock.mock.calls[0][0])).toContain('page=3&page_size=25')
    expect(String(fetchMock.mock.calls[0][0])).toContain('hide_unmapped=true')
    expect(String(fetchMock.mock.calls[0][0])).toContain('grain=branch_month')
    expect(String(fetchMock.mock.calls[0][0])).toContain('period_month=latest')
  })

  it('requests all available history aggregated by month', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateRange: 'all',
      branchId: 'all',
      mappingStatus: 'all',
      hideUnmapped: false,
      search: '',
      page: 1,
      pageSize: 100,
      dimension: 'month',
      mode: 'sales',
      branchMonth: 'latest',
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('grain=month')
    expect(url).not.toContain('date_from')
    expect(url).not.toContain('date_to')
  })

  it('requests date totals aggregated by the backend', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await fetchPerformance({
      dateRange: 'all',
      branchId: 'all',
      mappingStatus: 'all',
      hideUnmapped: false,
      search: '',
      page: 1,
      pageSize: 100,
      dimension: 'day',
      mode: 'sales',
      branchMonth: 'latest',
    })

    expect(String(fetchMock.mock.calls[0][0])).toContain('grain=day_total')
  })
})
