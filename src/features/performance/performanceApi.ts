import type { BranchPeriod, DateRange, Dimension, Metric, Mode, ModernTradeCode, PerformanceItem, PerformanceResponse, SalesBasis, SkuAnalysisFlagName, SkuAnalysisFlagResponse, SkuFlagFilter, SkuOption } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface PerformanceQuery {
  dateFrom: string
  dateTo: string
  dateRanges?: DateRange[]
  branchIds: string[]
  skuIds?: string[]
  monthFrom: string
  monthTo: string
  search: string
  page: number
  dimension: Dimension
  mode: Mode
  salesBasis?: SalesBasis
  branchMonth: string
  branchPeriod: BranchPeriod
  signal?: AbortSignal
  mtCode?: ModernTradeCode
  skuFlag?: SkuFlagFilter
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


function performanceQuery(
  queryInput: PerformanceQuery,
  latestInventorySnapshot = true,
) {
  const grain = queryInput.dimension === 'month'
    ? 'month'
    : queryInput.dimension === 'branch' && queryInput.mode === 'sales'
      ? queryInput.branchPeriod === 'day' ? 'branch_range' : 'branch_month'
      : queryInput.dimension === 'day'
        ? 'day_total'
        : 'day'
  const query = new URLSearchParams({ grain })
  query.set('mt_code', queryInput.mtCode ?? 'TWD')
  query.set('report_mode', queryInput.mode)
  if (queryInput.skuFlag) query.set('sku_flag', queryInput.skuFlag)
  if (queryInput.mode === 'sales') {
    query.set('sales_basis', queryInput.salesBasis ?? 'net')
  }
  if (queryInput.mode === 'inventory' && (queryInput.mtCode ?? 'TWD') === 'TWD') {
    query.set('include_turnover', 'true')
  }
  if (latestInventorySnapshot && queryInput.mode === 'inventory' && queryInput.dimension === 'branch') {
    query.set('latest_only', 'true')
  }
  if (grain === 'branch_month') {
    query.set('period_month', queryInput.branchMonth)
  } else if (grain === 'month') {
    if (queryInput.monthFrom) query.set('date_from', `${queryInput.monthFrom}-01`)
    if (queryInput.monthTo) query.set('date_to', monthEnd(queryInput.monthTo))
  } else {
    if (queryInput.dateRanges?.length) {
      queryInput.dateRanges.forEach(({ from, to }) => query.append('date_range', `${from},${to}`))
    } else {
      if (queryInput.dateFrom) query.set('date_from', queryInput.dateFrom)
      if (queryInput.dateTo) query.set('date_to', queryInput.dateTo)
    }
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

export async function fetchSkuOptions(mtCode: ModernTradeCode = 'TWD', signal?: AbortSignal): Promise<SkuOption[]> {
  const response = await fetch(`${apiBaseUrl}/api/performance/sku-options?mt_code=${mtCode}`, { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`SKU API ตอบกลับ ${response.status}`)
  const body = await response.json() as { items: SkuOption[] }
  return body.items
}

export async function updateSkuAnalysisFlag(
  mtCode: ModernTradeCode,
  sku: string,
  flag: SkuAnalysisFlagName,
  enabled: boolean,
): Promise<SkuAnalysisFlagResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/performance/sku-flags/${encodeURIComponent(mtCode)}/${encodeURIComponent(sku)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flag, enabled }),
    },
  )
  if (!response.ok) {
    throw new Error(await apiError(response, `SKU Flag API ตอบกลับ ${response.status}`))
  }
  return response.json() as Promise<SkuAnalysisFlagResponse>
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
  const { query } = performanceQuery({ ...queryInput, skuIds: [sku] }, false)
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
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : `${queryInput.mtCode ?? 'TWD'}_${queryInput.mode}_${metric}_${grain}.xlsx`,
  }
}
