import { describe, expect, it } from 'vitest'
import { performanceItems } from './sampleData'
import { aggregateByDimension, heatLevel, monthKeys, pointsForView, sumMetric } from './performanceMath'

describe('performance calculations', () => {
  const item = performanceItems[0]

  it('aggregates quantity by branch across selected days', () => {
    const points = pointsForView(item, ['2026-08-16', '2026-08-17'], 'all', 'sales', 'branch')
    const totals = aggregateByDimension(points, 'branch', 'qty')

    expect(totals['60920']).toBe(10)
    expect(sumMetric(points, 'qty')).toBe(24)
  })

  it('uses the latest selected snapshot for inventory by branch', () => {
    const points = pointsForView(item, ['2026-08-16', '2026-08-17'], 'all', 'inventory', 'branch')

    expect(points.every((point) => point.date === '2026-08-17')).toBe(true)
    expect(sumMetric(points, 'stockOh')).toBe(15)
  })

  it('keeps returns negative and gives them a distinct heat level', () => {
    const returnItem = performanceItems.find((candidate) => candidate.sku === '60358971')!
    const points = pointsForView(returnItem, ['2026-08-17'], '60920', 'sales', 'branch')

    expect(sumMetric(points, 'qty')).toBe(-1)
    expect(heatLevel(sumMetric(points, 'amount'), 10000)).toBe('negative')
  })

  it('orders months chronologically across years and aggregates monthly totals', () => {
    const points = [
      { date: '2026-02-03', branchId: 'A', amount: 20, qty: 2, stockOh: 0, stockOnOrder: 0 },
      { date: '2025-12-20', branchId: 'A', amount: 10, qty: 1, stockOh: 0, stockOnOrder: 0 },
      { date: '2026-01-02', branchId: 'B', amount: 30, qty: 3, stockOh: 0, stockOnOrder: 0 },
      { date: '2026-02-21', branchId: 'B', amount: -5, qty: -1, stockOh: 0, stockOnOrder: 0 },
    ]

    expect(monthKeys(points.map((point) => point.date))).toEqual(['2025-12', '2026-01', '2026-02'])
    expect(aggregateByDimension(points, 'month', 'amount')).toEqual({
      '2025-12': 10,
      '2026-01': 30,
      '2026-02': 15,
    })
  })
})
