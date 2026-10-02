import { useEffect, useRef, useState } from 'react'
import { Activity } from 'lucide-react'
import { App } from '../../app/App'
import { authRequest, setSessionToken, type LoginConfig, type LoginSession } from './authApi'
import './auth.css'

export function AuthRoot() {
  const [session, setSession] = useState<LoginSession | null>(null)
  const [config, setConfig] = useState<LoginConfig | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const [local, setLocal] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const started = useRef(false)
  const accept = (value: LoginSession) => { setSessionToken(value.csrf_token); setSession(value); window.history.replaceState({}, '', '/') }

  useEffect(() => {
    if (started.current) return
    started.current = true
    void (async () => {
      try {
        const cfg = await authRequest<LoginConfig>('/api/auth/sso/config')
        setConfig(cfg)
        if (window.location.pathname === '/auth/callback') {
          const query = new URLSearchParams(window.location.search)
          window.history.replaceState({}, '', '/auth/callback')
          if (query.has('error') || !query.get('code') || !query.get('state')) throw new Error('CIAM ไม่อนุญาตการเข้าสู่ระบบ กรุณาเริ่มใหม่')
          accept(await authRequest<LoginSession>('/api/auth/sso/callback', 'POST', { code: query.get('code'), state: query.get('state') }))
        } else {
          try { accept(await authRequest<LoginSession>('/api/auth/me')) } catch { /* Normal anonymous login. */ }
        }
      } catch (e) { setError(e instanceof Error ? e.message : 'เชื่อมต่อระบบไม่สำเร็จ') }
      finally { setBusy(false) }
    })()
  }, [])

  useEffect(() => {
    const expired = () => {
      setSessionToken('')
      if (session?.provider === 'sso' && config?.portal_url) window.location.assign(config.portal_url)
      else { setSession(null); setError('Session หมดอายุ กรุณาเข้าสู่ระบบใหม่') }
    }
    window.addEventListener('mtpulse:unauthorized', expired)
    const remaining = session?.expires_at ? new Date(session.expires_at).getTime() - Date.now() : null
    const timer = remaining === null ? undefined : window.setTimeout(expired, Math.max(0, remaining))
    return () => { window.removeEventListener('mtpulse:unauthorized', expired); window.clearTimeout(timer) }
  }, [session, config])

  async function logout() {
    try {
      const result = await authRequest<{ redirect_url: string }>('/api/auth/logout', 'POST')
      setSessionToken(''); setSession(null); window.location.assign(result.redirect_url)
    } catch (e) { setError(e instanceof Error ? e.message : 'ออกจากระบบไม่สำเร็จ') }
  }
  if (session) return <><App auth={session} onLogout={() => void logout()} />{error && <div className="auth-global-error" role="alert">{error}</div>}</>

  async function submit(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'เข้าสู่ระบบไม่สำเร็จ') }
    finally { setPassword(''); setBusy(false) }
  }
  const sso = config?.sso_enabled && !config.break_glass_active
  const ad = config?.break_glass_active && config.ad_login_enabled && !local
  return <main className="auth-page"><section className="auth-panel" aria-labelledby="login-heading">
    <Activity size={28} aria-hidden="true" /><h1 id="login-heading">MT Pulse</h1><p>เข้าสู่ระบบวิเคราะห์ Modern Trade</p>
    {config?.break_glass_active && <p className="auth-warning" role="status">โหมดฉุกเฉิน — ติดต่อผู้ดูแลระบบเพื่อเข้าใช้งาน</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    {busy && <p role="status">กำลังตรวจสอบ…</p>}
    {!config && !busy && <button onClick={() => window.location.reload()}>ลองใหม่</button>}
    {sso && !local && <><button className="auth-primary" disabled={busy} onClick={() => void submit(async () => {
      const result = await authRequest<{ authorize_url: string }>('/api/auth/sso/authorize-url', 'POST')
      window.location.assign(result.authorize_url)
    })}>เข้าสู่ระบบด้วย CIAM</button><button className="auth-link" disabled={busy} onClick={() => setLocal(true)}>บัญชี Local สำหรับผู้ดูแลระบบฉุกเฉิน</button></>}
    {config && (!sso || local) && <form onSubmit={(event) => {
      event.preventDefault()
      void submit(async () => accept(await authRequest<LoginSession>(ad ? '/api/auth/ad/login' : '/api/auth/local/login', 'POST', { username, password })))
    }}>
      <p>{ad ? 'เข้าสู่ระบบด้วย AD — เฉพาะบัญชีที่ Admin ผูกไว้' : 'บัญชี Local สำหรับผู้ดูแลระบบฉุกเฉิน'}</p>
      <label>ชื่อผู้ใช้<input autoComplete="username" value={username} maxLength={200} required onChange={e => setUsername(e.target.value)} /></label>
      <label>รหัสผ่าน<input type="password" autoComplete="current-password" value={password} maxLength={256} required onChange={e => setPassword(e.target.value)} /></label>
      <button className="auth-primary" disabled={busy}>{ad ? 'เข้าสู่ระบบด้วย AD' : 'เข้าสู่ระบบ'}</button>
      {config.ad_login_enabled && config.break_glass_active && <button type="button" className="auth-link" disabled={busy} onClick={() => { setLocal(!local); setPassword(''); setUsername('') }}>{local ? 'กลับไปเข้าสู่ระบบด้วย AD' : 'บัญชี Local สำหรับผู้ดูแลระบบฉุกเฉิน'}</button>}
      {sso && <button type="button" className="auth-link" disabled={busy} onClick={() => setLocal(false)}>กลับไปเข้าสู่ระบบด้วย CIAM</button>}
    </form>}
    <small>สำหรับใช้งานภายในองค์กร</small>
  </section></main>
}
