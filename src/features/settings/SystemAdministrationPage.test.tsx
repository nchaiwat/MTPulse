import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SystemAdministrationPage } from './SystemAdministrationPage'
import { RoleContext } from '../auth/permissions'

afterEach(() => vi.unstubAllGlobals())
it('separates CIAM and user management and protects unsaved edits', async () => {
  vi.stubGlobal('fetch', vi.fn((path: string) => Promise.resolve({ ok: true, json: async () => path.endsWith('/users') ? [] : { ciam_base_url: 'https://ciam.windowasia.com', ciam_client_id: 'client', ciam_redirect_uri: 'https://wa-mtpulse.wa.net/auth/callback', ciam_sso_enabled: true, ciam_break_glass_active: false, ciam_session_ttl_minutes: 480, ciam_ad_gateway_url: '', ciam_ad_app_id: 'MTPULSE' } })))
  const dirty = vi.fn()
  const confirm = vi.fn().mockReturnValue(false)
  vi.stubGlobal('confirm', confirm)
  render(<RoleContext.Provider value="admin"><SystemAdministrationPage onDirtyChange={dirty} /></RoleContext.Provider>)
  const input = await screen.findByLabelText('Client ID')
  expect(screen.queryByLabelText(/Account/)).not.toBeInTheDocument()
  fireEvent.change(input, { target: { value: 'changed' } })
  fireEvent.click(screen.getByRole('tab', { name: 'User Management' }))
  expect(confirm).toHaveBeenCalled()
  expect(screen.getByLabelText('Client ID')).toHaveValue('changed')
  confirm.mockReturnValue(true)
  fireEvent.click(screen.getByRole('tab', { name: 'User Management' }))
  expect(await screen.findByLabelText(/Account/)).toBeInTheDocument()
  expect(screen.queryByLabelText('Client ID')).not.toBeInTheDocument()
})
it('denies non-admin page access', () => {
  render(<RoleContext.Provider value="operator"><SystemAdministrationPage onDirtyChange={vi.fn()} /></RoleContext.Provider>)
  expect(screen.getByRole('alert')).toHaveTextContent('เฉพาะ System Admin')
  expect(screen.queryByRole('tab')).not.toBeInTheDocument()
})
