import { useState } from 'react'
import { CiamSecretField } from './CiamSecretField'
import { authRequest, setSessionToken, type LoginSession, type AuthUser } from '../auth/authApi'
import '../auth/auth.css'

type Config = {
  ciam_base_url: string; ciam_client_id: string; ciam_redirect_uri: string;
  ciam_sso_enabled: boolean; ciam_break_glass_active: boolean;
  ciam_session_ttl_minutes: number; ciam_auto_provision_group: 'viewer';
  client_secret_configured: boolean; ad_secret_configured: boolean;
  ciam_ad_gateway_url: string; ciam_ad_app_id: string;
}
export function CiamSettingsPanel({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [open, setOpen] = useState(false)
  const [cfg, setCfg] = useState<Config | null>(null)
  const [users, setUsers] = useState<AuthUser[]>([])
  const [secret, setSecret] = useState('')
  const [secretVersion, setSecretVersion] = useState(0)
  const [adSecret, setAdSecret] = useState('')
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('')
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'ทำรายการไม่สำเร็จ') }
    finally { setBusy(false) }
  }
  async function load() {
    const [settings, accounts] = await Promise.all([
      authRequest<Config>('/api/settings/ciam-sso'), authRequest<AuthUser[]>('/api/settings/ciam-sso/users'),
    ])
    setCfg(settings); setUsers(accounts)
  }
  return <section className="ciam-panel" aria-labelledby="ciam-heading">
    <h2 id="ciam-heading">Central IAM SSO</h2>
    <p>การเข้าสู่ระบบและสิทธิ์ผู้ใช้ · Mode B · ผู้ใช้ใหม่เป็น Viewer</p>
    <button type="button" aria-expanded={open} onClick={() => { setOpen(!open); if (!open) void run(load) }}>ตั้งค่า CIAM และผู้ใช้</button>
    {open && <>
      {busy && <p role="status">กำลังดำเนินการ…</p>}
      {error && <p role="alert" className="auth-error">{error}</p>}
      {message && <p role="status">{message}</p>}
      {!cfg && !busy && <button onClick={() => void run(load)}>ลองโหลดใหม่</button>}
      {cfg && <>
        <form onChange={() => onDirtyChange?.(true)} onSubmit={e => { e.preventDefault(); void run(async () => {
          const { client_secret_configured: _configured, ad_secret_configured: _adConfigured, ciam_break_glass_active: _breakGlass, ...values } = cfg
          void _configured; void _adConfigured; void _breakGlass
          setCfg(await authRequest<Config>('/api/settings/ciam-sso', 'PUT', { ...values, ciam_client_secret: secret || null, ciam_ad_secret: adSecret || null }))
          setSecret(''); setAdSecret(''); setSecretVersion(v => v + 1); onDirtyChange?.(false); setMessage('บันทึกแล้ว มีผลกับคำขอใหม่ทันที')
        }) }}>
          <fieldset disabled={busy}><legend>การเชื่อมต่อ CIAM</legend><div className="ciam-form">
            <label>CIAM Base URL<input type="url" required value={cfg.ciam_base_url} onChange={e => setCfg({ ...cfg, ciam_base_url: e.target.value })} /></label>
            <label>Client ID<input value={cfg.ciam_client_id} onChange={e => setCfg({ ...cfg, ciam_client_id: e.target.value })} /></label>
            <CiamSecretField key={`client-${secretVersion}`} label="Client Secret" kind="client" configured={cfg.client_secret_configured} value={secret} onChange={value => { setSecret(value); onDirtyChange?.(true) }} />
            <label>Callback URL<input type="url" required value={cfg.ciam_redirect_uri} onChange={e => setCfg({ ...cfg, ciam_redirect_uri: e.target.value })} /></label>
            <label>อายุ Session (นาที)<input type="number" min={5} max={1440} required value={cfg.ciam_session_ttl_minutes} onChange={e => setCfg({ ...cfg, ciam_session_ttl_minutes: Number(e.target.value) })} /></label>
            <label>SSO<select value={String(cfg.ciam_sso_enabled)} onChange={e => setCfg({ ...cfg, ciam_sso_enabled: e.target.value === 'true' })}><option value="false">ปิด</option><option value="true">เปิด</option></select></label>
            <label>AD Gateway URL<input type="url" required value={cfg.ciam_ad_gateway_url ?? ''} onChange={e => setCfg({ ...cfg, ciam_ad_gateway_url: e.target.value })} /></label>
            <label>AD App ID<input required value={cfg.ciam_ad_app_id ?? ''} onChange={e => setCfg({ ...cfg, ciam_ad_app_id: e.target.value })} /></label>
            <CiamSecretField key={`ad-${secretVersion}`} label="AD Secret" kind="ad" configured={cfg.ad_secret_configured} value={adSecret} onChange={value => { setAdSecret(value); onDirtyChange?.(true) }} />
          </div><div className="ciam-actions"><button type="submit">บันทึก CIAM</button>
          <button type="button" onClick={() => void run(async () => {
            const result = await authRequest<{ message: string }>('/api/settings/ciam-sso/test-connection', 'POST')
            setMessage(result.message)
          })}>ทดสอบการเชื่อมต่อที่บันทึกไว้</button></div></fieldset>
        </form>
        <p>Session ที่ออกใหม่ใช้เวลาที่ตั้งไว้ การระงับผู้ใช้จาก CIAM จะมีผลเมื่อยืนยันตัวตนใหม่ ส่วนการปิดบัญชีที่นี่มีผลทันที</p>
        <fieldset disabled={busy}><legend>โหมดฉุกเฉิน: {cfg.ciam_break_glass_active ? 'เปิด' : 'ปิด'}</legend>
          <label>เหตุผล<input value={reason} maxLength={300} onChange={e => setReason(e.target.value)} /></label>
          <button type="button" disabled={reason.trim().length < 5} onClick={() => void run(async () => {
            setCfg(await authRequest<Config>('/api/auth/sso/break-glass-toggle', 'POST', { active: !cfg.ciam_break_glass_active, reason }))
            setReason(''); setMessage('บันทึกโหมดฉุกเฉินและ Audit แล้ว')
          })}>{cfg.ciam_break_glass_active ? 'ปิดโหมดฉุกเฉิน' : 'เปิดโหมดฉุกเฉิน'}</button>
        </fieldset>
        <details><summary>เปลี่ยนรหัสผ่าน Local Admin ของตนเอง</summary>
          <form className="ciam-form" onSubmit={e => { e.preventDefault(); void run(async () => {
            const value = await authRequest<LoginSession>('/api/settings/ciam-sso/local-password', 'POST', { current_password: currentPassword, new_password: newPassword })
            setSessionToken(value.csrf_token); setCurrentPassword(''); setNewPassword(''); setMessage('เปลี่ยนรหัสผ่านแล้ว Session เก่าถูกยกเลิก')
          }) }}>
            <label>รหัสผ่านปัจจุบัน<input type="password" autoComplete="current-password" required value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>
            <label>รหัสผ่านใหม่<input type="password" autoComplete="new-password" minLength={12} maxLength={256} required value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label>
            <button disabled={busy}>เปลี่ยนรหัสผ่าน</button>
          </form>
        </details>
        <p>AD ใช้ได้เฉพาะโหมดฉุกเฉินและบัญชีที่ผูกไว้ การปิดโหมดฉุกเฉินหรือเปลี่ยนค่า Gateway จะยกเลิก AD Session</p>
        <h3>ผู้ใช้และสิทธิ์</h3><p>การเปลี่ยนสิทธิ์หรือสถานะจะยกเลิก Session ของผู้ใช้นั้น</p>
        <div className="ciam-users"><table><thead><tr><th>ผู้ใช้</th><th>สิทธิ์</th><th>สถานะ</th><th>AD username</th><th>บันทึก</th></tr></thead><tbody>
          {users.map(user => <UserRow key={user.id} user={user} busy={busy} bind={username => void run(async () => {
            await authRequest(`/api/settings/ciam-sso/users/${user.id}/ad-binding`, 'PUT', { username })
            await load(); setMessage('บันทึกบัญชี AD แล้ว')
          })} save={value => void run(async () => {
            await authRequest(`/api/settings/ciam-sso/users/${user.id}`, 'PATCH', value)
            await load(); setMessage('บันทึกผู้ใช้แล้ว')
          })} />)}
          {users.length === 0 && <tr><td colSpan={5}>ยังไม่มีผู้ใช้เข้าสู่ระบบ</td></tr>}
        </tbody></table></div>
      </>}
    </>}
  </section>
}
function UserRow({ user, busy, save, bind }: { user: AuthUser; busy: boolean; bind: (username: string) => void; save: (value: { role: string; active: boolean }) => void }) {
  const [role, setRole] = useState(user.role)
  const [active, setActive] = useState(user.active)
  const [adUsername, setAdUsername] = useState(user.ad_username ?? '')
  return <tr><td>{user.full_name}<br /><small>{user.username}{user.local ? ' · Local Admin' : ''}</small></td>
    <td><select aria-label={`สิทธิ์ ${user.username}`} value={role} disabled={busy || user.local} onChange={e => setRole(e.target.value as AuthUser['role'])}><option value="viewer">Viewer</option><option value="operator">Data Operator</option><option value="admin">System Admin</option></select></td>
    <td><select aria-label={`สถานะ ${user.username}`} value={String(active)} disabled={busy || user.local} onChange={e => setActive(e.target.value === 'true')}><option value="true">ใช้งาน</option><option value="false">ระงับ</option></select></td>
    <td>{user.local ? '—' : <div className="ciam-ad-binding"><input aria-label={`AD username ${user.username}`} value={adUsername} maxLength={200} disabled={busy} onChange={e => setAdUsername(e.target.value)} /><button disabled={busy || adUsername.trim().toLowerCase() === (user.ad_username ?? '')} onClick={() => bind(adUsername)}>บันทึก AD {user.username}</button><small>เว้นว่างเพื่อลบการผูกบัญชี</small></div>}</td>
    <td><button disabled={busy || user.local || (role === user.role && active === user.active)} onClick={() => save({ role, active })}>บันทึก {user.username}</button></td></tr>
}
