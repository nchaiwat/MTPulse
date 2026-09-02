import { useState } from 'react'
import type { DashboardMetric, DashboardMonth } from './types'

const compact = new Intl.NumberFormat('th-TH', { notation: 'compact', maximumFractionDigits: 1 })
const exact = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 0 })
const monthNames = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

function valueOf(row: DashboardMonth, metric: DashboardMetric, current: boolean) {
  if (metric === 'qty') return current ? row.currentQty : row.previousQty
  return current ? row.currentAmount : row.previousAmount
}

export function TrendChart({
  rows,
  metric,
  currentYear,
  previousYear,
}: {
  rows: DashboardMonth[]
  metric: DashboardMetric
  currentYear: number
  previousYear: number
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const width = 720
  const height = 260
  const left = 58
  const right = 18
  const top = 20
  const bottom = 38
  const values = rows.flatMap((row) => [valueOf(row, metric, true), valueOf(row, metric, false)])
  const maxValue = Math.max(...values, 1)
  const x = (index: number) => left + (index * (width - left - right)) / Math.max(rows.length - 1, 1)
  const y = (value: number) => top + (1 - value / maxValue) * (height - top - bottom)
  const points = (current: boolean) => rows.map((row, index) => `${x(index)},${y(valueOf(row, metric, current))}`).join(' ')

  const activeRow = activeIndex === null ? null : rows[activeIndex]
  return (
    <div className="line-chart-stage" onMouseLeave={() => setActiveIndex(null)}>
    <svg className="dashboard-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`แนวโน้ม ${metric === 'amount' ? 'ยอดขาย' : 'จำนวน'} ปี ${currentYear} เทียบ ${previousYear}`}>
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const lineY = top + ratio * (height - top - bottom)
        return <g key={ratio}><line x1={left} x2={width - right} y1={lineY} y2={lineY} /><text x={left - 8} y={lineY + 4}>{compact.format(maxValue * (1 - ratio))}</text></g>
      })}
      <polyline className="previous-line" points={points(false)} />
      <polyline className="current-line" points={points(true)} />
      {rows.map((row, index) => (
        <g
          className="chart-point-group"
          key={row.monthKey}
          tabIndex={0}
          role="button"
          aria-label={`${monthNames[row.month - 1]} ${currentYear}: ${exact.format(valueOf(row, metric, true))}, ${previousYear}: ${exact.format(valueOf(row, metric, false))}`}
          onMouseEnter={() => setActiveIndex(index)}
          onFocus={() => setActiveIndex(index)}
          onBlur={() => setActiveIndex(null)}
        >
          <circle className="chart-hit-area" cx={x(index)} cy={Math.min(y(valueOf(row, metric, false)), y(valueOf(row, metric, true)))} r="13" />
          <circle className="previous-point" cx={x(index)} cy={y(valueOf(row, metric, false))} r="3" />
          <circle className="current-point" cx={x(index)} cy={y(valueOf(row, metric, true))} r="3.5" />
          <text className="month-label" x={x(index)} y={height - 12}>{monthNames[row.month - 1]}</text>
        </g>
      ))}
    </svg>
    {activeRow && activeIndex !== null && (
      <div className="chart-tooltip line-tooltip" style={{ left: `clamp(96px, ${(x(activeIndex) / width) * 100}%, calc(100% - 96px))` }} role="status">
        <strong>{monthNames[activeRow.month - 1]} {currentYear}</strong>
        <span><i className="current-swatch" />{currentYear}<b>{exact.format(valueOf(activeRow, metric, true))}</b></span>
        <span><i className="previous-swatch" />{previousYear}<b>{exact.format(valueOf(activeRow, metric, false))}</b></span>
      </div>
    )}
    </div>
  )
}

export function MonthlyBars({
  rows,
  metric,
  currentYear,
  previousYear,
}: {
  rows: DashboardMonth[]
  metric: DashboardMetric
  currentYear: number
  previousYear: number
}) {
  const maxValue = Math.max(
    ...rows.flatMap((row) => [valueOf(row, metric, true), valueOf(row, metric, false)]),
    1,
  )
  return (
    <div className="monthly-bars" role="group" aria-label="กราฟแท่งเปรียบเทียบรายเดือน">
      {rows.map((row) => (
        <button className="month-bar-group" type="button" key={row.monthKey} aria-label={`${monthNames[row.month - 1]} ${currentYear}: ${exact.format(valueOf(row, metric, true))}, ${previousYear}: ${exact.format(valueOf(row, metric, false))}`}>
          <div className="bar-pair">
            <span className="previous-bar" style={{ height: `${(valueOf(row, metric, false) / maxValue) * 100}%` }} />
            <span className="current-bar" style={{ height: `${(valueOf(row, metric, true) / maxValue) * 100}%` }} />
          </div>
          <small>{monthNames[row.month - 1]}</small>
          <span className="chart-tooltip"><strong>{monthNames[row.month - 1]} {currentYear}</strong><span><i className="current-swatch" />{currentYear}<b>{exact.format(valueOf(row, metric, true))}</b></span><span><i className="previous-swatch" />{previousYear}<b>{exact.format(valueOf(row, metric, false))}</b></span></span>
        </button>
      ))}
    </div>
  )
}

export function RankingBars<T extends { currentAmount: number; previousAmount: number; currentQty: number; previousQty: number }>({
  rows,
  metric,
  label,
  currentYear,
  previousYear,
}: {
  rows: T[]
  metric: DashboardMetric
  label: (row: T) => string
  currentYear: number
  previousYear: number
}) {
  const current = (row: T) => metric === 'amount' ? row.currentAmount : row.currentQty
  const previous = (row: T) => metric === 'amount' ? row.previousAmount : row.previousQty
  const maxValue = Math.max(...rows.flatMap((row) => [current(row), previous(row)]), 1)
  return (
    <div className="ranking-bars" role="group" aria-label="กราฟอันดับเปรียบเทียบปีปัจจุบันกับปีก่อน">
      {rows.map((row, index) => (
        <button className="ranking-bar-row" type="button" key={index} aria-label={`${label(row)}, ${currentYear}: ${exact.format(current(row))}, ${previousYear}: ${exact.format(previous(row))}`}>
          <span title={label(row)}>{label(row)}</span>
          <div className="ranking-track">
            <i className="previous-ranking-bar" style={{ width: `${(previous(row) / maxValue) * 100}%` }} />
            <i className="current-ranking-bar" style={{ width: `${(current(row) / maxValue) * 100}%` }} />
          </div>
          <div className="chart-tooltip ranking-tooltip"><strong>{label(row)}</strong><span><i className="current-swatch" />{currentYear}<b>{exact.format(current(row))}</b></span><span><i className="previous-swatch" />{previousYear}<b>{exact.format(previous(row))}</b></span></div>
        </button>
      ))}
    </div>
  )
}
