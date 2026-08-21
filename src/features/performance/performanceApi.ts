import type { Dimension, Mode, PerformanceResponse } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

interface PerformanceQuery {
  dateRange: string
  branchId: string
  mappingStatus: string
  hideUnmapped: boolean
  search: string
  page: number
  pageSize: number
  dimension: Dimension
  mode: Mode
  branchMonth: string
  signal?: AbortSignal
}

export interface ItemMappingImportReport {
  total_rows: number
  candidates: number
  inserted_pending: number
  unchanged: number
  skipped_blank: number
  new_source_skus: number
  conflicts: number
  branch_candidates: number
  branch_inserted_pending: number
  branch_updated: number
  branch_unchanged: number
  branch_skipped_blank: number
  branch_conflicts: number
  errors: string[]
}

function dateBounds(dateRange: string) {
  const selectedDate = dateRange === 'all' ? null : dateRange
  return {
    dateFrom: selectedDate ?? '2026-08-16',
    dateTo: selectedDate ?? '2026-08-17',
  }
}

async function apiError(response: Response, fallback: string) {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? fallback
  } catch {
    return fallback
  }
}

export async function fetchPerformance(queryInput: PerformanceQuery): Promise<PerformanceResponse> {
  const { dateFrom, dateTo } = dateBounds(queryInput.dateRange)
  const grain = queryInput.dimension === 'month'
    ? 'month'
    : queryInput.dimension === 'branch' && queryInput.mode === 'sales'
      ? 'branch_month'
      : 'day'
  const query = new URLSearchParams({
    page: String(queryInput.page),
    page_size: String(queryInput.pageSize),
    grain,
  })
  if (grain === 'branch_month') {
    query.set('period_month', queryInput.branchMonth)
  } else if (queryInput.dateRange !== 'all' || queryInput.dimension !== 'month') {
    query.set('date_from', dateFrom)
    query.set('date_to', dateTo)
  }
  if (queryInput.branchId !== 'all') query.set('branch_id', queryInput.branchId)
  if (queryInput.mappingStatus !== 'all') query.set('mapping_status', queryInput.mappingStatus)
  if (queryInput.hideUnmapped) query.set('hide_unmapped', 'true')
  if (queryInput.search) query.set('search', queryInput.search)
  const response = await fetch(`${apiBaseUrl}/api/performance?${query}`, { signal: queryInput.signal })
  if (!response.ok) throw new Error(`Performance API ตอบกลับ ${response.status}`)
  return response.json() as Promise<PerformanceResponse>
}

export async function exportItemMappings(dateRange: string): Promise<{ blob: Blob, filename: string }> {
  const { dateFrom, dateTo } = dateBounds(dateRange)
  const query = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
  const response = await fetch(`${apiBaseUrl}/api/item-mappings/export?${query}`)
  if (!response.ok) throw new Error(await apiError(response, `Export API ตอบกลับ ${response.status}`))
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : `TWD_Item_Mapping_${dateFrom}_${dateTo}.xlsx`,
  }
}

export async function importItemMappings(file: File, dateRange: string): Promise<ItemMappingImportReport> {
  const { dateFrom } = dateBounds(dateRange)
  const body = new FormData()
  body.set('file', file)
  body.set('effective_from', dateFrom)
  const response = await fetch(`${apiBaseUrl}/api/item-mappings/import`, { method: 'POST', body })
  if (!response.ok) throw new Error(await apiError(response, `Import API ตอบกลับ ${response.status}`))
  return response.json() as Promise<ItemMappingImportReport>
}
