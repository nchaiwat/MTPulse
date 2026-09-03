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
  sourceMode?: 'upload' | 'fileshare'
  sourceFileId?: number | null
  timings?: ImportTimings
}

export interface ImportTimings {
  serverReadMs?: number
  downloadMs?: number
  parseMs?: number
  duplicateCheckMs?: number
  importMs?: number
}

export interface UploadProgress {
  phase: 'uploading' | 'processing'
  loaded: number
  total: number
  percent: number
}

export interface FileShareReadyFile {
  id: number
  filename: string
  dataDate: string | null
  sizeBytes: number
  discoveredAt: string
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

function xhrErrorMessage(xhr: XMLHttpRequest): string {
  try {
    const payload = JSON.parse(xhr.responseText) as { detail?: string }
    return payload.detail ?? `Import API ตอบกลับ ${xhr.status}`
  } catch {
    return xhr.status
      ? `Import API ตอบกลับ ${xhr.status}`
      : 'ไม่สามารถเชื่อมต่อ Import API'
  }
}

function uploadForm<T>(
  path: string,
  form: FormData,
  onProgress?: (progress: UploadProgress) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${apiBaseUrl}${path}`)
    xhr.upload.addEventListener('progress', (event) => {
      if (!event.lengthComputable) return
      onProgress?.({
        phase: 'uploading',
        loaded: event.loaded,
        total: event.total,
        percent: Math.min(100, Math.round((event.loaded / event.total) * 100)),
      })
    })
    xhr.upload.addEventListener('load', () => {
      onProgress?.({ phase: 'processing', loaded: 0, total: 0, percent: 100 })
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T)
        } catch {
          reject(new Error('Import API ส่งข้อมูลตอบกลับไม่ถูกต้อง'))
        }
        return
      }
      reject(new Error(xhrErrorMessage(xhr)))
    })
    xhr.addEventListener('error', () => reject(new Error('ไม่สามารถเชื่อมต่อ Import API')))
    xhr.addEventListener('abort', () => reject(new Error('ยกเลิกการส่งไฟล์แล้ว')))
    xhr.send(form)
  })
}

export async function previewImport(
  file: File,
  onProgress?: (progress: UploadProgress) => void,
): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  return uploadForm<ImportPreview>('/api/imports/preview', form, onProgress)
}

export async function confirmImport(
  file: File,
  checksum: string,
  onProgress?: (progress: UploadProgress) => void,
) {
  const form = new FormData()
  form.append('file', file)
  form.append('expected_checksum', checksum)
  return uploadForm<{
    message: string
    pendingSkus: string[]
    timings?: ImportTimings
    notification: { status: string; message: string }
  }>('/api/imports/confirm', form, onProgress)
}

export async function fetchFileShareReady(
  signal?: AbortSignal,
): Promise<FileShareReadyFile[]> {
  const response = await fetch(`${apiBaseUrl}/api/imports/fileshare-ready`, { signal })
  if (!response.ok) throw new Error(await errorMessage(response))
  const payload = await response.json() as { items: FileShareReadyFile[] }
  return payload.items
}

export async function previewFileShareImport(
  sourceFileId: number,
): Promise<ImportPreview> {
  const response = await fetch(
    `${apiBaseUrl}/api/imports/fileshare/${sourceFileId}/preview`,
    { method: 'POST' },
  )
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<ImportPreview>
}

export async function confirmFileShareImport(
  sourceFileId: number,
  checksum: string,
) {
  const form = new FormData()
  form.append('expected_checksum', checksum)
  const response = await fetch(
    `${apiBaseUrl}/api/imports/fileshare/${sourceFileId}/confirm`,
    { method: 'POST', body: form },
  )
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<{
    message: string
    pendingSkus: string[]
    timings?: ImportTimings
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
