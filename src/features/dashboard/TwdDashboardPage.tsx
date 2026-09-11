import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  CalendarDays,
  CheckCircle2,
  Download,
  PackageSearch,
  RefreshCw,
  Store,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { MonthlyBars, RankingBars, TrendChart } from './DashboardCharts'
import { downloadDashboard, fetchDashboard } from './dashboardApi'
import type {
  DashboardMetric,
  DashboardPeriod,
  TwdDashboardResponse,
} from './types'
import './twd-dashboard.css'
import { MODERN_TRADES, type ActiveModernTradeCode } from '../../config/modernTrades'

const amount = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 0 })
const quantity = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 0 })
const monthNames = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

function percentage(value: number | null) {
  if (value === null) return '—'
  return `${value < 0 ? '(' : ''}${Math.abs(value).toFixed(1)}%${value < 0 ? ')' : ''}`
}

function dateLabel(value?: string | null) {
  if (!value) return 'ยังไม่มีข้อมูล'
  return new Intl.DateTimeFormat('th-TH', { day: '2-digit', month: 'short', year: 'numeric' })
    .format(new Date(`${value}T00:00:00`))
}

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className="change-neutral">—</span>
  const positive = value >= 0
  return (
    <span className={positive ? 'change-positive' : 'change-negative'}>
      {positive ? <TrendingUp size={14} aria-hidden="true" /> : <TrendingDown size={14} aria-hidden="true" />}
      {percentage(value)}
    </span>
  )
}

interface TwdDashboardPageProps {
  mtCode?: ActiveModernTradeCode
  onOpenReport?: () => void
}

