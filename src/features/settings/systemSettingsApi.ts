const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export interface TelegramSettings {
  telegramConfigured: boolean
  botTokenMasked: string
  groupId: string
  notifyManualImport: boolean
}

export type TechnicalMetricCode = 'cpu' | 'memory' | 'disk' | 'connections' | 'deadTuples'

export interface TechnicalNotificationSettings {
  dailyEnabled: boolean
  dailyTime: string
  criticalEnabled: boolean
  recoveryEnabled: boolean
  cooldownMinutes: number
  thresholds: Record<TechnicalMetricCode, { warning: number; critical: number }>
}

export interface TechnicalHealthCheck {
  status: 'sent'
  message: string
  checkedAt: string
  overallStatus: 'healthy' | 'warning' | 'critical'
  metrics: Array<{
    code: TechnicalMetricCode
    label: string
    value: number | null
    unit: string
    status: 'healthy' | 'warning' | 'critical' | 'unknown'
  }>
}

export const defaultTechnicalNotificationSettings: TechnicalNotificationSettings = {
  dailyEnabled: true,
  dailyTime: '07:00',
  criticalEnabled: true,
  recoveryEnabled: true,
  cooldownMinutes: 60,
  thresholds: {
    cpu: { warning: 80, critical: 95 },
    memory: { warning: 80, critical: 90 },
    disk: { warning: 80, critical: 90 },
    connections: { warning: 80, critical: 95 },
    deadTuples: { warning: 10, critical: 20 },
  },
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

export async function fetchTechnicalNotificationSettings(
  signal?: AbortSignal,
): Promise<TechnicalNotificationSettings> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/technical-notifications`, { signal })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<TechnicalNotificationSettings>
}

export async function saveTechnicalNotificationSettings(
  input: TechnicalNotificationSettings,
): Promise<TechnicalNotificationSettings> {
  const response = await fetch(`${apiBaseUrl}/api/settings/system/technical-notifications`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      daily_enabled: input.dailyEnabled,
      daily_time: input.dailyTime,
      critical_enabled: input.criticalEnabled,
      recovery_enabled: input.recoveryEnabled,
      cooldown_minutes: input.cooldownMinutes,
      thresholds: input.thresholds,
    }),
  })
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<TechnicalNotificationSettings>
}

export async function checkTechnicalHealth(): Promise<TechnicalHealthCheck> {
  const response = await fetch(
    `${apiBaseUrl}/api/settings/system/technical-notifications/check`,
    { method: 'POST' },
  )
  if (!response.ok) throw new Error(await detail(response))
  return response.json() as Promise<TechnicalHealthCheck>
}
