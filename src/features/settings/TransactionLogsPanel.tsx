import { useEffect, useState } from 'react'
import { authRequest } from '../auth/authApi'
import '../auth/auth.css'

type Log = {
  id: number; event_code: string; category: string | null; action: string; status: string | null;
  message: string; triggered_by: string; created_at: string; details: Record<string, unknown>;
  records_count: number | null; duration_ms: number | null;
}
type Result = { items: Log[]; total: number; page: number; page_size: number }
const empty = { date_from: '', date_to: '', category: '', status: '', triggered_by: '', legacy: false }
const statusNames: Record<string, string> = { success: 'สำเร็จ', failed: 'ล้มเหลว', warning: 'คำเตือน', info: 'ข้อมูล' }

const field = (log: Log, key: string) => typeof log.details[key] === 'string' ? log.details[key] as string : ''
const gatewayResults: Record<string, string> = {
  success: 'AD ยืนยันตัวตนสำเร็จ', rejected: 'AD ไม่ยืนยันตัวตน', timeout: 'AD Gateway หมดเวลารอ',
  rate_limited: 'AD Gateway จำกัดจำนวนครั้ง', not_configured: 'ยังตั้งค่า AD ไม่ครบ',
  settings_changed: 'การตั้งค่าเปลี่ยนระหว่างทดสอบ ต้องทดสอบใหม่',
  invalid_username: 'รูปแบบบัญชีไม่ถูกต้อง', unavailable: 'AD Gateway ไม่พร้อมใช้งาน',
}
const accountResults: Record<string, string> = {
  ready: 'มีสิทธิ์เข้า MTPulse', account_missing: 'ไม่มีบัญชีใน MTPulse', disabled: 'บัญชี MTPulse ถูกปิด',
  ad_not_enabled: 'บัญชียังไม่เปิดใช้ AD', ambiguous: 'พบบัญชีซ้ำ ต้องตรวจสอบ',
  local_account: 'บัญชี Local ใช้ AD ไม่ได้', not_checked: 'ยังไม่ได้ตรวจสิทธิ์ MTPulse',
}
function LogRow({ log }: { log: Log }) {
  const adTest = log.action === 'ad_gateway_test'
  const target = field(log, 'tested_username')
  return <tr>
    <td><time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString('th-TH', { calendar: 'gregory', hour12: false })}</time></td>
    <td>{log.triggered_by}</td>
    <td><strong>{log.event_code}</strong><br />{adTest ? 'ทดสอบบัญชี AD: ' + (target || 'ไม่ได้บันทึกบัญชี') : log.message}<br /><small>{log.category}</small>{adTest && <p>ทดสอบการยืนยันตัวตน ไม่ได้สร้าง Session เข้าระบบ</p>}</td>
    <td>{adTest ? <><span>{gatewayResults[field(log, 'gateway_status')] || 'ไม่มีผล AD ที่บันทึกไว้'}</span><br /><span>{accountResults[field(log, 'mtpulse_status')] || 'ไม่มีผลสิทธิ์ MTPulse ที่บันทึกไว้'}</span></> : log.status ? statusNames[log.status] || log.status : 'ไม่ระบุ (Legacy)'}</td>
    <td>{field(log, 'ip') ? <><span>{field(log, 'ip_source') === 'trusted_proxy' ? 'IP ผู้ใช้' : 'IP ที่ Server เห็น (อาจเป็น Proxy)'}</span><br />{field(log, 'ip')}</> : 'ไม่ได้บันทึก IP'}{adTest && <p>ปลายทาง: {field(log, 'gateway') || 'ไม่ได้บันทึกปลายทาง'}</p>}</td>
    <td><details><summary>ดูรายละเอียด #{log.id}</summary>
      <p>คำขอ: {field(log, 'request_method') || '—'} {field(log, 'request_path') || '—'}</p>
      <p>วิธียืนยันตัวตน: {field(log, 'auth_method') || field(log, 'provider') || '—'} · App ID: {field(log, 'app_id') || '—'}</p>
      <p>IP ที่เชื่อมต่อ Server: {field(log, 'peer_ip') || '—'}</p>
      <p>จำนวนรายการ: {log.records_count ?? '—'} · เวลาประมวลผล: {log.duration_ms ?? '—'} ms</p>
      <pre className="transaction-details">{JSON.stringify(log.details, null, 2)}</pre>
    </details></td>
  </tr>
}

