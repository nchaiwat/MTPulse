import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CiamSettingsPanel } from './CiamSettingsPanel'
afterEach(() => vi.unstubAllGlobals())
it('loads redacted settings and preserves secret when left blank', async () => {
  const cfg = { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_auto_provision_group: 'viewer', client_secret_configured: true }
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [] : cfg }))
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSettingsPanel />)
  fireEvent.click(screen.getByRole('button', { name: 'ตั้งค่า CIAM และผู้ใช้' }))
  expect(await screen.findByDisplayValue('client')).toBeInTheDocument()
  expect(screen.getByText('บันทึก Secret แล้ว — เว้นว่างเพื่อคงค่าเดิม')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก CIAM' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(JSON.parse(fetchMock.mock.calls[2][1].body).ciam_client_secret).toBeNull()
})
