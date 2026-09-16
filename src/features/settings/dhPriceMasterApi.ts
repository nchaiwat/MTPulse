const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export type DhPriceStatus = 'current' | 'upcoming' | 'expired'

export interface DhPricePreview {
  row_count: number
  candidate_count: number
  inserted: number
  updated: number
  unchanged: number
  source_checksum_sha256: string
  preview_fingerprint: string
  errors: string[]
}

export interface DhPriceConfirmation extends DhPricePreview {
  confirmed_by: string
  confirmed_at: string
}

export interface DhPriceListItem {
  source_sku: string
  unit_price_ex_vat: string | number
  effective_from: string
  effective_to: string | null
  status: DhPriceStatus
  source_filename: string
  changed_by: string
  changed_at: string
}

export interface DhPriceListPage {
  items: DhPriceListItem[]
  total: number
  page: number
  page_size: number
}

async function apiError(response: Response, fallback: string) {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? fallback
  } catch {
    return fallback
  }
}

export async function downloadDhPriceTemplate(): Promise<{ blob: Blob, filename: string }> {
  const response = await fetch(`${apiBaseUrl}/api/dh-prices/template`)
  if (!response.ok) throw new Error(await apiError(response, `Download API ตอบกลับ ${response.status}`))
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : 'DH_Price_Master_Template.xlsx',
  }
}

export async function previewDhPriceMaster(file: File): Promise<DhPricePreview> {
  const body = new FormData()
  body.set('file', file)
  const response = await fetch(`${apiBaseUrl}/api/dh-prices/preview`, { method: 'POST', body })
  if (!response.ok) throw new Error(await apiError(response, `Preview API ตอบกลับ ${response.status}`))
  return response.json() as Promise<DhPricePreview>
}

export async function confirmDhPriceMaster(file: File, previewFingerprint: string): Promise<DhPriceConfirmation> {
  const body = new FormData()
  body.set('file', file)
  body.set('preview_fingerprint', previewFingerprint)
  const response = await fetch(`${apiBaseUrl}/api/dh-prices/confirm`, { method: 'POST', body })
  if (!response.ok) throw new Error(await apiError(response, `Confirm API ตอบกลับ ${response.status}`))
  return response.json() as Promise<DhPriceConfirmation>
}

export async function fetchDhPrices(
  options: { query?: string, status?: DhPriceStatus | '', page: number, pageSize: number },
  signal?: AbortSignal,
): Promise<DhPriceListPage> {
  const query = new URLSearchParams({
    page: String(options.page),
    page_size: String(options.pageSize),
  })
  if (options.query?.trim()) query.set('q', options.query.trim())
  if (options.status) query.set('status', options.status)
  const response = await fetch(`${apiBaseUrl}/api/dh-prices?${query}`, { signal })
  if (!response.ok) throw new Error(await apiError(response, `Price API ตอบกลับ ${response.status}`))
  return response.json() as Promise<DhPriceListPage>
}
