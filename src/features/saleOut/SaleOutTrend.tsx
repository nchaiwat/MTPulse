import { useState } from 'react'
import type { SaleOutMetric, SaleOutMonth } from './types'

const monthNames = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

function readable(value: number | null) {
  if (value === null) return 'ไม่มีข้อมูล'
  return new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 }).format(value)
}

export function SaleOutTrend({
  rows,
  metric,
  baseYear,
  comparisonYear,
}: {
  rows: SaleOutMonth[]
  metric: SaleOutMetric
  baseYear: number
  comparisonYear: number
}) {
  const [activeMonth, setActiveMonth] = useState<number | null>(null)
  const width = 760
  const height = 248
  const left = 62
  const right = 20
  const top = 18
  const bottom = 38
  const byMonth = new Map(rows.map((row) => [row.month, row]))
  const months = Array.from({ length: 12 }, (_, index) => byMonth.get(index + 1))
  const values = months.flatMap((row) => row ? [row.base.value, row.comparison.value].filter((entry): entry is number => entry !== null) : [])
  const maximum = Math.max(...values, 1)
  const x = (index: number) => left + (index * (width - left - right)) / 11
  const y = (value: number) => top + (1 - value / maximum) * (height - top - bottom)
  const path = (key: 'base' | 'comparison') => {
    let drawing = false
    return months.map((row, index) => {
      const value = row?.[key].value
      if (value === null || value === undefined) {
        drawing = false
        return ''
      }
      const command = drawing ? 'L' : 'M'
      drawing = true
      return `${command} ${x(index)} ${y(value)}`
    }).join(' ')
  }
  const activeRow = activeMonth === null ? null : byMonth.get(activeMonth)
  const metricLabel = metric === 'amount' ? 'Amount Ex.VAT' : metric === 'qty' ? 'Qty' : 'Average Price'

  return (
    <div className="saleout-chart-stage" onMouseLeave={() => setActiveMonth(null)}>
      <svg
        className="saleout-line-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`แนวโน้ม Sale Out ปี ${comparisonYear} เทียบ ${baseYear} · ${metricLabel}`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const lineY = top + ratio * (height - top - bottom)
          return (
            <g key={ratio}>
              <line className="saleout-grid-line" x1={left} x2={width - right} y1={lineY} y2={lineY} />
              <text className="saleout-axis-label" x={left - 8} y={lineY + 4}>
                {maximum >= 1_000_000 ? `${(maximum * (1 - ratio) / 1_000_000).toFixed(0)}ล.` : new Intl.NumberFormat('th-TH', { notation: 'compact' }).format(maximum * (1 - ratio))}
              </text>
            </g>
          )
        })}
        <path className="saleout-series is-base" d={path('base')} />
        <path className="saleout-series is-comparison" d={path('comparison')} />
        {months.map((row, index) => (
          <g
            className="saleout-chart-point"
            key={index + 1}
            tabIndex={row ? 0 : -1}
            role={row ? 'button' : undefined}
            aria-label={row ? `${monthNames[index]} ${comparisonYear}: ${readable(row.comparison.value)}, ${baseYear}: ${readable(row.base.value)}` : undefined}
            onMouseEnter={() => row && setActiveMonth(index + 1)}
            onFocus={() => row && setActiveMonth(index + 1)}
            onBlur={() => setActiveMonth(null)}
          >
            {row && <circle className="saleout-point-hit" cx={x(index)} cy={y(row.comparison.value ?? row.base.value ?? 0)} r="20" />}
            {row?.base.value !== null && row?.base.value !== undefined && <circle className="saleout-point is-base" cx={x(index)} cy={y(row.base.value)} r="3" />}
            {row?.comparison.value !== null && row?.comparison.value !== undefined && <circle className="saleout-point is-comparison" cx={x(index)} cy={y(row.comparison.value)} r="3.5" />}
            <text className="saleout-month-label" x={x(index)} y={height - 12}>{monthNames[index]}</text>
          </g>
        ))}
      </svg>
      {activeRow && activeMonth !== null && (
        <div className="saleout-chart-tooltip" role="status" style={{ left: `clamp(90px, ${(x(activeMonth - 1) / width) * 100}%, calc(100% - 90px))` }}>
          <strong>{monthNames[activeMonth - 1]}</strong>
          <span><i className="is-comparison" />{comparisonYear}<b>{readable(activeRow.comparison.value)}</b></span>
          <span><i className="is-base" />{baseYear}<b>{readable(activeRow.base.value)}</b></span>
        </div>
      )}
    </div>
  )
}
