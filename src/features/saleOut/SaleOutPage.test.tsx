import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SaleOutPage } from './SaleOutPage'

const value = (amount: number) => ({ state: amount === 0 ? 'zero' : 'value', value: amount })
const unavailable = { state: 'unavailable', value: null }

const response = {
  meta: {
    baseYear: 2025,
    comparisonYear: 2026,
    cutoff: '2026-08-03',
    activeCutoff: '2026-08-03',
    salesBasis: 'gross',
    metric: 'amount',
    mtCodes: ['TWD', 'HP', 'DH'],
    availableYears: [2025, 2026],
  },
  kpis: {
    baseYtd: value(100_000_000),
    comparisonYtd: value(112_000_000),
    difference: 12_000_000,
    growthPercent: 12,
    latestMonth: value(12_000_000),
    momPercent: 3.2,
    yoyPercent: 8.4,
    dataCompletenessPercent: 96.7,
  },
  monthly: [
    { month: 1, base: value(10_000_000), comparison: value(11_000_000), growthPercent: 10 },
    { month: 2, base: value(12_000_000), comparison: value(13_000_000), growthPercent: 8.3 },
    { month: 9, base: value(9_000_000), comparison: { state: 'future', value: null }, growthPercent: null },
  ],
  modernTrades: [
    {
      code: 'TWD', name: 'Thai Watsadu', status: 'ready', includedInTotal: true,
      startDate: '2025-01-01', latestSourceDate: '2026-08-03', latestDailyDate: '2026-08-03',
      baseYtd: value(60_000_000), comparisonYtd: value(67_000_000), difference: 7_000_000,
      growthPercent: 11.7, latestMonth: value(7_000_000), momPercent: 2.1, yoyPercent: 6.3,
      monthly: [{ month: 1, base: value(6_000_000), comparison: value(6_700_000), growthPercent: 11.7 }],
    },
    {
      code: 'HP', name: 'HomePro', status: 'incomplete', includedInTotal: true,
      startDate: '2025-01-01', latestSourceDate: '2026-08-02', latestDailyDate: '2026-08-02',
      baseYtd: value(40_000_000), comparisonYtd: value(45_000_000), difference: 5_000_000,
      growthPercent: 12.5, latestMonth: value(5_000_000), momPercent: 4.5, yoyPercent: 11.2,
      monthly: [{ month: 1, base: value(4_000_000), comparison: value(4_500_000), growthPercent: 12.5 }],
    },
    {
      code: 'DH', name: 'DoHome', status: 'excluded', includedInTotal: false,
      startDate: null, latestSourceDate: null, latestDailyDate: null,
      baseYtd: unavailable, comparisonYtd: unavailable, difference: null, growthPercent: null,
      latestMonth: unavailable, momPercent: null, yoyPercent: null, monthly: [],
    },
  ],
  periods: [
    { code: 'Q1', base: value(30_000_000), comparison: value(34_000_000), growthPercent: 13.3 },
    { code: 'H1', base: value(75_000_000), comparison: value(83_000_000), growthPercent: 10.7 },
    { code: 'YTD', base: value(100_000_000), comparison: value(112_000_000), growthPercent: 12 },
  ],
}

