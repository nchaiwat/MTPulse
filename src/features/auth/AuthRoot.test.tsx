import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthRoot } from './AuthRoot'
import { setSessionToken } from './authApi'
vi.mock('../../app/App', () => ({ App: ({ auth }: { auth: { user: { full_name: string } } }) => <div>Authenticated {auth.user.full_name}</div> }))
const cfg = { mode: 'ciam', sso_enabled: true, break_glass_active: false }
const user = { id: '1', username: 'viewer', full_name: 'Viewer User', role: 'viewer', active: true }
function response(body: unknown, status = 200) { return { ok: status < 400, status, json: async () => body } }
beforeEach(() => { window.history.replaceState({}, '', '/'); setSessionToken('') })
afterEach(() => { vi.unstubAllGlobals() })
describe('CIAM Login', () => {
  it('shows SSO and keeps emergency password form behind a labelled action', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(cfg)).mockResolvedValueOnce(response({ detail: 'anonymous' }, 401)))
    render(<AuthRoot />)
    expect(await screen.findByRole('button', { name: 'เข้าสู่ระบบด้วย CIAM' })).toBeEnabled()
    expect(screen.queryByLabelText('รหัสผ่าน')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'บัญชี Local สำหรับผู้ดูแลระบบฉุกเฉิน' }))
    expect(screen.getByLabelText('ชื่อผู้ใช้')).toBeInTheDocument()
    expect(screen.getByLabelText('รหัสผ่าน')).toHaveAttribute('type', 'password')
  })
  it('shows local form when SSO disabled without a false SSO error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({ ...cfg, sso_enabled: false })).mockResolvedValueOnce(response({}, 401)))
    render(<AuthRoot />)
    expect(await screen.findByLabelText('รหัสผ่าน')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
  it('processes callback once and removes authorization code from browser URL', async () => {
    window.history.replaceState({}, '', '/auth/callback?code=private-code&state=test-state')
    const fetchMock = vi.fn().mockResolvedValueOnce(response(cfg)).mockResolvedValueOnce(response({ user, provider: 'sso', csrf_token: 'csrf', expires_at: null }))
    vi.stubGlobal('fetch', fetchMock)
    render(<AuthRoot />)
    expect(await screen.findByText('Authenticated Viewer User')).toBeInTheDocument()
    expect(window.location.search).toBe('')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ code: 'private-code', state: 'test-state' })
  })
  it('shows callback failure and can start again', async () => {
    window.history.replaceState({}, '', '/auth/callback?error=access_denied')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(cfg)))
    render(<AuthRoot />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('CIAM ไม่อนุญาต'))
    expect(screen.getByRole('button', { name: 'เข้าสู่ระบบด้วย CIAM' })).toBeEnabled()
  })
})
