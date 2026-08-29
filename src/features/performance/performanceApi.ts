import type { BranchPeriod, Dimension, Metric, Mode, PerformanceItem, PerformanceResponse, SkuOption } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface PerformanceQuery {
  dateFrom: string
  dateTo: string
  branchIds: string[]
  skuIds?: string[]
  monthFrom: string
  monthTo: string
  search: string
  page: number
  dimension: Dimension
  mode: Mode
  branchMonth: string
  branchPeriod: BranchPeriod
  signal?: AbortSignal
}

async function apiError(response: Response, fallback: string) {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? fallback
  } catch {
    return fallback
  }
}
function monthEnd(month: string) {
  const [year, monthNumber] = month.split('-').map(Number)
  const lastDay = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate()
  return `${month}-${String(lastDay).padStart(2, '0')}`
}


function performanceQuery(queryInput: PerformanceQuery) {
  const grain = queryInput.dimension === 'month'
    ? 'month'
    : queryInput.dimension === 'branch' && queryInput.mode === 'sales'
      ? queryInput.branchPeriod === 'day' ? 'branch_range' : 'branch_month'
      : queryInput.dimension === 'day'
        ? 'day_total'
        : 'day'
  const query = new URLSearchParams({ grain })
  if (grain === 'branch_month') {
    query.set('period_month', queryInput.branchMonth)
  } else if (grain === 'month') {
    if (queryInput.monthFrom) query.set('date_from', `${queryInput.monthFrom}-01`)
    if (queryInput.monthTo) query.set('date_to', monthEnd(queryInput.monthTo))
  } else {
    if (queryInput.dateFrom) query.set('date_from', queryInput.dateFrom)
    if (queryInput.dateTo) query.set('date_to', queryInput.dateTo)
  }
  if (queryInput.branchIds.length > 0) {
    query.set('branch_ids', queryInput.branchIds.join(','))
  }
  if (queryInput.skuIds?.length) {
    query.set('sku_ids', queryInput.skuIds.join(','))
  }
  if (queryInput.search) query.set('search', queryInput.search)
  return { grain, query }
}

export async function fetchSkuOptions(signal?: AbortSignal): Promise<SkuOption[]> {
  const response = await fetch(`${apiBaseUrl}/api/performance/sku-options`, { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`SKU API ตอบกลับ ${response.status}`)
  const body = await response.json() as { items: SkuOption[] }
  return body.items
}
export async function fetchPerformance(queryInput: PerformanceQuery): Promise<PerformanceResponse> {
  const { query } = performanceQuery(queryInput)
  query.set('page', String(queryInput.page))
  const response = await fetch(`${apiBaseUrl}/api/performance?${query}`, { signal: queryInput.signal })
  if (!response.ok) throw new Error(`Performance API ตอบกลับ ${response.status}`)
  return response.json() as Promise<PerformanceResponse>
}

export async function fetchPerformanceItemDetail(
  queryInput: PerformanceQuery,
  sku: string,
  signal?: AbortSignal,
): Promise<PerformanceItem | null> {
  const { query } = performanceQuery({ ...queryInput, skuIds: [sku] })
  query.set('grain', 'day')
  query.set('page', '1')
  const response = await fetch(`${apiBaseUrl}/api/performance?${query}`, { signal })
  if (!response.ok) throw new Error(`Performance API ตอบกลับ ${response.status}`)
  const body = await response.json() as PerformanceResponse
  return body.items[0] ?? null
}

export async function downloadPerformanceReport(
  queryInput: PerformanceQuery,
  metric: Metric,
  showDescriptions: boolean,
): Promise<{ blob: Blob, filename: string }> {
  const { grain, query } = performanceQuery(queryInput)
  query.set('mode', queryInput.mode)
  query.set('metric', metric)
  query.set('show_descriptions', String(showDescriptions))
  const response = await fetch(`${apiBaseUrl}/api/performance/export?${query}`)
  if (!response.ok) throw new Error(await apiError(response, `Download API ตอบกลับ ${response.status}`))
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : `TWD_${queryInput.mode}_${metric}_${grain}.xlsx`,
  }
}
