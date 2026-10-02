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
    <p>ประวัติการเข้าสู่ระบบและการจัดการระบบ · เวลาแสดงตามเขตเวลาของเครื่อง</p>
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
      <div className="ciam-users"><table><caption className="sr-only">ประวัติการทำรายการระบบ</caption><thead><tr><th>เวลา</th><th>เหตุการณ์</th><th>ผลลัพธ์</th><th>ผู้ทำรายการ</th><th>รายละเอียด</th></tr></thead><tbody>
        {result.items.map(log => <tr key={log.id}><td>{new Date(log.created_at).toLocaleString('th-TH')}</td><td><strong>{log.event_code}</strong><br />{log.message}<br /><small>{log.category}</small></td><td>{log.status ? statusNames[log.status] || log.status : 'ไม่ระบุ (Legacy)'}</td><td>{log.triggered_by}</td><td><details><summary>ดูรายละเอียด #{log.id}</summary><p>จำนวนรายการ: {log.records_count ?? '—'} · เวลา: {log.duration_ms ?? '—'} ms</p><pre className="transaction-details">{JSON.stringify(log.details, null, 2)}</pre></details></td></tr>)}
        {result.items.length === 0 && <tr><td colSpan={5}>ไม่พบประวัติในเงื่อนไขนี้</td></tr>}
      </tbody></table></div>
      <div className="ciam-actions"><button disabled={page === 1} onClick={() => { setBusy(true); setPage(page - 1) }}>ก่อนหน้า</button><button disabled={page * result.page_size >= result.total} onClick={() => { setBusy(true); setPage(page + 1) }}>ถัดไป</button></div>
    </>}
  </section>
}
