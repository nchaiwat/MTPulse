const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface UnmatchedVisibility {
  showUnmatchedItems: boolean
  showUnmatchedBranches: boolean
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
