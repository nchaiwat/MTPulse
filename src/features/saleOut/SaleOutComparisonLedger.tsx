import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import type { SaleOutMetric, SaleOutModernTrade, SaleOutReport, SaleOutValue } from './types'

const months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
const exact = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

const stateLabels: Record<SaleOutValue['state'], string> = {
  value: '',
  zero: '0',
  missing: 'ไม่มีข้อมูล',
  future: 'ยังไม่ถึงช่วง',
  unavailable: 'ไม่พร้อม',
  incomplete: 'ข้อมูลไม่ครบ',
}

function displayValue(entry: SaleOutValue, metric: SaleOutMetric) {
  if (entry.value !== null && ['value', 'zero', 'incomplete'].includes(entry.state)) {
    if (metric === 'amount' && Math.abs(entry.value) >= 1_000_000) return `${exact.format(entry.value / 1_000_000)} ล.`
    return exact.format(entry.value)
  }
  return stateLabels[entry.state] || '—'
}

function displayPercent(value: number | null) {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
}

function heatTone(value: number | null) {
  if (value === null) return 'unavailable'
  if (value < 0) return 'negative'
  if (value < 2) return 'low'
  if (value < 10) return 'medium'
  return 'high'
}

function intensityTone(value: number | null, values: Array<number | null>) {
  if (value === null) return 'unavailable'
  const available = values.filter((candidate): candidate is number => candidate !== null)
  if (available.length < 2) return 'neutral'
  const minimum = Math.min(...available)
  const maximum = Math.max(...available)
  if (minimum === maximum) return 'neutral'
  const position = (value - minimum) / (maximum - minimum)
  if (position < 0.34) return 'low'
  if (position < 0.67) return 'medium'
  return 'high'
}

function unavailableFor(item: SaleOutModernTrade): SaleOutValue {
  return item.status === 'unavailable' || item.status === 'excluded' || item.status === 'missing_start_date'
    ? { state: 'unavailable', value: null }
    : { state: 'missing', value: null }
}

function comparableRunRate(item: Pick<SaleOutModernTrade, 'latestMonth' | 'momPercent'>) {
  const current = item.latestMonth.value
  const growth = item.momPercent
  if (current === null || growth === null || growth === -100) return null
  return current / (1 + growth / 100)
}

function HeatCell({
  value,
  label,
  heatmap,
  tone,
  children,
}: {
  value: number | null
  label: string
  heatmap: boolean
  tone?: string
  children?: ReactNode
}) {
  const heat = tone ?? heatTone(value)
  return (
    <td
      aria-label={`${label} ${children ? '' : displayPercent(value)}`.trim()}
      className="saleout-heat-cell"
      data-heat-enabled={heatmap ? 'true' : 'false'}
      data-heat-tone={heat}
    >
      {children ?? displayPercent(value)}
    </td>
  )
}

function LedgerRow({
  item,
  metric,
  heatmap,
}: {
  item: SaleOutModernTrade
  metric: SaleOutMetric
  heatmap: boolean
}) {
  const fallback = unavailableFor(item)
  const byMonth = new Map(item.monthly.map((entry) => [entry.month, entry]))
  const monthRows = months.map((_, index) => byMonth.get(index + 1))
  const baseValues = monthRows.map((entry) => entry?.base.value ?? null)
  const comparisonValues = monthRows.map((entry) => entry?.comparison.value ?? null)
  const runRate = comparableRunRate(item)
  const runRateDiff = item.latestMonth.value !== null && runRate !== null ? item.latestMonth.value - runRate : null

  return (
    <tr>
      <th scope="row" className="saleout-ledger-identity">
        <strong>{item.code}</strong>
        <small>{item.name}</small>
        <em>{item.status === 'ready' ? 'พร้อม' : item.status === 'incomplete' ? 'ข้อมูลไม่ครบ' : 'ไม่พร้อม'}</em>
      </th>
      {months.map((month, index) => {
        const entry = monthRows[index]?.base ?? fallback
        return (
          <HeatCell
            key={`base-${month}`}
            value={null}
            label={`${month} ${displayValue(entry, metric)}`}
            heatmap={heatmap}
            tone={intensityTone(entry.value, baseValues)}
          >
            <span>{displayValue(entry, metric)}</span>
          </HeatCell>
        )
      })}
      <td className="saleout-ledger-total">{displayValue(item.baseYtd, metric)}</td>
      {months.map((month, index) => {
        const entry = monthRows[index]
        const comparison = entry?.comparison ?? fallback
        return (
          <HeatCell
            key={`comparison-${month}`}
            value={entry?.growthPercent ?? null}
            label={`${month} ${displayValue(comparison, metric)} เติบโต ${displayPercent(entry?.growthPercent ?? null)}`}
            heatmap={heatmap}
            tone={intensityTone(comparison.value, comparisonValues)}
          >
            <span>{displayValue(comparison, metric)}</span>
            {entry?.growthPercent !== null && entry?.growthPercent !== undefined && (
              <small data-growth-tone={heatTone(entry.growthPercent)}>{displayPercent(entry.growthPercent)}</small>
            )}
          </HeatCell>
        )
      })}
      <td className="saleout-ledger-total">{displayValue(item.comparisonYtd, metric)}</td>
      <td>{runRate === null ? '—' : displayValue({ state: runRate === 0 ? 'zero' : 'value', value: runRate }, metric)}</td>
      <td
        aria-label={`Diff เทียบ Run rate ${runRateDiff === null ? '—' : displayValue({ state: runRateDiff === 0 ? 'zero' : 'value', value: runRateDiff }, metric)}`}
        className="saleout-heat-cell"
        data-heat-enabled={heatmap ? 'true' : 'false'}
        data-heat-tone={runRateDiff === null ? 'unavailable' : runRateDiff > 0 ? 'high' : runRateDiff < 0 ? 'negative' : 'low'}
      >
        {runRateDiff === null ? '—' : displayValue({ state: runRateDiff === 0 ? 'zero' : 'value', value: runRateDiff }, metric)}
      </td>
      <HeatCell value={item.momPercent} label="MoM" heatmap={heatmap} />
      <HeatCell value={item.yoyPercent} label="YoY" heatmap={heatmap} />
      <HeatCell value={item.growthPercent} label="YTD" heatmap={heatmap} />
    </tr>
  )
}

