export type AuthUser = { id: string; username: string; full_name: string; role: 'viewer' | 'operator' | 'admin'; active: boolean; local?: boolean; ad_enabled?: boolean; ciam_linked?: boolean; ad_username?: string | null }
export type LoginSession = { user: AuthUser; provider: 'sso' | 'ad' | 'local' | 'development'; csrf_token: string; expires_at: string | null; portal_url?: string }
export type LoginConfig = { mode: string; sso_enabled: boolean; break_glass_active: boolean; ad_login_enabled?: boolean; portal_url?: string }
const base = import.meta.env.VITE_API_BASE_URL ?? ''
let csrfToken = ''
export function setSessionToken(token: string) { csrfToken = token }

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let options = init
  if (csrfToken) {
    const headers = new Headers(init?.headers)
    if (!['GET', 'HEAD', 'OPTIONS'].includes((init?.method ?? 'GET').toUpperCase())) headers.set('X-CSRF-Token', csrfToken)
    options = { ...init, credentials: 'include', headers }
  }
  const response = options === undefined ? await fetch(input) : await fetch(input, options)
  notifyUnauthorized(response.status)
  return response
}

export async function authRequest<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method, credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  })
  if (!response.ok) {
    if (!['/api/auth/me', '/api/auth/local/login', '/api/auth/ad/login', '/api/auth/sso/callback'].includes(path)) notifyUnauthorized(response.status)
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `คำขอไม่สำเร็จ (${response.status})`)
  }
  return response.json()
}

export function applyXhrAuth(xhr: XMLHttpRequest) {
  if (csrfToken) {
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', csrfToken)
  }
}
export function notifyUnauthorized(status: number) {
  if (status === 401) window.dispatchEvent(new Event('mtpulse:unauthorized'))
}
