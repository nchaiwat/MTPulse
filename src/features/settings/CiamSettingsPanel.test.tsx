import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CiamSettingsPanel } from './CiamSettingsPanel'
afterEach(() => vi.unstubAllGlobals())
it('loads redacted settings and preserves secret when left blank', async () => {
  const cfg = { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_auto_provision_group: 'viewer', client_secret_configured: true, ad_secret_configured: true, ciam_ad_gateway_url: 'http://192.168.12.11:3100/api/v2/login', ciam_ad_app_id: 'MTPULSE' }
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [] : path.endsWith('/ciam-agent') ? { enabled: false, app_code: 'mtpulse', key_configured: false, pending_results: 0 } : cfg }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel />)
  expect(await screen.findByDisplayValue('client')).toBeInTheDocument()
  expect(screen.getByLabelText('Client Secret')).toHaveValue('********')
  expect(screen.getByLabelText('AD Secret')).toHaveValue('********')
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก CIAM' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(call => call[1]?.method === 'PUT')).toBe(true))
  const saved = fetchMock.mock.calls.find(call => call[1]?.method === 'PUT')!
  expect(JSON.parse(saved[1].body).ciam_client_secret).toBeNull()
  expect(JSON.parse(saved[1].body).ciam_ad_secret).toBeNull()
})


it('allows AD for an existing account', async () => {
  const cfg = { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_auto_provision_group: 'viewer', client_secret_configured: true, ad_secret_configured: true, ciam_ad_gateway_url: 'http://192.168.12.11:3100/api/v2/login', ciam_ad_app_id: 'MTPULSE' }
  const user = { id: 'ci-user', username: 'tester', full_name: 'Test', role: 'operator', active: true, ad_username: null }
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [user] : cfg }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel mode="users" />)
  fireEvent.change(await screen.findByLabelText('AD Login tester'), { target: { value: 'true' } })
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก tester' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/settings/ciam-sso/users/ci-user', expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ role: 'operator', active: true, ad_enabled: true }) })))
})


it('creates a managed account with selected role and AD permission', async () => {
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [] : { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: '', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: false, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_ad_gateway_url: 'http://192.168.12.11:3100/api/v2/login', ciam_ad_app_id: 'MTPULSE' } }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel mode="users" />)
  fireEvent.change(await screen.findByLabelText(/Account/), { target: { value: 'Chaiwat.N' } })
  fireEvent.change(screen.getByLabelText('ชื่อที่แสดง'), { target: { value: 'Chaiwat' } })
  fireEvent.change(screen.getByLabelText('สิทธิ์ผู้ใช้ใหม่'), { target: { value: 'operator' } })
  fireEvent.change(screen.getByLabelText('AD Login'), { target: { value: 'true' } })
  fireEvent.click(screen.getByRole('button', { name: 'สร้างผู้ใช้' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/settings/ciam-sso/users', expect.objectContaining({ method: 'POST', body: JSON.stringify({ username: 'Chaiwat.N', full_name: 'Chaiwat', role: 'operator', ad_enabled: true }) })))
})
