import type { MonitoringResponse } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

async function requestMonitoring(method: 'GET' | 'POST', signal?: AbortSignal) {
  const response = await fetch(`${apiBaseUrl}/api/monitoring${method === 'POST' ? '/refresh' : ''}`, {
    method,
    signal,
  })
  if (!response.ok) throw new Error(`Monitoring API ตอบกลับ ${response.status}`)
  return response.json() as Promise<MonitoringResponse>
}

export function fetchMonitoring(signal?: AbortSignal) {
  return requestMonitoring('GET', signal)
}

export function refreshMonitoring() {
  return requestMonitoring('POST')
}

export async function decideSkuInterest(
  mtCode: string,
  sku: string,
  decision: 'accept' | 'ignore',
) {
  const response = await fetch(
    apiBaseUrl + '/api/admin/modern-trades/' + encodeURIComponent(mtCode)
      + '/sku-interests/' + encodeURIComponent(sku),
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    },
  )
  if (!response.ok) throw new Error('บันทึกการตัดสินใจ SKU ไม่สำเร็จ')
  return response.json() as Promise<{ status: string, message: string }>
}
