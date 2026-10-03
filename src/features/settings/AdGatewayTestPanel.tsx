import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { authRequest } from '../auth/authApi'

type Result = { gateway_status: string; mtpulse_status: string; message: string }
const eligibility: Record<string, string> = {
  ready: 'มีบัญชีที่ใช้งานและเปิดสิทธิ์ AD แล้ว สามารถไปลองเข้าสู่ระบบ MTPulse ได้',
  account_missing: 'ยังไม่มีบัญชีใน MTPulse กรุณาสร้างใน User Management และเปิดสิทธิ์ AD',
  disabled: 'บัญชี MTPulse ถูกระงับ',
  ad_not_enabled: 'บัญชีนี้ยังไม่ได้เปิดสิทธิ์ AD สำหรับ Username ที่ทดสอบ',
  local_account: 'เป็นบัญชี Local Admin ซึ่งแยกจากการเข้า AD',
  ambiguous: 'พบชื่อบัญชีซ้ำ กรุณาตรวจสอบ User Management',
  not_checked: 'ยังไม่ตรวจสิทธิ์ MTPulse เพราะ AD ยังยืนยันตัวตนไม่สำเร็จ',
}

export function AdGatewayTestPanel({ disabled = false }: { disabled?: boolean }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  async function test() {
    setBusy(true); setError(''); setResult(null)
    const suppliedPassword = password
    setPassword(''); setVisible(false)
    try {
      setResult(await authRequest<Result>('/api/settings/ciam-sso/test-ad-login', 'POST', { username, password: suppliedPassword }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ทดสอบ AD Gateway ไม่สำเร็จ')
    } finally { setBusy(false) }
  }
  return <section aria-labelledby="ad-test-heading">
    <h3 id="ad-test-heading">ทดสอบ AD Gateway</h3>
    <p>ใช้ URL, App ID และ Secret ที่บันทึกไว้เท่านั้น หากแก้ค่าไว้ด้านบน ให้บันทึกก่อนทดสอบ</p>
    <p>ทดสอบได้แม้ยังไม่มีบัญชีใน MTPulse โดยคงบัญชี Admin ที่กำลังใช้งานอยู่</p>
    <form onSubmit={event => { event.preventDefault(); void test() }} autoComplete="off">
      <fieldset disabled={busy || disabled}><legend>บัญชี AD สำหรับทดสอบ</legend>
        <div className="ciam-form">
          <label>AD Username<input required maxLength={200} autoComplete="off" placeholder="เช่น Chaiwat.N" value={username} onChange={event => { setUsername(event.target.value); setResult(null); setError('') }} /></label>
          <div className="ciam-secret">
            <label htmlFor="ad-test-password">AD Password</label>
            <div className="ciam-secret-input">
              <input id="ad-test-password" type={visible ? 'text' : 'password'} required maxLength={256} autoComplete="off" value={password} onChange={event => { setPassword(event.target.value); setResult(null); setError('') }} />
              <button type="button" aria-label={visible ? 'ซ่อนรหัสผ่านทดสอบ AD' : 'แสดงรหัสผ่านทดสอบ AD'} aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}</button>
            </div>
            <small>ล้างรหัสผ่านจากช่องกรอกเมื่อเริ่มทดสอบ และไม่บันทึกลง Log</small>
          </div>
        </div>
        <div className="ciam-actions"><button type="submit" disabled={!username.trim() || !password}>{busy ? 'กำลังทดสอบ…' : 'ทดสอบ AD Login'}</button></div>
      </fieldset>
    </form>
    {busy && <p role="status">กำลังตรวจสอบกับ AD Gateway…</p>}
    {error && <p role="alert" className="auth-error">{error}</p>}
    {result && <div role="status">
      <p><strong>ผล AD:</strong> {result.message}</p>
      <p><strong>สิทธิ์ MTPulse:</strong> {eligibility[result.mtpulse_status] ?? 'ไม่สามารถระบุสถานะได้'}</p>
    </div>}
  </section>
}
