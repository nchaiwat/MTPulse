import type { DataPoint, Dimension, Metric, Mode, PerformanceItem } from './types'

const amountFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const quantityFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

export const metricLabel: Record<Metric, string> = {
  amount: 'Amount',
  qty: 'Qty',
  stockOh: 'Stock On Hand',
  stockOnOrder: 'Stock On Order',
}

export function metricValue(point: DataPoint, metric: Metric) {
  return point[metric]
}

export function pointsForView(
  item: PerformanceItem,
  dates: string[],
  branchId: string,
  mode: Mode,
  dimension: Dimension,
) {
  let points = item.points.filter(
    (point) => dates.includes(point.date) && (branchId === 'all' || point.branchId === branchId),
  )

  if (mode === 'inventory' && dimension === 'branch' && dates.length > 0) {
    const latestDate = [...dates].sort().at(-1)
    points = points.filter((point) => point.date === latestDate)
  }

  return points
}

export function sumMetric(points: DataPoint[], metric: Metric) {
  return points.reduce((total, point) => total + metricValue(point, metric), 0)
}

export function monthKey(date: string) {
  return date.slice(0, 7)
}

export function monthKeys(dates: string[]) {
  return [...new Set(dates.map(monthKey))].sort()
}

export function aggregateByDimension(points: DataPoint[], dimension: Dimension, metric: Metric) {
  return points.reduce<Record<string, number>>((totals, point) => {
    const key = dimension === 'branch'
      ? point.branchId
      : dimension === 'month'
        ? monthKey(point.date)
        : point.date
    totals[key] = (totals[key] ?? 0) + metricValue(point, metric)
    return totals
  }, {})
}

export function formatMetric(value: number, metric: Metric) {
  return (metric === 'amount' ? amountFormatter : quantityFormatter).format(value)
}

export function heatLevel(value: number, maxValue: number) {
  if (value < 0) return 'negative'
  if (value === 0 || maxValue <= 0) return 'zero'
  const ratio = value / maxValue
  if (ratio >= 0.7) return 'high'
  if (ratio >= 0.35) return 'medium'
  return 'low'
}
