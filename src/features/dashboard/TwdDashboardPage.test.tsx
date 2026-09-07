import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TwdDashboardPage } from './TwdDashboardPage'

const response = {
  meta: {
    mtCode: 'TWD',
    mtName: 'ไทวัสดุ',
    year: 2026,
    previousYear: 2025,
    period: 'ytd',
    latestDataDate: '2026-01-31',
    availableYears: [2025, 2026],
    loadedDays: 31,
    expectedDays: 31,
    completenessPercent: 100,
  },
  summary: {
    currentAmount: 1200,
    previousAmount: 1000,
    amountYoY: 20,
    currentQty: 12,
    previousQty: 10,
    qtyYoY: 20,
  },
  monthly: [{
    month: 1,
    monthKey: '2026-01',
    currentAmount: 1200,
    previousAmount: 1000,
    amountYoY: 20,
    amountMoM: null,
    currentQty: 12,
    previousQty: 10,
    qtyYoY: 20,
  }],
  topBranches: [{
    branchCode: '60016',
    branchName: 'ภูเก็ต เฟสติวัล',
    mappedBranchCode: 'CTW-0048',
    displayName: '60016 - ภูเก็ต เฟสติวัล (CTW-0048)',
    currentAmount: 1200,
    previousAmount: 1000,
    currentQty: 12,
    previousQty: 10,
    amountYoY: 20,
    qtyYoY: 20,
  }],
  topSkus: [{
    sku: '60365148',
    description: 'ประตูบานเลื่อน UPVC FRAMEX 2 บาน',
    currentAmount: 1200,
    previousAmount: 1000,
    currentQty: 12,
    previousQty: 10,
    amountYoY: 20,
    qtyYoY: 20,
  }],
}

describe('TwdDashboardPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses mapped branch labels, separate SKU columns, and non-overlapping chart details', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    )
    render(<TwdDashboardPage onOpenReport={vi.fn()} />)

    const branchHeading = await screen.findByRole('heading', { name: 'Top 10 สาขา' })
    const branchSection = branchHeading.closest('section')
    expect(branchSection).not.toBeNull()
    expect(within(branchSection!).getAllByText('60016 - ภูเก็ต เฟสติวัล (CTW-0048)').length).toBeGreaterThan(0)
    expect(within(branchSection!).getByText('01')).toBeInTheDocument()
    expect(within(branchSection!).getAllByText('60016').length).toBeGreaterThan(0)
    expect(within(branchSection!).getAllByText('ภูเก็ต เฟสติวัล (CTW-0048)').length).toBeGreaterThanOrEqual(2)
    expect(within(branchSection!).getAllByText('+20.0%').length).toBeGreaterThanOrEqual(2)
    const branchInspector = within(branchSection!).getByRole('status')
    expect(within(branchInspector).getByText('1,200')).toBeInTheDocument()
    expect(within(branchInspector).getByText('1,000')).toBeInTheDocument()
    expect(branchSection!.querySelector('.ranking-tooltip')).not.toBeInTheDocument()

    const skuHeading = screen.getByRole('heading', { name: 'Top 15 SKU' })
    const skuSection = skuHeading.closest('section')
    expect(skuSection).not.toBeNull()
    const skuTable = within(skuSection!).getByRole('table')
    expect(within(skuTable).getByRole('columnheader', { name: 'SKU' })).toBeInTheDocument()
    expect(within(skuTable).getByRole('columnheader', { name: 'สินค้า' })).toBeInTheDocument()
    expect(within(skuTable).getByRole('cell', { name: '60365148' })).toBeInTheDocument()
    expect(within(skuTable).getByRole('cell', { name: 'ประตูบานเลื่อน UPVC FRAMEX 2 บาน' })).toBeInTheDocument()
    expect(within(skuSection!).getAllByText('60365148').length).toBeGreaterThan(1)

    const chartTargets = screen.getAllByRole('button', { name: /ม\.ค\. 2026: 1,200, 2025: 1,000/ })
    expect(chartTargets.length).toBeGreaterThanOrEqual(2)
    await userEvent.tab()
    expect(chartTargets[0]).toHaveAttribute('tabindex', '0')
    expect(within(chartTargets[1]).getByText('ม.ค. 2026')).toBeInTheDocument()
  })
})
