import { useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  RefreshCw,
  Server,
  TableProperties,
  XCircle,
} from 'lucide-react'
import { fetchMonitoring, refreshMonitoring } from './monitoringApi'
import { formatDisplayDate, formatDisplayDateTime } from '../../shared/dateFormat'
import type { MonitoringResponse, MonitoringStatus } from './types'
import './monitoring.css'

const integer = new Intl.NumberFormat('th-TH')
const decimal = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

function formatBytes(value: number) {
  if (value < 1024) return `${integer.format(value)} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let amount = value / 1024
  let index = 0
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024
    index += 1
  }
  return `${decimal.format(amount)} ${units[index]}`
}


function statusLabel(status: MonitoringStatus) {
  if (status === 'healthy') return 'ปกติ'
  if (status === 'warning') return 'ควรตรวจสอบ'
  return 'ผิดปกติ'
}

function importStatus(status: string) {
  if (status === 'imported') return 'สำเร็จ'
  if (status === 'imported_with_warnings') return 'สำเร็จพร้อมคำเตือน'
  return status
}

function triggerLabel(trigger: string) {
  if (trigger === 'import') return 'หลัง Import'
  if (trigger === 'manual_refresh') return 'Refresh'
  return 'เปิดหน้า'
}

function StatusIcon({ status }: { status: MonitoringStatus }) {
  if (status === 'healthy') return <CheckCircle2 size={18} aria-hidden="true" />
  if (status === 'warning') return <AlertTriangle size={18} aria-hidden="true" />
  return <XCircle size={18} aria-hidden="true" />
}

interface MonitoringPageProps {
  onOpenImports?: (batchId: number) => void
  onOpenCoverage?: () => void
}

export function MonitoringPage({ onOpenImports, onOpenCoverage }: MonitoringPageProps) {
  const [data, setData] = useState<MonitoringResponse | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async (manual = false) => {
    setBusy(true)
    setError(null)
    try {
      setData(manual ? await refreshMonitoring() : await fetchMonitoring())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ไม่สามารถอ่านสถานะระบบได้')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchMonitoring(controller.signal)
      .then(setData)
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setError(reason instanceof Error ? reason.message : 'ไม่สามารถอ่านสถานะระบบได้')
      })
      .finally(() => setBusy(false))
    return () => controller.abort()
  }, [])

  if (!data && busy) {
    return <div className="monitoring-page page-content"><div className="monitoring-loading" role="status">กำลังตรวจสอบระบบ…</div></div>
  }

  if (!data) {
    return (
      <div className="monitoring-page page-content">
        <div className="monitoring-error" role="alert">
          <AlertTriangle size={20} aria-hidden="true" />
          <div><strong>เปิดหน้า Monitoring ไม่สำเร็จ</strong><span>{error}</span></div>
          <button className="secondary-action" type="button" onClick={() => void load()}>ลองอีกครั้ง</button>
        </div>
      </div>
    )
  }

  const current = data.current
  const latestImport = current.latestImport

  return (
    <div className="monitoring-page page-content">
      <header className="monitoring-intro">
        <div>
          <span className="eyebrow">System health</span>
          <h2>สถานะระบบ</h2>
          <p>ตรวจสอบ API, PostgreSQL, ข้อมูลล่าสุด และภาระของฐานข้อมูลในจุดเดียว</p>
        </div>
        <div className="monitoring-refresh">
          <span>ตรวจล่าสุด <time>{formatDisplayDateTime(current.capturedAt)}</time></span>
          <button className="secondary-action" type="button" disabled={busy} onClick={() => void load(true)}>
            <RefreshCw size={15} aria-hidden="true" className={busy ? 'is-spinning' : undefined} />
            {busy ? 'กำลังตรวจสอบ…' : 'Refresh'}
          </button>
        </div>
      </header>

      {error && <div className="monitoring-inline-error" role="alert">{error}</div>}

      <section className="monitoring-health-ledger" aria-label="สรุปสถานะระบบ">
        <article data-status={current.overallStatus}>
          <StatusIcon status={current.overallStatus} />
          <span><small>ภาพรวมระบบ</small><strong>{statusLabel(current.overallStatus)}</strong></span>
        </article>
        <article data-status={current.api.status}>
          <Server size={18} aria-hidden="true" />
          <span><small>API</small><strong>{statusLabel(current.api.status)}</strong></span>
        </article>
        <article data-status={current.database.status}>
          <Database size={18} aria-hidden="true" />
          <span><small>PostgreSQL</small><strong>{statusLabel(current.database.status)}</strong></span>
        </article>
        <article data-status={current.latestDataDate ? 'healthy' : 'warning'}>
          <Clock3 size={18} aria-hidden="true" />
          <span><small>วันที่ข้อมูลล่าสุด</small><strong>{formatDisplayDate(current.latestDataDate, 'ยังไม่มีข้อมูล')}</strong><em>{latestImport ? `Import ล่าสุด: ${importStatus(latestImport.status)}` : 'ยังไม่มี Import'}</em></span>
        </article>
        <article data-status={current.notices.length ? 'warning' : 'healthy'}>
          <AlertTriangle size={18} aria-hidden="true" />
          <span><small>รายการที่ต้องดู</small><strong>{integer.format(current.notices.length)} รายการ</strong></span>
        </article>
      </section>

      <div className="monitoring-grid">
        <section className="monitoring-panel monitoring-database" aria-labelledby="database-heading">
          <header><Database size={18} aria-hidden="true" /><div><span className="eyebrow">Database</span><h3 id="database-heading">PostgreSQL และ Fact table</h3></div></header>
          <dl>
            <div><dt>Fact records</dt><dd>{integer.format(current.database.factCount)}</dd></div>
            <div><dt>Database size</dt><dd>{formatBytes(current.database.databaseSizeBytes)}</dd></div>
            <div><dt>Fact table</dt><dd>{formatBytes(current.database.factTableSizeBytes)}</dd></div>
            <div><dt>Fact indexes</dt><dd>{formatBytes(current.database.factIndexesSizeBytes)}</dd></div>
            <div><dt>Connections</dt><dd>{integer.format(current.database.currentConnections)} / {integer.format(current.database.maxConnections)}</dd></div>
            <div><dt>Dead tuples</dt><dd>{integer.format(current.database.deadTupleCount)} <small>({decimal.format(current.database.deadTupleRatio)}%)</small></dd></div>
            <div><dt>Vacuum ล่าสุด</dt><dd>{formatDisplayDateTime(current.database.lastVacuumAt, 'ยังไม่มีข้อมูล')}</dd></div>
            <div><dt>Analyze ล่าสุด</dt><dd>{formatDisplayDateTime(current.database.lastAnalyzeAt, 'ยังไม่มีข้อมูล')}</dd></div>
          </dl>
        </section>

        <section className="monitoring-panel monitoring-notices" aria-labelledby="notice-heading">
          <header><Activity size={18} aria-hidden="true" /><div><span className="eyebrow">Attention</span><h3 id="notice-heading">สิ่งที่ควรตรวจสอบ</h3></div></header>
          <div className="monitoring-notice-list">
            {current.notices.length === 0 && <p className="monitoring-clear"><CheckCircle2 size={17} aria-hidden="true" />ไม่พบเหตุการณ์ที่ต้องตรวจสอบ</p>}
            {current.notices.map((notice) => (
              <article key={`${notice.title}-${notice.detail}`} data-status={notice.level}>
                <StatusIcon status={notice.level} />
                <span><strong>{notice.title}</strong><small>{notice.detail}</small></span>
                {notice.code === 'import_warning' && notice.batchId && onOpenImports && (
                  <button className="monitoring-notice-action" type="button" onClick={() => onOpenImports(notice.batchId!)}>ดำเนินการแก้ไข</button>
                )}
                {notice.code === 'data_delayed' && onOpenCoverage && (
                  <button className="monitoring-notice-action" type="button" onClick={onOpenCoverage}>ตรวจวันที่ขาด</button>
                )}
              </article>
            ))}
          </div>
          <div className="monitoring-mt-list">
            <strong>ข้อมูลตาม Modern Trade</strong>
            {current.modernTrades.map((mt) => (
              <span key={mt.code}><b>{mt.code}</b>{mt.name}<time>{formatDisplayDate(mt.latestDataDate, 'ยังไม่มีข้อมูล')}</time></span>
            ))}
          </div>
        </section>
      </div>

      <section className="monitoring-panel monitoring-query-panel" aria-labelledby="query-heading">
        <header>
          <TableProperties size={18} aria-hidden="true" />
          <div><span className="eyebrow">Query workload</span><h3 id="query-heading">Top 10 Query ที่ใช้เวลารวมสูงสุด</h3></div>
          <small>{current.pgStatStatementsAvailable ? 'เรียงตาม Total time' : 'pg_stat_statements ยังไม่พร้อม'}</small>
        </header>
        <div className="monitoring-table-scroll">
          <table>
            <thead><tr><th>Query</th><th>Calls</th><th>Avg ms</th><th>Total ms</th><th>Rows</th></tr></thead>
            <tbody>
              {current.slowQueries.length === 0 && <tr><td colSpan={5} className="monitoring-table-empty">ยังไม่มี Query statistics</td></tr>}
              {current.slowQueries.map((query, index) => (
                <tr key={`${index}-${query.query}`}>
                  <td><code title={query.query}>{query.query}</code></td>
                  <td>{integer.format(query.calls)}</td>
                  <td>{decimal.format(query.meanTimeMs)}</td>
                  <td>{decimal.format(query.totalTimeMs)}</td>
                  <td>{integer.format(query.rows)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="monitoring-panel monitoring-history-panel" aria-labelledby="history-heading">
        <header><Clock3 size={18} aria-hidden="true" /><div><span className="eyebrow">Daily snapshot</span><h3 id="history-heading">ประวัติสถานะรายวัน</h3></div><small>เก็บย้อนหลัง 365 วัน</small></header>
        <div className="monitoring-table-scroll">
          <table>
            <thead><tr><th>วันที่</th><th>สถานะ</th><th>Fact records</th><th>Database</th><th>Dead tuple</th><th>Connections</th><th>วันที่ข้อมูลล่าสุด</th><th>บันทึกโดย</th></tr></thead>
            <tbody>
              {data.history.map((item) => (
                <tr key={item.date}>
                  <td>{formatDisplayDate(item.date, 'ยังไม่มีข้อมูล')}</td>
                  <td><span className="monitoring-status-text" data-status={item.status}>{statusLabel(item.status)}</span></td>
                  <td>{integer.format(item.factCount)}</td>
                  <td>{formatBytes(item.databaseSizeBytes)}</td>
                  <td>{decimal.format(item.deadTupleRatio)}%</td>
                  <td>{integer.format(item.connections)}</td>
                  <td>{formatDisplayDate(item.latestDataDate, 'ยังไม่มีข้อมูล')}</td>
                  <td>{triggerLabel(item.trigger)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