export function TransactionLogsPanel() {
  const [draft, setDraft] = useState(empty)
  const [filters, setFilters] = useState(empty)
  const [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let current = true
    const query = new URLSearchParams({ page: String(page), page_size: '25', legacy: String(filters.legacy) })
    for (const key of ['category', 'status', 'triggered_by', 'date_from', 'date_to'] as const) {
      if (!filters[key] || (filters.legacy && (key === 'category' || key === 'status'))) continue
      query.set(key, key.startsWith('date_') ? new Date(filters[key]).toISOString() : filters[key])
    }
    void authRequest<Result>('/api/settings/transaction-logs?' + query).then(data => {
      if (current) { setResult(data); setError('') }
    }).catch(reason => { if (current) { setError(reason instanceof Error ? reason.message : 'โหลด Log ไม่สำเร็จ'); setResult(null) } })
      .finally(() => { if (current) setBusy(false) })
    return () => { current = false }
  }, [filters, page, revision])
  const reload = () => { setBusy(true); setError(''); setRevision(value => value + 1) }
  return <section className="ciam-panel" aria-labelledby="transaction-heading">
    <h2 id="transaction-heading">Transaction Logs</h2>
    <p>ประวัติการเข้าสู่ระบบและการจัดการระบบ · เวลาแสดงตามเขตเวลาของเครื่อง ({Intl.DateTimeFormat().resolvedOptions().timeZone}) · ค.ศ.</p>
    <form className="ciam-form" onSubmit={event => { event.preventDefault(); setBusy(true); setFilters({ ...draft }); setPage(1) }}>
      <label>ตั้งแต่<input type="datetime-local" value={draft.date_from} onChange={e => setDraft({ ...draft, date_from: e.target.value })} /></label>
      <label>ถึง<input type="datetime-local" min={draft.date_from || undefined} value={draft.date_to} onChange={e => setDraft({ ...draft, date_to: e.target.value })} /></label>
      <label>หมวดหมู่<select disabled={draft.legacy} value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}><option value="">ทั้งหมด</option>{['ciam_sso', 'security_break_glass', 'system_setting', 'authentication', 'user_management'].map(value => <option key={value}>{value}</option>)}</select></label>
      <label>ผลลัพธ์<select disabled={draft.legacy} value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })}><option value="">ทั้งหมด</option>{Object.entries(statusNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>ผู้ทำรายการ<input maxLength={220} value={draft.triggered_by} onChange={e => setDraft({ ...draft, triggered_by: e.target.value })} /></label>
      <label>แหล่งประวัติ<select value={String(draft.legacy)} onChange={e => setDraft({ ...draft, legacy: e.target.value === 'true' })}><option value="false">Transaction Logs</option><option value="true">ประวัติ CIAM เดิม (Legacy)</option></select></label>
      <div className="ciam-actions"><button disabled={busy}>ค้นหา</button><button type="button" disabled={busy} onClick={reload}>รีเฟรช</button></div>
    </form>
    {filters.legacy && <p>ประวัติเดิมไม่มีข้อมูล IP และสถานะครบถ้วน แสดงเฉพาะข้อมูลที่ยืนยันได้</p>}
    {busy && <p role="status">กำลังโหลด…</p>}
    {error && <p role="alert" className="auth-error">{error} <button onClick={reload}>ลองใหม่</button></p>}
    {!busy && result && <>
      <p role="status">พบ {result.total.toLocaleString()} รายการ · หน้า {result.page}</p>
      <div className="ciam-users transaction-log-table"><table><caption className="sr-only">ประวัติการทำรายการระบบ</caption><thead><tr><th>เวลา</th><th>ผู้ทำรายการ</th><th>เหตุการณ์ / บัญชีเป้าหมาย</th><th>ผลลัพธ์</th><th>ต้นทาง / ปลายทาง</th><th>รายละเอียด</th></tr></thead><tbody>
        {result.items.map(log => <LogRow key={log.id} log={log} />)}
        {result.items.length === 0 && <tr><td colSpan={6}>ไม่พบประวัติในเงื่อนไขนี้</td></tr>}
      </tbody></table></div>
      <div className="ciam-actions"><button disabled={page === 1} onClick={() => { setBusy(true); setPage(page - 1) }}>ก่อนหน้า</button><button disabled={page * result.page_size >= result.total} onClick={() => { setBusy(true); setPage(page + 1) }}>ถัดไป</button></div>
    </>}
  </section>
}
