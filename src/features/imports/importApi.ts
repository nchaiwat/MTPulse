const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface ImportPreview {
  detectedMt: string
  detectedMtName: string
  filename: string
  checksum: string
  dataDate: string
  rowCount: number
  skuCount: number
  branchCount: number
  sourceAmount: number
  amount: number
  salesQty: number
  stockOnHand: number
  stockOnOrder: number
  negativeRowCount: number
  warnings: string[]
  canImport: boolean
  duplicateReason: string | null
}

export interface ImportActivity {
  id: number
  occurredAt: string
  action: string
  status: string
  message: string
  filename: string
  mtCode: string
  dataDate: string | null
  batchId: number | null
  notification?: { status: string; message: string }
}


export interface ImportBatchSummary {
  rowCount: number
  skuCount: number
  branchCount: number
  amount: number
  salesQty: number
  stockOnHand: number
  reportedStockOnHand: number
  stockOnOrder: number
  negativeRowCount: number
}

export interface ImportBatchDetail {
  batchId: number
  dataDate: string
  filename: string
  status: string
  warnings: string[]
  summary: ImportBatchSummary
  resolution: null | {
    type: string
    note: string
    resolvedAt: string
    resolvedBy: string
  }
}

export interface ReplacementPreview {
  batchId: number
  checksum: string
  filename: string
  dataDate: string
  current: ImportBatchSummary
  replacement: ImportBatchSummary
  warnings: string[]
  canReplace: boolean
  blockedReason: string | null
}
async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string }
    return payload.detail ?? `Import API ตอบกลับ ${response.status}`
  } catch {
    return `Import API ตอบกลับ ${response.status}`
  }
}

export async function previewImport(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${apiBaseUrl}/api/imports/preview`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ImportPreview>
}

export async function confirmImport(file: File, checksum: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('expected_checksum', checksum)
  const response = await fetch(`${apiBaseUrl}/api/imports/confirm`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<{
    message: string
    pendingSkus: string[]
    notification: { status: string; message: string }
  }>
}

export async function fetchImportActivity(signal?: AbortSignal): Promise<ImportActivity[]> {
  const response = await fetch(`${apiBaseUrl}/api/imports/activity`, { signal })
  if (!response.ok) throw new Error(`Import API ตอบกลับ ${response.status}`)
  const payload = await response.json() as { items: ImportActivity[] }
  return payload.items
}

export async function fetchImportBatch(batchId: number, signal?: AbortSignal): Promise<ImportBatchDetail> {
  const response = await fetch(`${apiBaseUrl}/api/imports/batches/${batchId}`, { signal })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ImportBatchDetail>
}

export async function acknowledgeImportWarning(batchId: number, note: string): Promise<ImportBatchDetail> {
  const response = await fetch(`${apiBaseUrl}/api/imports/batches/${batchId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ImportBatchDetail>
}

export async function previewBatchReplacement(batchId: number, file: File): Promise<ReplacementPreview> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${apiBaseUrl}/api/imports/batches/${batchId}/replacement-preview`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ReplacementPreview>
}

export async function replaceImportBatch(batchId: number, file: File, checksum: string): Promise<ImportBatchDetail> {
  const form = new FormData()
  form.append('file', file)
  form.append('expected_checksum', checksum)
  const response = await fetch(`${apiBaseUrl}/api/imports/batches/${batchId}/replace`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ImportBatchDetail>
}
