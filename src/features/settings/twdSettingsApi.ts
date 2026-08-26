const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface UnmatchedVisibility {
  showUnmatchedItems: boolean
  showUnmatchedBranches: boolean
  mappingAttentionItems: number
  mappingAttentionBranches: number
  reportPageSize: number
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

async function apiError(response: Response, fallback: string) {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? fallback
  } catch {
    return fallback
  }
}

export async function fetchUnmatchedVisibility(
  signal?: AbortSignal,
): Promise<UnmatchedVisibility> {
  const response = await fetch(
    `${apiBaseUrl}/api/settings/twd/unmatched-visibility`,
    { signal },
  )
  if (!response.ok) throw new Error(`Settings API ตอบกลับ ${response.status}`)
  return response.json() as Promise<UnmatchedVisibility>
}

export async function updateUnmatchedVisibility(
  settings: UnmatchedVisibility,
): Promise<UnmatchedVisibility> {
  const response = await fetch(
    `${apiBaseUrl}/api/settings/twd/unmatched-visibility`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        show_unmatched_items: settings.showUnmatchedItems,
        show_unmatched_branches: settings.showUnmatchedBranches,
      }),
    },
  )
  if (!response.ok) throw new Error(`Settings API ตอบกลับ ${response.status}`)
  return response.json() as Promise<UnmatchedVisibility>
}

export async function exportItemMappings(): Promise<{ blob: Blob, filename: string }> {
  const response = await fetch(`${apiBaseUrl}/api/item-mappings/export`)
  if (!response.ok) throw new Error(await apiError(response, `Export API ตอบกลับ ${response.status}`))
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : 'TWD_Item_Mapping.xlsx',
  }
}

export async function importItemMappings(file: File): Promise<ItemMappingImportReport> {
  const body = new FormData()
  body.set('file', file)
  const response = await fetch(`${apiBaseUrl}/api/item-mappings/import`, { method: 'POST', body })
  if (!response.ok) throw new Error(await apiError(response, `Import API ตอบกลับ ${response.status}`))
  return response.json() as Promise<ItemMappingImportReport>
}

export async function downloadDataCoverage(
  mtCode: string,
  year: number,
): Promise<{ blob: Blob, filename: string }> {
  const query = new URLSearchParams({ mt_code: mtCode, year: String(year) })
  const response = await fetch(`${apiBaseUrl}/api/data-coverage/export?${query}`)
  if (!response.ok) throw new Error(await apiError(response, `Download API ตอบกลับ ${response.status}`))
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedFilename ? decodeURIComponent(encodedFilename) : `${mtCode}_Data_Coverage_${year}.xlsx`,
  }
}

export async function updateReportPageSize(
  reportPageSize: number,
): Promise<{ reportPageSize: number }> {
  const response = await fetch(
    `${apiBaseUrl}/api/settings/twd/report-page-size`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_page_size: reportPageSize }),
    },
  )
  if (!response.ok) {
    throw new Error(await apiError(response, `Settings API ตอบกลับ ${response.status}`))
  }
  return response.json() as Promise<{ reportPageSize: number }>
}
