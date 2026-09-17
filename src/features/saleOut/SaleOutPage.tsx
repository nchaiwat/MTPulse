import { useEffect, useMemo, useState } from 'react'
import { CalendarRange, CircleAlert, RefreshCw } from 'lucide-react'
import { fetchSaleOutReport } from './saleOutApi'
import { SaleOutComparisonLedger } from './SaleOutComparisonLedger'
import type { SaleOutBasis, SaleOutFilters, SaleOutMetric, SaleOutModernTrade, SaleOutReport, SaleOutState, SaleOutValue } from './types'
import './sale-out.css'

const exact = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

const stateLabels: Record<SaleOutState, string> = {
  value: '',
  zero: '0',
  missing: 'ไม่มีข้อมูล',
  future: 'ยังไม่ถึงช่วง',
  unavailable: 'ไม่พร้อม',
  incomplete: 'ข้อมูลไม่ครบ',
}

const statusLabels: Record<string, string> = {
  ready: 'พร้อม',
  incomplete: 'ข้อมูลไม่ครบ',
  unavailable: 'ยังไม่พร้อม',
  missing: 'ไม่มีข้อมูล',
  missing_start_date: 'ยังไม่กำหนดวันเริ่ม',
  excluded: 'ไม่รวมใน Total',
}

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

function formatCompact(value: number | null, metric: SaleOutMetric) {
  if (value === null) return '—'
  if (metric === 'amount') {
    if (Math.abs(value) >= 1_000_000) return `${exact.format(value / 1_000_000)} ล.`
    if (Math.abs(value) >= 1_000) return `${exact.format(value / 1_000)} พัน`
  }
  return exact.format(value)
}

function formatValue(entry: SaleOutValue, metric: SaleOutMetric, compact = false) {
  if (entry.value !== null && (entry.state === 'value' || entry.state === 'zero' || entry.state === 'incomplete')) {
    return compact ? formatCompact(entry.value, metric) : exact.format(entry.value)
  }
  return stateLabels[entry.state] || '—'
}

function formatPercent(value: number | null) {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
}

function tone(value: number | null) {
  if (value === null || value === 0) return 'is-neutral'
  return value > 0 ? 'is-positive' : 'is-negative'
}

function ValueCell({ entry, metric }: { entry: SaleOutValue; metric: SaleOutMetric }) {
  return (
    <span className={`saleout-value state-${entry.state}`}>
      {formatValue(entry, metric)}
      {entry.state === 'incomplete' && entry.value !== null && <small>ข้อมูลไม่ครบ</small>}
    </span>
  )
}

