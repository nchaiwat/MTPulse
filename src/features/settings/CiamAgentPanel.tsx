import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { authRequest } from '../auth/authApi'

type Config = { enabled: boolean; app_code: string; key_configured: boolean; pending_results: number;
  last_success?: string; last_attempt?: string; last_full_sync?: string; next_attempt?: string;
  last_error?: string | null; api_status?: string }
const date = (value?: string) => value ? new Date(value).toLocaleString('th-TH', { calendar: 'gregory' }) : 'ยังไม่มีข้อมูล'
export function CiamAgentPanel({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [key, setKey] = useState('')
  const [revealed, setRevealed] = useState('')
  const [editing, setEditing] = useState(false)
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => {
    let current = true
    void authRequest<Config>('/api/settings/ciam-agent').then(value => { if (current) setCfg(value) })
      .catch(reason => { if (current) setError(reason instanceof Error ? reason.message : 'โหลด Agent ไม่สำเร็จ') })
    return () => { current = false }
  }, [])
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('')
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'ทำรายการไม่สำเร็จ') }
    finally { setBusy(false) }
  }
  return <section aria-labelledby="agent-heading">
    <h3 id="agent-heading">Outbound Agent · Mode C</h3>
    <p>ส่ง Heartbeat ทุก 120 วินาที และรายชื่อบัญชีเมื่อมีการเปลี่ยนแปลงหรือครบ 24 ชั่วโมง ใช้ CIAM Base URL และ Client ID ที่บันทึกไว้ด้านบน</p>
    {error && <p role="alert" className="auth-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!cfg && <button type="button" disabled={busy} onClick={() => void run(async () => setCfg(await authRequest<Config>('/api/settings/ciam-agent')))}>โหลดข้อมูล Agent</button>}
    {cfg && <>
      <form onSubmit={e => { e.preventDefault(); void run(async () => {
        setCfg(await authRequest<Config>('/api/settings/ciam-agent', 'PUT', { enabled: cfg.enabled, app_code: cfg.app_code, api_key: editing ? key : undefined }))
        setKey(''); setRevealed(''); setVisible(false); setEditing(false); onDirtyChange(false)
        setMessage('บันทึกแล้ว Agent จะอ่านค่าใหม่ในรอบถัดไป')
      }) }}>
        <fieldset disabled={busy}><legend>การตั้งค่า Agent</legend><div className="ciam-form">
          <label>Outbound Agent<select value={String(cfg.enabled)} onChange={e => { setCfg({ ...cfg, enabled: e.target.value === 'true' }); onDirtyChange(true) }}><option value="false">ปิด</option><option value="true">เปิด</option></select></label>
          <label>App Code<input required pattern="[a-z][a-z0-9_-]{0,49}" maxLength={50} value={cfg.app_code} onChange={e => { setCfg({ ...cfg, app_code: e.target.value }); onDirtyChange(true) }} /></label>
          <div><label>Agent API Key<input autoComplete="new-password" type={visible ? 'text' : 'password'} readOnly={!editing} value={editing ? key : revealed || (cfg.key_configured ? '********' : '')} onChange={e => { setKey(e.target.value); onDirtyChange(true) }} /></label>
            <div className="ciam-actions"><button type="button" aria-label={visible ? 'ซ่อน Agent API Key' : 'แสดง Agent API Key'} onClick={() => void run(async () => {
              if (!visible && !editing && cfg.key_configured) setRevealed((await authRequest<{ value: string }>('/api/settings/ciam-agent/reveal', 'POST')).value)
              if (visible) setRevealed('')
              setVisible(!visible)
            })}>{visible ? <EyeOff size={16} /> : <Eye size={16} />}</button><button type="button" onClick={() => { setEditing(true); setRevealed(''); setVisible(false) }}>เปลี่ยน Agent API Key</button></div>
            <small>{cfg.key_configured ? 'บันทึก Key แล้ว · เว้นว่างเพื่อคงค่าเดิม' : 'ยังไม่ได้ตั้ง Key · ใช้ค่าที่ลงทะเบียนกับ CIAM'}</small>
          </div>
        </div><div className="ciam-actions"><button>บันทึก Agent</button><button type="button" onClick={() => void run(async () => {
          const fresh = await authRequest<Config>('/api/settings/ciam-agent')
          setCfg(previous => previous ? { ...fresh, enabled: previous.enabled, app_code: previous.app_code } : fresh)
          setMessage('อัปเดตสถานะแล้ว')
        })}>รีเฟรชสถานะ Agent</button></div></fieldset>
      </form>
      <p>การติดต่อ CIAM: {cfg.last_error ? 'มีข้อผิดพลาด: ' + cfg.last_error : cfg.last_success ? 'เคยติดต่อสำเร็จ — ตรวจเวลาล่าสุดด้านล่าง' : 'ยังไม่เคยติดต่อสำเร็จ'}</p>
      <dl><dt>พยายามติดต่อล่าสุด</dt><dd>{date(cfg.last_attempt)}</dd><dt>CIAM ตอบรับล่าสุด</dt><dd>{date(cfg.last_success)}</dd><dt>Full Sync ล่าสุด</dt><dd>{date(cfg.last_full_sync)}</dd><dt>รอบถัดไป</dt><dd>{date(cfg.next_attempt)}</dd><dt>ผลคำสั่งที่ยังไม่ได้รับการตอบรับ</dt><dd>{cfg.pending_results}</dd><dt>สถานะ API ที่ตรวจล่าสุด</dt><dd>{cfg.api_status || 'ยังไม่ตรวจ'}</dd></dl>
      <p>CIAM เปิดคืนบัญชีทั่วไปได้แม้ MTPulse Admin เป็นผู้ปิด บัญชี Local Admin ฉุกเฉินได้รับการป้องกัน การระงับมีผลเมื่อ Agent รับและทำคำสั่งสำเร็จ</p>
    </>}
  </section>
}
