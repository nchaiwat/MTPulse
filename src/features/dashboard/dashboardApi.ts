import type { DashboardPeriod, TwdDashboardResponse } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export async function fetchTwdDashboard(
  period: DashboardPeriod,
  year?: number,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ period })
  if (year) params.set('year', String(year))
  const response = await fetch(`${apiBaseUrl}/api/dashboards/twd?${params}`, { signal })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? `Dashboard API ตอบกลับ ${response.status}`)
  }
  return response.json() as Promise<TwdDashboardResponse>
}
