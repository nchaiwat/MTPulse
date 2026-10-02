import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CiamSettingsPanel } from './CiamSettingsPanel'
afterEach(() => vi.unstubAllGlobals())
it('loads redacted settings and preserves secret when left blank', async () => {
  const cfg = { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_auto_provision_group: 'viewer', client_secret_configured: true, ad_secret_configured: true, ciam_ad_gateway_url: 'http://192.168.12.11:3100/api/v2/login', ciam_ad_app_id: 'MTPULSE' }
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [] : cfg }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel />)
  fireEvent.click(screen.getByRole('button', { name: 'ตั้งค่า CIAM และผู้ใช้' }))
  expect(await screen.findByDisplayValue('client')).toBeInTheDocument()
  expect(screen.getByLabelText('Client Secret')).toHaveValue('********')
  expect(screen.getByLabelText('AD Secret')).toHaveValue('********')
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก CIAM' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(JSON.parse(fetchMock.mock.calls[2][1].body).ciam_client_secret).toBeNull()
  expect(JSON.parse(fetchMock.mock.calls[2][1].body).ciam_ad_secret).toBeNull()
})


it('saves explicit AD binding separately from user roles', async () => {
  const cfg = { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_auto_provision_group: 'viewer', client_secret_configured: true, ad_secret_configured: true, ciam_ad_gateway_url: 'http://192.168.12.11:3100/api/v2/login', ciam_ad_app_id: 'MTPULSE' }
  const user = { id: 'ci-user', username: 'tester', full_name: 'Test', role: 'operator', active: true, ad_username: null }
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [user] : cfg }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel />)
  fireEvent.click(screen.getByRole('button', { name: 'ตั้งค่า CIAM และผู้ใช้' }))
  fireEvent.change(await screen.findByLabelText('AD username tester'), { target: { value: 'ad.tester' } })
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก AD tester' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/settings/ciam-sso/users/ci-user/ad-binding', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ username: 'ad.tester' }) })))
})
