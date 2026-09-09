import type { ImportRun } from './fileShareSettingsApi'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface SkuBackfillOptions {
  mappings: Array<{
    sourceSku: string
    sourceDescription: string | null
    waItemCode: string
    waItemDescription: string | null
    effectiveFrom: string
  }>
  unmappedSkus: Array<{
    sourceSku: string
    sourceDescription: string | null
    interestStatus: 'active' | 'pending' | 'ignored'
    firstSeenDate: string
    lastSeenDate: string
  }>
  registry: {
    earliestDate: string | null
    latestDate: string | null
    refreshedAt: string | null
  }
}

export interface SkuBackfillPreview {
  sourceSku: string
  rangeStart: string
  rangeEnd: string
  mappingEffectiveFrom: string
  mappingWillMoveTo: string | null
  mappingConflict: boolean
  registry: SkuBackfillOptions['registry']
  counts: {
    candidate: number
    already_present: number
    waiting_for_batch: number
    source_conflict: number
  }
  dates: Array<{
    dataDate: string
    status: 'candidate' | 'already_present' | 'waiting_for_batch' | 'source_conflict'
    message: string
    sourceFileId: number | null
    batchId: number | null
  }>
}

async function apiError(response: Response) {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? `API ตอบกลับ ${response.status}`
  } catch {
    return `API ตอบกลับ ${response.status}`
  }
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${url}`, init)
  if (!response.ok) throw new Error(await apiError(response))
  return response.json() as Promise<T>
}

export function fetchSkuBackfillOptions(mtCode = 'TWD', signal?: AbortSignal) {
  return jsonRequest<SkuBackfillOptions>(
    `/api/admin/modern-trades/${encodeURIComponent(mtCode)}/sku-backfills/options`,
    { signal },
  )
}

export function previewSkuBackfill(sourceSku: string, rangeStart: string | null, mtCode = 'TWD') {
  return jsonRequest<SkuBackfillPreview>(
    `/api/admin/modern-trades/${encodeURIComponent(mtCode)}/sku-backfills/preview`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_sku: sourceSku, range_start: rangeStart }),
    },
  )
}

export function startSkuBackfill(sourceSku: string, rangeStart: string | null, mtCode = 'TWD') {
  return jsonRequest<ImportRun>(`/api/admin/modern-trades/${encodeURIComponent(mtCode)}/sku-backfills`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_sku: sourceSku,
      range_start: rangeStart,
      confirmed: true,
    }),
  })
}

export function refreshSourceRegistry(mtCode = 'TWD') {
  return jsonRequest<ImportRun>(
    `/api/admin/modern-trades/${encodeURIComponent(mtCode)}/source-registry/refresh`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed: true }),
    },
  )
}

export function fetchImportRun(runId: number) {
  return jsonRequest<ImportRun>(`/api/admin/import-runs/${runId}`)
}

export async function fetchLatestBackfillRun(mtCode = 'TWD', signal?: AbortSignal) {
  const payload = await jsonRequest<{ runs: ImportRun[] }>(
    `/api/admin/import-runs?mt_code=${encodeURIComponent(mtCode)}&limit=20`,
    { signal },
  )
  return payload.runs.find((run) => run.mode === 'sku_backfill') ?? null
}

export function stopSkuBackfill(runId: number) {
  return jsonRequest<ImportRun>(`/api/admin/import-runs/${runId}/stop`, {
    method: 'POST',
  })
}

export function resumeSkuBackfill(runId: number) {
  return jsonRequest<ImportRun>(`/api/admin/import-runs/${runId}/resume`, {
    method: 'POST',
  })
}