export function SaleOutComparisonLedger({
  report,
  metric,
  baseYear,
  comparisonYear,
  heatmap,
  onToggleHeatmap,
}: {
  report: SaleOutReport
  metric: SaleOutMetric
  baseYear: number
  comparisonYear: number
  heatmap: boolean
  onToggleHeatmap: () => void
}) {
  const topScrollRef = useRef<HTMLDivElement>(null)
  const ledgerScrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const topSpacerRef = useRef<HTMLDivElement>(null)
  const totalItem: SaleOutModernTrade = {
    code: 'Total',
    name: 'เฉพาะ MT ที่พร้อมรวม',
    status: report.kpis.dataCompletenessPercent === 100 ? 'ready' : 'incomplete',
    includedInTotal: true,
    startDate: null,
    latestSourceDate: report.meta.cutoff,
    latestDailyDate: report.meta.cutoff,
    baseYtd: report.kpis.baseYtd,
    comparisonYtd: report.kpis.comparisonYtd,
    difference: report.kpis.difference,
    growthPercent: report.kpis.growthPercent,
    latestMonth: report.kpis.latestMonth,
    momPercent: report.kpis.momPercent,
    yoyPercent: report.kpis.yoyPercent,
    monthly: report.monthly,
  }

  useLayoutEffect(() => {
    const table = tableRef.current
    const spacer = topSpacerRef.current
    if (!table || !spacer) return

    const syncWidth = () => {
      const ledgerScroll = ledgerScrollRef.current
      const scrollbarWidth = Math.max(0, (ledgerScroll?.offsetWidth ?? 0) - (ledgerScroll?.clientWidth ?? 0))
      spacer.style.width = `${table.scrollWidth + scrollbarWidth}px`
    }
    syncWidth()

    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(syncWidth)
    observer.observe(table)
    if (ledgerScrollRef.current) observer.observe(ledgerScrollRef.current)
    return () => observer.disconnect()
  }, [report, metric, baseYear, comparisonYear])

  return (
    <section className="saleout-panel saleout-ledger-panel">
      <header>
        <div>
          <span className="eyebrow">REPORT SALE OUT {baseYear}–{comparisonYear}</span>
          <h2>ตารางเปรียบเทียบรายเดือน</h2>
          <small>โครงเดียวกับ Excel: ปีฐาน → ปีเปรียบเทียบ → Run rate และ Growth</small>
        </div>
        <div className="saleout-heatmap-controls">
          <div className="heat-legend" aria-label="คำอธิบายสี Heat Map">
            <span>ต่ำ</span><i className="heat-low" /><i className="heat-medium" /><i className="heat-high" /><span>สูง</span><i className="heat-negative" /><span>ลดลง</span>
          </div>
          <label className="heatmap-toggle">
            <input type="checkbox" checked={heatmap} onChange={onToggleHeatmap} />
            <span className="toggle-track" aria-hidden="true"><span /></span>
            <span><SlidersHorizontal size={15} aria-hidden="true" />Heatmap</span>
          </label>
        </div>
      </header>
      <div
        className="matrix-top-scroll saleout-ledger-top-scroll"
        ref={topScrollRef}
        role="region"
        aria-label="เลื่อนตาราง Sale Out แนวนอนด้านบน"
        tabIndex={0}
        onScroll={(event) => { if (ledgerScrollRef.current) ledgerScrollRef.current.scrollLeft = event.currentTarget.scrollLeft }}
      >
        <div className="matrix-top-scroll-spacer" ref={topSpacerRef} />
      </div>
      <div className="saleout-ledger-scroll" ref={ledgerScrollRef} onScroll={(event) => { if (topScrollRef.current) topScrollRef.current.scrollLeft = event.currentTarget.scrollLeft }}>
        <table ref={tableRef} className="saleout-ledger" aria-label="ตารางเปรียบเทียบ Sale Out แบบ Heat Map">
          <thead>
            <tr>
              <th rowSpan={2}>MT</th>
              <th colSpan={13}>ปี {baseYear}</th>
              <th colSpan={13}>ปี {comparisonYear}</th>
              <th colSpan={5}>วิเคราะห์ ณ Cut-off</th>
            </tr>
            <tr>
              {months.map((month) => <th key={`base-${month}`}>{month}</th>)}
              <th>YTD</th>
              {months.map((month) => <th key={`comparison-${month}`}>{month}</th>)}
              <th>YTD</th>
              <th title="ยอดอ้างอิง MTD ของเดือนก่อนในจำนวนวันเท่ากัน">Run rate</th>
              <th>Diff</th>
              <th>MoM</th>
              <th>YoY</th>
              <th>YTD</th>
            </tr>
          </thead>
          <tbody>
            {report.modernTrades.map((item) => (
              <LedgerRow key={item.code} item={item} metric={metric} heatmap={heatmap} />
            ))}
          </tbody>
          <tfoot>
            <LedgerRow item={totalItem} metric={metric} heatmap={heatmap} />
          </tfoot>
        </table>
      </div>
    </section>
  )
}