describe('SaleOutPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders the common-cutoff ledger and an Excel-style comparison heat map', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    )

    render(<SaleOutPage />)

    expect(await screen.findByRole('heading', { level: 1, name: 'Sale Out' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('base_year=2025&comparison_year=2026&sales_basis=gross&metric=amount'),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(screen.getByRole('button', { name: 'Amount Ex.VAT' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Gross' })).toHaveAttribute('aria-pressed', 'true')

    const cutoffLedger = screen.getByRole('region', { name: 'Common Cut-off และความสดของข้อมูล' })
    expect(within(cutoffLedger).getAllByText('03/08/2026').length).toBeGreaterThan(0)
    expect(within(cutoffLedger).getByText('TWD')).toBeInTheDocument()
    expect(within(cutoffLedger).getByText('DH')).toBeInTheDocument()
    expect(within(cutoffLedger).getByText('ไม่รวมใน Total')).toBeInTheDocument()

    expect(screen.getAllByText('112 ล.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('+12.0%').length).toBeGreaterThan(0)
    expect(screen.getByRole('table', { name: 'สรุป Sale Out ตาม Modern Trade' })).toBeInTheDocument()
    const heatMap = screen.getByRole('table', { name: 'ตารางเปรียบเทียบ Sale Out แบบ Heat Map' })
    expect(within(heatMap).getByText('ปี 2025')).toBeInTheDocument()
    expect(within(heatMap).getByText('ปี 2026')).toBeInTheDocument()
    expect(within(heatMap).getAllByText('+10.0%').length).toBeGreaterThan(0)
    expect(within(heatMap).getByRole('cell', { name: /ม.ค. .*เติบโต \+10.0%/ })).not.toHaveAttribute('data-heat-tone', 'unavailable')
    expect(screen.getByLabelText('คำอธิบายสี Heat Map')).toHaveTextContent('ต่ำ')
    expect(screen.getByLabelText('คำอธิบายสี Heat Map')).toHaveTextContent('สูง')
    expect(screen.getByLabelText('คำอธิบายสี Heat Map')).toHaveTextContent('ลดลง')
    expect(within(heatMap).getByText('11.63 ล.')).toBeInTheDocument()
    const heatmapToggle = screen.getByRole('checkbox', { name: 'Heatmap' })
    expect(heatmapToggle).toBeChecked()
    await userEvent.click(heatmapToggle)
    expect(within(heatMap).getByRole('cell', { name: /ม.ค. .*เติบโต \+10.0%/ })).toHaveAttribute('data-heat-enabled', 'false')
    expect(screen.getByRole('table', { name: 'สรุปตามช่วงเวลา' })).toBeInTheDocument()
    expect(within(heatMap).getByRole('row', { name: /DHDoHomeไม่พร้อม/ })).toBeInTheDocument()
  })

  it('uses the compact report header, dd/mm/yyyy cut-off and synchronized horizontal scrollbars', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    )

    render(<SaleOutPage />)
    await screen.findByRole('heading', { level: 1, name: 'Sale Out' })

    const header = screen.getByRole('banner', { name: 'ส่วนหัวรายงาน Sale Out' })
    expect(header).toHaveClass('saleout-compact-header')
    expect(within(header).getByText('03/08/2026')).toBeInTheDocument()

    const cutoffInput = screen.getByRole('textbox', { name: 'Historical Cut-off' })
    expect(cutoffInput).toHaveValue('03/08/2026')
    expect(cutoffInput).toHaveAttribute('placeholder', 'dd/mm/yyyy')

    const topScroll = screen.getByRole('region', { name: 'เลื่อนตาราง Sale Out แนวนอนด้านบน' })
    const bottomScroll = document.querySelector<HTMLElement>('.saleout-ledger-scroll')
    expect(bottomScroll).not.toBeNull()

    topScroll.scrollLeft = 160
    fireEvent.scroll(topScroll)
    expect(bottomScroll?.scrollLeft).toBe(160)

    if (bottomScroll) {
      bottomScroll.scrollLeft = 48
      fireEvent.scroll(bottomScroll)
    }
    expect(topScroll.scrollLeft).toBe(48)
  })

  it('refetches when the metric changes and keeps unavailable distinct from zero', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => (
      new Response(JSON.stringify(response), { status: 200 })
    ))
    render(<SaleOutPage />)
    await screen.findByRole('heading', { level: 1, name: 'Sale Out' })

    await userEvent.click(screen.getByRole('button', { name: 'Qty' }))

    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('metric=qty'))).toBe(true)
    const dhRow = screen.getByRole('row', { name: /DHDoHome ไม่รวมใน Total/ })
    expect(within(dhRow).getAllByText('ไม่พร้อม').length).toBeGreaterThan(0)
  })
})