export function TwdDashboardPage({
  mtCode = 'TWD',
  onOpenReport,
}: TwdDashboardPageProps) {
  const [period, setPeriod] = useState<DashboardPeriod>('ytd')
  const [metric, setMetric] = useState<DashboardMetric>('amount')
  const [year, setYear] = useState<number>()
  const [data, setData] = useState<TwdDashboardResponse | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadMessage, setDownloadMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    fetchDashboard(mtCode, period, year, controller.signal)
      .then((response) => {
        if (active) setData(response)
      })
      .catch((reason) => {
        if (!active || reason instanceof DOMException && reason.name === 'AbortError') return
        setError(reason instanceof Error ? reason.message : 'ไม่สามารถอ่านข้อมูล Dashboard ได้')
      })
      .finally(() => {
        if (active) setBusy(false)
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [mtCode, period, year, reloadKey])

  const dashboardName = {
    short: MODERN_TRADES[mtCode].code,
    name: MODERN_TRADES[mtCode].displayName,
  }

  if (!data && busy) {
    return (
      <div className="twd-dashboard page-content" aria-busy="true">
        <div className="dashboard-skeleton dashboard-skeleton-toolbar" />
        <div className="dashboard-skeleton dashboard-skeleton-strip" />
        <div className="dashboard-skeleton-grid">
          <div className="dashboard-skeleton" /><div className="dashboard-skeleton" />
        </div>
        <span className="sr-only" role="status">
          กำลังโหลด Dashboard {dashboardName.name}
        </span>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="twd-dashboard page-content">
        <div className="dashboard-state" role="alert">
          <AlertTriangle size={24} aria-hidden="true" />
          <div><strong>เปิด Dashboard ไม่สำเร็จ</strong><span>{error}</span></div>
          <button className="secondary-action" type="button" onClick={() => { setBusy(true); setError(null); setReloadKey((value) => value + 1) }}>ลองอีกครั้ง</button>
        </div>
      </div>
    )
  }

  const { meta, summary, monthly, topBranches, topSkus } = data
  const currentYear = meta.year ?? new Date().getFullYear()
  const previousYear = meta.previousYear ?? currentYear - 1
  const metricLabel = metric === 'amount' ? 'ยอดขาย Ex.VAT' : 'จำนวน (Qty)'
  const formatMetric = metric === 'amount' ? amount : quantity

  const handleDownload = async () => {
    setIsDownloading(true)
    setDownloadMessage(null)
    try {
      const { blob, filename } = await downloadDashboard(mtCode, period, metric, currentYear)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
      setDownloadMessage({ kind: 'success', text: 'Download Dashboard Excel ตามตัวกรองปัจจุบันแล้ว' })
    } catch (reason) {
      setDownloadMessage({
        kind: 'error',
        text: reason instanceof Error ? reason.message : 'Download Dashboard Excel ไม่สำเร็จ',
      })
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="twd-dashboard page-content" aria-busy={busy}>
      <header className="dashboard-intro">
        <div>
          <span className="eyebrow">{dashboardName.short} sales intelligence</span>
          <h2>ภาพรวม Performance ของ {dashboardName.name}</h2>
          <p>ติดตามยอดขาย แนวโน้ม สาขา และ SKU ที่สร้างผลลัพธ์ในช่วงเวลาเดียวกัน</p>
        </div>
        <div className="dashboard-intro-actions">
          <div className="dashboard-updated"><CalendarDays size={16} aria-hidden="true" /><span>ข้อมูลล่าสุด<strong>{dateLabel(meta.latestDataDate)}</strong></span></div>
          <button className="secondary-action dashboard-download" type="button" disabled={isDownloading || !summary} onClick={() => void handleDownload()}>
            <Download size={15} aria-hidden="true" />{isDownloading ? 'กำลัง Download…' : 'Download Excel'}
          </button>
          {onOpenReport && (
            <button className="secondary-action dashboard-report-link" type="button" onClick={onOpenReport}>
              เปิดรายงานรายละเอียด <ArrowRight size={15} aria-hidden="true" />
            </button>
          )}
        </div>
      </header>

      <section className="dashboard-toolbar" aria-label="ตัวกรอง Dashboard">
        <label><span>ปี</span><select value={currentYear} onChange={(event) => { setBusy(true); setError(null); setYear(Number(event.target.value)) }}>{meta.availableYears.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <fieldset><legend>ช่วงเวลา</legend>{([
          ['ytd', 'YTD'], ['h1', 'H1'], ['h2', 'H2'], ['full', 'ปีเต็ม'],
        ] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={period === value} onClick={() => { setBusy(true); setError(null); setPeriod(value) }}>{label}</button>)}</fieldset>
        <fieldset><legend>มุมมองตัวเลข</legend>{([
          ['amount', 'ยอดขาย'], ['qty', 'จำนวน'],
        ] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={metric === value} onClick={() => setMetric(value)}>{label}</button>)}</fieldset>
        {busy && <RefreshCw className="is-spinning dashboard-busy" size={17} aria-label="กำลังอัปเดตข้อมูล" />}
      </section>

      {downloadMessage && <div className={`dashboard-download-message is-${downloadMessage.kind}`} role={downloadMessage.kind === 'error' ? 'alert' : 'status'}>{downloadMessage.text}</div>}
      {error && <div className="dashboard-inline-error" role="alert"><AlertTriangle size={16} aria-hidden="true" />{error}<button type="button" onClick={() => { setBusy(true); setError(null); setReloadKey((value) => value + 1) }}>ลองอีกครั้ง</button></div>}

      {!summary ? (
        <section className="dashboard-state dashboard-empty">
          <PackageSearch size={30} aria-hidden="true" />
          <div>
            <strong>ยังไม่มีข้อมูลสำหรับ Dashboard</strong>
            <span>นำเข้าข้อมูล {dashboardName.short} แล้วกลับมาที่หน้านี้อีกครั้ง</span>
          </div>
          {onOpenReport && (
            <button className="secondary-action" type="button" onClick={onOpenReport}>
              เปิดรายงาน {dashboardName.name}
            </button>
          )}
        </section>
      ) : (
        <>
          <section className="comparison-strip" aria-label="สรุป Performance">
            <article><BarChart3 size={18} aria-hidden="true" /><span><small>ยอดขาย Ex.VAT · {currentYear}</small><strong>{amount.format(summary.currentAmount)}</strong><em>ปีก่อน {amount.format(summary.previousAmount)}</em></span></article>
            <article><TrendingUp size={18} aria-hidden="true" /><span><small>Sales YoY</small><strong><Change value={summary.amountYoY} /></strong><em>{previousYear} → {currentYear}</em></span></article>
            <article><Boxes size={18} aria-hidden="true" /><span><small>จำนวน (Qty) · {currentYear}</small><strong>{quantity.format(summary.currentQty)}</strong><em>ปีก่อน {quantity.format(summary.previousQty)}</em></span></article>
            <article><TrendingUp size={18} aria-hidden="true" /><span><small>Qty YoY</small><strong><Change value={summary.qtyYoY} /></strong><em>{previousYear} → {currentYear}</em></span></article>
            <article data-complete={meta.completenessPercent >= 95 || undefined}><CheckCircle2 size={18} aria-hidden="true" /><span><small>Data completeness</small><strong>{meta.completenessPercent.toFixed(1)}%</strong><em>{meta.loadedDays} / {meta.expectedDays} วัน</em></span></article>
          </section>

          <section className="dashboard-chart-grid">
            <article className="dashboard-panel">
              <header><div><span className="eyebrow">Monthly trend</span><h3>{metricLabel} รายเดือน</h3></div><ChartLegend currentYear={currentYear} previousYear={previousYear} /></header>
              <TrendChart rows={monthly} metric={metric} currentYear={currentYear} previousYear={previousYear} />
            </article>
            <article className="dashboard-panel">
              <header><div><span className="eyebrow">Year over year</span><h3>เปรียบเทียบรายเดือน</h3></div><ChartLegend currentYear={currentYear} previousYear={previousYear} /></header>
              <MonthlyBars rows={monthly} metric={metric} currentYear={currentYear} previousYear={previousYear} />
            </article>
          </section>

          <section className="dashboard-panel monthly-table-panel">
            <header><div><span className="eyebrow">Monthly ledger</span><h3>รายละเอียดรายเดือน</h3></div><small>หน่วยยอดขาย Ex.VAT / Qty</small></header>
            <div className="dashboard-table-scroll"><table><thead><tr><th>เดือน</th><th>ยอดขาย {previousYear}</th><th>ยอดขาย {currentYear}</th><th>YoY</th><th>MoM</th><th>Qty {previousYear}</th><th>Qty {currentYear}</th><th>Qty YoY</th></tr></thead><tbody>{monthly.map((row) => { const available = row.currentAvailable !== false; return <tr key={row.monthKey}><td>{monthNames[row.month - 1]} {currentYear}</td><td>{amount.format(row.previousAmount)}</td><td>{available ? amount.format(row.currentAmount) : '–'}</td><td><Change value={row.amountYoY} /></td><td><Change value={row.amountMoM} /></td><td>{quantity.format(row.previousQty)}</td><td>{available ? quantity.format(row.currentQty) : '–'}</td><td><Change value={row.qtyYoY} /></td></tr> })}</tbody></table></div>
          </section>

          <RankingSection title="Top 10 สาขา" eyebrow="Branch performance" icon={<Store size={18} aria-hidden="true" />} currentYear={currentYear} previousYear={previousYear} metric={metric} rows={topBranches} kind="branch" code={(row) => row.branchCode} name={(row) => row.displayName} chartName={(row) => row.mappedBranchCode ? `${row.branchName} (${row.mappedBranchCode})` : row.branchName} formatMetric={formatMetric} />
          <RankingSection title="Top 15 SKU" eyebrow="Product performance" icon={<PackageSearch size={18} aria-hidden="true" />} currentYear={currentYear} previousYear={previousYear} metric={metric} rows={topSkus} kind="sku" code={(row) => row.sku} name={(row) => row.description} chartName={(row) => row.description} formatMetric={formatMetric} />
        </>
      )}
    </div>
  )
}

function ChartLegend({ currentYear, previousYear }: { currentYear: number; previousYear: number }) {
  return <div className="chart-legend"><span><i className="current-swatch" />{currentYear}</span><span><i className="previous-swatch" />{previousYear}</span></div>
}

function RankingSection<T extends { currentAmount: number; previousAmount: number; currentQty: number; previousQty: number; amountYoY: number | null; qtyYoY: number | null }>({
  title, eyebrow, icon, currentYear, previousYear, metric, rows, kind, code, name, chartName, formatMetric,
}: {
  title: string
  eyebrow: string
  icon: ReactNode
  currentYear: number
  previousYear: number
  metric: DashboardMetric
  rows: T[]
  kind: 'branch' | 'sku'
  code: (row: T) => string
  name: (row: T) => string
  chartName: (row: T) => string
  formatMetric: Intl.NumberFormat
}) {
  const current = (row: T) => metric === 'amount' ? row.currentAmount : row.currentQty
  const previous = (row: T) => metric === 'amount' ? row.previousAmount : row.previousQty
  return (
    <section className="dashboard-panel ranking-panel">
      <header><div className="ranking-heading">{icon}<div><span className="eyebrow">{eyebrow}</span><h3>{title}</h3></div></div><ChartLegend currentYear={currentYear} previousYear={previousYear} /></header>
      <div className="ranking-content">
        <RankingBars rows={rows} metric={metric} code={code} label={chartName} change={(row) => metric === 'amount' ? row.amountYoY : row.qtyYoY} currentYear={currentYear} previousYear={previousYear} />
        <div className="dashboard-table-scroll"><table><thead><tr><th>#</th><th>{kind === 'sku' ? 'SKU' : 'รายการ'}</th>{kind === 'sku' && <th>สินค้า</th>}<th>{previousYear}</th><th>{currentYear}</th><th>YoY</th></tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td>{index + 1}</td>{kind === 'sku' ? <><td className="ranking-code">{code(row)}</td><td className="ranking-product-name">{name(row)}</td></> : <td className="ranking-branch-name">{name(row)}</td>}<td>{formatMetric.format(previous(row))}</td><td>{formatMetric.format(current(row))}</td><td><Change value={metric === 'amount' ? row.amountYoY : row.qtyYoY} /></td></tr>)}</tbody></table></div>
      </div>
    </section>
  )
}