function Kpi({ label, value, detail, valueTone = 'is-neutral' }: { label: string; value: string; detail: string; valueTone?: string }) {
  return (
    <article className="saleout-kpi">
      <span>{label}</span>
      <strong className={valueTone}>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

export function SaleOutPage() {
  const [baseYear, setBaseYear] = useState(2025)
  const [comparisonYear, setComparisonYear] = useState(2026)
  const [salesBasis, setSalesBasis] = useState<SaleOutBasis>('gross')
  const [metric, setMetric] = useState<SaleOutMetric>('amount')
  const [cutoff, setCutoff] = useState('')
  const [selectedCodes, setSelectedCodes] = useState<string[] | null>(null)
  const [catalog, setCatalog] = useState<SaleOutModernTrade[]>([])
  const [report, setReport] = useState<SaleOutReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [showHeatmap, setShowHeatmap] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    const filters: SaleOutFilters = {
      baseYear,
      comparisonYear,
      salesBasis,
      metric,
      ...(cutoff ? { cutoff } : {}),
      ...(selectedCodes ? { mtCodes: selectedCodes } : {}),
    }
    fetchSaleOutReport(filters, controller.signal)
      .then((nextReport) => {
        setReport(nextReport)
        setError(null)
        setCatalog((current) => current.length > 0 ? current : nextReport.modernTrades)
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'ไม่สามารถโหลดรายงาน Sale Out ได้')
      })
    return () => controller.abort()
  }, [baseYear, comparisonYear, salesBasis, metric, cutoff, selectedCodes, reloadKey])

  const years = useMemo(() => Array.from(new Set([2025, 2026, ...(report?.meta.availableYears ?? [])])).sort(), [report])
  const effectiveCutoff = report?.meta.cutoff ?? cutoff

  const toggleModernTrade = (code: string) => {
    const allCodes = catalog.map((item) => item.code)
    const current = selectedCodes ?? allCodes
    const next = current.includes(code) ? current.filter((item) => item !== code) : [...current, code]
    if (next.length === 0) return
    setSelectedCodes(next.length === allCodes.length ? null : next)
  }

  return (
    <div className="saleout-page">
      <header className="saleout-intro">
        <div>
          <span className="eyebrow">REPORT SALE OUT · ทุก Modern Trade</span>
          <h1>Sale Out</h1>
          <p>ภาพรวมยอดขายบน Cut-off เดียวกัน พร้อมสถานะความพร้อมของข้อมูลแต่ละ MT</p>
        </div>
        <div className="saleout-intro-meta" aria-label="ขอบเขตรายงานปัจจุบัน">
          <span><CalendarRange size={15} aria-hidden="true" />Cut-off</span>
          <strong>{formatDate(effectiveCutoff)}</strong>
          <small>{salesBasis === 'gross' ? 'Gross' : 'Net'} · {metric === 'amount' ? 'Amount Ex.VAT' : metric === 'qty' ? 'Qty' : 'Average Price'}</small>
        </div>
      </header>

      <section className="saleout-toolbar" aria-label="ตัวกรอง Sale Out">
        <label>ปีฐาน<select aria-label="ปีฐาน" value={baseYear} onChange={(event) => setBaseYear(Number(event.target.value))}>{years.map((year) => <option key={year} value={year} disabled={year === comparisonYear}>{year}</option>)}</select></label>
        <label>ปีเปรียบเทียบ<select aria-label="ปีเปรียบเทียบ" value={comparisonYear} onChange={(event) => setComparisonYear(Number(event.target.value))}>{years.map((year) => <option key={year} value={year} disabled={year === baseYear}>{year}</option>)}</select></label>
        <fieldset><legend>Accounting basis</legend><div className="saleout-segmented"><button type="button" aria-pressed={salesBasis === 'gross'} onClick={() => setSalesBasis('gross')}>Gross</button><button type="button" aria-pressed={salesBasis === 'net'} onClick={() => setSalesBasis('net')}>Net</button></div></fieldset>
        <fieldset><legend>Metric</legend><div className="saleout-segmented"><button type="button" aria-pressed={metric === 'amount'} onClick={() => setMetric('amount')}>Amount Ex.VAT</button><button type="button" aria-pressed={metric === 'qty'} onClick={() => setMetric('qty')}>Qty</button><button type="button" aria-pressed={metric === 'average_price'} onClick={() => setMetric('average_price')}>Average Price</button></div></fieldset>
        <label>Historical Cut-off<input aria-label="Historical Cut-off" type="date" value={cutoff || report?.meta.activeCutoff || ''} max={report?.meta.activeCutoff ?? undefined} onChange={(event) => setCutoff(event.target.value)} /></label>
        <fieldset className="saleout-mt-filter"><legend>Modern Trade</legend><div>{catalog.map((item) => { const checked = selectedCodes === null || selectedCodes.includes(item.code); const lastSelected = selectedCodes !== null && selectedCodes.length === 1 && checked; return <label key={item.code}><input type="checkbox" checked={checked} disabled={lastSelected} onChange={() => toggleModernTrade(item.code)} />{item.code}</label> })}</div></fieldset>
      </section>

      {error && (
        <div className="saleout-error" role="alert"><CircleAlert size={18} aria-hidden="true" /><span><strong>โหลดรายงานไม่สำเร็จ</strong>{error}</span><button type="button" onClick={() => setReloadKey((value) => value + 1)}><RefreshCw size={15} aria-hidden="true" />ลองใหม่</button></div>
      )}
      {!report && !error && <div className="saleout-loading" role="status">กำลังจัดทำภาพรวม Sale Out…</div>}

      {report && (
        <>
          <section className="saleout-cutoff-ledger" role="region" aria-label="Common Cut-off และความสดของข้อมูล">
            <div className="saleout-cutoff-anchor"><span>COMMON CUT-OFF</span><strong>{formatDate(report.meta.cutoff)}</strong><small>{report.meta.cutoff === report.meta.activeCutoff ? 'Active reporting date' : 'Historical view'}</small></div>
            <div className="saleout-freshness-track">
              {report.modernTrades.map((item) => <div className={`saleout-freshness is-${item.status}`} key={item.code}><span><strong>{item.code}</strong><small>{item.name}</small></span><b>{formatDate(item.latestDailyDate)}</b><em>{statusLabels[item.status] ?? item.status}</em></div>)}
            </div>
          </section>

          <SaleOutComparisonLedger
            report={report}
            metric={metric}
            baseYear={baseYear}
            comparisonYear={comparisonYear}
            heatmap={showHeatmap}
            onToggleHeatmap={() => setShowHeatmap((value) => !value)}
          />

          <section className="saleout-kpi-strip" aria-label="KPI Sale Out">
            <Kpi label={`YTD ${comparisonYear}`} value={formatValue(report.kpis.comparisonYtd, metric, true)} detail={`01/01–${formatDate(report.meta.cutoff)}`} />
            <Kpi label={`YTD ${baseYear}`} value={formatValue(report.kpis.baseYtd, metric, true)} detail="ช่วงวันเดียวกันของปีก่อน" />
            <Kpi label="ผลต่าง YTD" value={formatCompact(report.kpis.difference, metric)} detail="ปีเปรียบเทียบ − ปีฐาน" valueTone={tone(report.kpis.difference)} />
            <Kpi label="YTD Growth" value={formatPercent(report.kpis.growthPercent)} detail="เทียบช่วงวันเดียวกัน" valueTone={tone(report.kpis.growthPercent)} />
            <Kpi label="เดือนล่าสุด" value={formatValue(report.kpis.latestMonth, metric, true)} detail={`MoM ${formatPercent(report.kpis.momPercent)} · YoY ${formatPercent(report.kpis.yoyPercent)}`} />
            <Kpi label="Data completeness" value={report.kpis.dataCompletenessPercent === null ? '—' : `${report.kpis.dataCompletenessPercent.toFixed(1)}%`} detail="MT ที่รวมในยอด Total" valueTone={report.kpis.dataCompletenessPercent !== null && report.kpis.dataCompletenessPercent < 100 ? 'is-warning' : 'is-positive'} />
          </section>

          <div className="saleout-analysis-grid saleout-analysis-grid--single">
            <section className="saleout-panel saleout-period-panel">
              <header><div><span className="eyebrow">PERIOD SUMMARY</span><h2>สรุปตามช่วงเวลา</h2></div></header>
              <div className="saleout-table-scroll"><table aria-label="สรุปตามช่วงเวลา"><thead><tr><th>ช่วง</th><th>{baseYear}</th><th>{comparisonYear}</th><th>Growth</th></tr></thead><tbody>{report.periods.map((period) => <tr key={period.code}><th scope="row">{period.code}</th><td><ValueCell entry={period.base} metric={metric} /></td><td><ValueCell entry={period.comparison} metric={metric} /></td><td className={tone(period.growthPercent)}>{formatPercent(period.growthPercent)}</td></tr>)}</tbody></table></div>
            </section>
          </div>

          <section className="saleout-panel">
            <header><div><span className="eyebrow">MT CONTRIBUTION</span><h2>สรุปตาม Modern Trade</h2></div><small>สถานะ “ไม่พร้อม” ไม่ถูกนำไปรวมใน Total</small></header>
            <div className="saleout-table-scroll"><table className="saleout-summary-table" aria-label="สรุป Sale Out ตาม Modern Trade"><thead><tr><th>MT</th><th>สถานะ</th><th>ข้อมูลล่าสุด</th><th>YTD {baseYear}</th><th>YTD {comparisonYear}</th><th>ผลต่าง</th><th>YTD Growth</th><th>MoM</th><th>YoY</th></tr></thead><tbody>{report.modernTrades.map((item) => <tr key={item.code}><th scope="row"><strong>{item.code}</strong><small>{item.name}</small></th><td><span className={`saleout-status is-${item.status}`}>{statusLabels[item.status] ?? item.status}</span></td><td>{formatDate(item.latestDailyDate)}</td><td><ValueCell entry={item.baseYtd} metric={metric} /></td><td><ValueCell entry={item.comparisonYtd} metric={metric} /></td><td className={tone(item.difference)}>{item.difference === null ? '—' : formatCompact(item.difference, metric)}</td><td className={tone(item.growthPercent)}>{formatPercent(item.growthPercent)}</td><td className={tone(item.momPercent)}>{formatPercent(item.momPercent)}</td><td className={tone(item.yoyPercent)}>{formatPercent(item.yoyPercent)}</td></tr>)}</tbody><tfoot><tr><th scope="row">Total<small>เฉพาะ MT ที่พร้อมรวม</small></th><td colSpan={2}>Cut-off {formatDate(report.meta.cutoff)}</td><td><ValueCell entry={report.kpis.baseYtd} metric={metric} /></td><td><ValueCell entry={report.kpis.comparisonYtd} metric={metric} /></td><td className={tone(report.kpis.difference)}>{formatCompact(report.kpis.difference, metric)}</td><td className={tone(report.kpis.growthPercent)}>{formatPercent(report.kpis.growthPercent)}</td><td className={tone(report.kpis.momPercent)}>{formatPercent(report.kpis.momPercent)}</td><td className={tone(report.kpis.yoyPercent)}>{formatPercent(report.kpis.yoyPercent)}</td></tr></tfoot></table></div>
          </section>

        </>
      )}
    </div>
  )
}
