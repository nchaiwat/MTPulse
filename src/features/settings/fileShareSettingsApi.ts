const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface FileShareProfile {
  code: string
  name: string
  subfolder: string
  enabled: boolean
  fullPath: string
}

export interface FileShareTestResult {
  code: string
  name: string
  path: string
  status: 'success' | 'failed'
  message: string
}

export interface FileShareSettings {
  baseUnc: string
  domain: string
  username: string
  passwordConfigured: boolean
  passwordMasked: string
  lastTestAt: string | null
  lastTestStatus: string | null
  lastTestResults: FileShareTestResult[]
  profiles: FileShareProfile[]
}

export interface FileShareSettingsInput {
  baseUnc: string
  domain: string
  username: string
  password?: string
  profiles: FileShareProfile[]
}

async function detail(response: Response) {
  try {
    const payload = await response.json() as { detail?: string }
    return payload.detail ?? `FileShare API ตอบกลับ ${response.status}`
  } catch {
    return `FileShare API ตอบกลับ ${response.status}`
  }
}

function requestBody(input: FileShareSettingsInput) {
  return JSON.stringify({
    base_unc: input.baseUnc,
    domain: input.domain,
    username: input.username,
    password: input.password || null,
    profiles: input.profiles.map((profile) => ({
      code: profile.code,
      subfolder: profile.subfolder,
      enabled: profile.enabled,
    })),
  })
}

export async function fetchFileShareSettings(signal?: AbortSignal): Promise<FileShareSettings> {
  const response = await fetch(`${apiBaseUrl}/api/admin/fileshare-settings`, { signal })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<FileShareSettings>
}

export async function saveFileShareSettings(input: FileShareSettingsInput): Promise<FileShareSettings> {
  const response = await fetch(`${apiBaseUrl}/api/admin/fileshare-settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: requestBody(input),
  })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<FileShareSettings>
}

export async function fetchFileSharePassword(): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/api/admin/fileshare-settings/password`)
  if (!response.ok) throw new Error(await detail(response))
  const payload = await response.json() as { password: string }
  return payload.password
}

export async function testFileShare(input: FileShareSettingsInput): Promise<{
  status: 'success' | 'failed'
  message: string
  results: FileShareTestResult[]
}> {
  const response = await fetch(`${apiBaseUrl}/api/admin/fileshare-settings/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: requestBody(input),
  })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<{
    status: 'success' | 'failed'
    message: string
    results: FileShareTestResult[]
  }>
}
