const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface TelegramSettings {
  telegramConfigured: boolean
  botTokenMasked: string
  groupId: string
  notifyManualImport: boolean
}

async function detail(response: Response) {
  try {
    const payload = await response.json() as { detail?: string }
    return payload.detail ?? `Settings API ตอบกลับ ${response.status}`
  } catch {
    return `Settings API ตอบกลับ ${response.status}`
  }
}

export async function fetchTelegramSettings(signal?: AbortSignal): Promise<TelegramSettings> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/telegram`, { signal })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<TelegramSettings>
}

export async function saveTelegramSettings(input: {
  botToken?: string
  groupId: string
  notifyManualImport: boolean
}): Promise<TelegramSettings> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/telegram`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bot_token: input.botToken || null,
      group_id: input.groupId,
      notify_manual_import: input.notifyManualImport,
    }),
  })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<TelegramSettings>
}

export async function fetchTelegramToken(): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/telegram/token`)
  if (!response.ok) throw new Error(await detail(response))
  const payload = await response.json() as { botToken: string }
  return payload.botToken
}

export async function testTelegram(): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/telegram/test`, { method: 'POST' })
  if (!response.ok) throw new Error(await detail(response))
  const payload = await response.json() as { message: string }
  return payload.message
}