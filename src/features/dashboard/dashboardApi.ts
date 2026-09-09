import type { DashboardMetric, DashboardPeriod, TwdDashboardResponse } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export async function fetchDashboard(
  mtCode: 'TWD' | 'HP' | 'MH',
  period: DashboardPeriod,
  year?: number,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ period })
  if (year) params.set('year', String(year))
  const response = await fetch(
    `${apiBaseUrl}/api/dashboards/${mtCode.toLowerCase()}?${params}`,
    { signal },
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? `Dashboard API ตอบกลับ ${response.status}`)
  }
  return response.json() as Promise<TwdDashboardResponse>
}

export function fetchTwdDashboard(
  period: DashboardPeriod,
  year?: number,
  signal?: AbortSignal,
) {
  return fetchDashboard('TWD', period, year, signal)
}

export async function downloadDashboard(
  mtCode: 'TWD' | 'HP' | 'MH',
  period: DashboardPeriod,
  metric: DashboardMetric,
  year?: number,
): Promise<{ blob: Blob, filename: string }> {
  const params = new URLSearchParams({ period, metric })
  if (year) params.set('year', String(year))
  const response = await fetch(
    `${apiBaseUrl}/api/dashboards/${mtCode.toLowerCase()}/export?${params}`,
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? `Dashboard Download API ตอบกลับ ${response.status}`)
  }
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename
      ? decodeURIComponent(encodedFilename)
      : `${mtCode}_Dashboard_${year ?? 'latest'}_${period}_${metric}.xlsx`,
  }
}
