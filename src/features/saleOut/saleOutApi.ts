import type { SaleOutFilters, SaleOutReport } from './types'

export async function fetchSaleOutReport(filters: SaleOutFilters, signal?: AbortSignal): Promise<SaleOutReport> {
  const params = new URLSearchParams({
    base_year: String(filters.baseYear),
    comparison_year: String(filters.comparisonYear),
    sales_basis: filters.salesBasis,
    metric: filters.metric,
  })
  if (filters.cutoff) params.set('cutoff', filters.cutoff)
  filters.mtCodes?.forEach((code) => params.append('mt_code', code))

  const response = await fetch(`/api/sale-out?${params.toString()}`, { signal })
  if (!response.ok) {
    let message = 'ไม่สามารถโหลดรายงาน Sale Out ได้'
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // Keep the stable user-facing fallback when the server does not return JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<SaleOutReport>
}
