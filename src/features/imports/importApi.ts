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
  return response.json() as Promise<{ message: string; notification: { status: string; message: string } }>
}

export async function fetchImportActivity(signal?: AbortSignal): Promise<ImportActivity[]> {
  const response = await fetch(`${apiBaseUrl}/api/imports/activity`, { signal })
  if (!response.ok) throw new Error(`Import API ตอบกลับ ${response.status}`)
  const payload = await response.json() as { items: ImportActivity[] }
  return payload.items
}