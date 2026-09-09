import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PerformancePage } from './PerformancePage'
import { samplePerformanceResponse } from './sampleData'
import type { PerformanceResponse } from './types'
afterEach(() => {
  window.localStorage.removeItem('mtpulse.performance.twd.current-view')
  window.localStorage.removeItem('mtpulse.performance.hp.current-view')
  window.localStorage.removeItem('mtpulse.performance.mh.current-view')
  vi.restoreAllMocks()
})


describe('PerformancePage', () => {
  it.each([
    ['HP', 'HomePro'],
    ['MH', 'MegaHome'],
  ] as const)('shows %s template columns and Stock Value instead of Stock On Order', async (mtCode, mtName) => {
    const user = userEvent.setup()
    const hpData: PerformanceResponse = {
      ...samplePerformanceResponse,
      mtCode,
      mtName,
      metricCapabilities: {
        sales: ['amount', 'qty'],
        inventory: ['stockOh', 'stockValue'],
      },
      inventorySummary: { stockOh: 15, stockOnOrder: 0, stockValue: 35000 },
      items: samplePerformanceResponse.items.map((item) => ({
        ...item,
        tom: 5.99,
        tod: 179.7,
        points: item.points.map((point) => ({ ...point, stockValue: point.stockOh * 2000 })),
      })),
    }

    render(<PerformancePage mtCode={mtCode} initialData={hpData} />)

    expect(screen.getByRole('heading', { name: `Matrix Performance ของ ${mtName} (${mtCode})` })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: `${mtCode} SKU` })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Inventory' }))
    expect(screen.getByRole('button', { name: 'Stock value' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Stock on order' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Month' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Sho' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Pro' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'TOM' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'TOD' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'สถานะ Sho/Pro' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Stock value' }))
    expect(screen.getByText(/Stock Value \(Source\)/)).toBeInTheDocument()
  })

  it('defaults to Net Sales and persists the selected Gross Sale Out basis', async () => {
    const user = userEvent.setup()
    const firstRender = render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('button', { name: 'Net Sales' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Amount · Net')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Gross Sale Out' }))
    expect(screen.getByRole('button', { name: 'Gross Sale Out' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Amount · Gross')).toBeInTheDocument()
    expect(screen.queryByText('Return')).not.toBeInTheDocument()

    await waitFor(() => expect(window.localStorage.getItem('mtpulse.performance.twd.current-view')).toContain('"salesBasis":"gross"'))
    firstRender.unmount()
    render(<PerformancePage initialData={samplePerformanceResponse} />)
    expect(screen.getByRole('button', { name: 'Gross Sale Out' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows a visible loading indicator over the matrix while refreshing data', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'รายวัน' }))

    const loading = screen.getByRole('status', { name: 'กำลังโหลดข้อมูล Performance' })
    expect(loading).toHaveTextContent('กำลังโหลดข้อมูล…')
    expect(loading.querySelector('svg')).toHaveClass('matrix-loading-spinner')
  })

  it('shows the loading overlay immediately while a mode change is waiting for new data', async () => {
    let performanceCalls = 0
    let resolveInventory!: (response: Response) => void
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/sku-options')) return new Response(JSON.stringify({ items: [] }), { status: 200 })
      performanceCalls += 1
      if (performanceCalls === 1) return new Response(JSON.stringify(samplePerformanceResponse), { status: 200 })
      return new Promise((resolve) => { resolveInventory = resolve })
    })
    const user = userEvent.setup()
    render(<PerformancePage />)

    await waitFor(() => expect(screen.queryByRole('status', { name: 'กำลังโหลดข้อมูล Performance' })).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Inventory' }))

    expect(screen.getByRole('status', { name: 'กำลังโหลดข้อมูล Performance' })).toHaveTextContent('กำลังโหลดข้อมูล…')
    resolveInventory(new Response(JSON.stringify(samplePerformanceResponse), { status: 200 }))
    await waitFor(() => expect(screen.queryByRole('status', { name: 'กำลังโหลดข้อมูล Performance' })).not.toBeInTheDocument())
  })

  it('switches between branch and day matrix views', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('button', { name: 'Download Excel' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Export Mapping' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Import Mapping' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sales ตาม Branch' })).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Mapping' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Date' }))

    expect(screen.getByRole('heading', { name: 'Sales ตาม Date' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '16/08/2026' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '17/08/2026' })).toBeInTheDocument()
    expect(document.querySelector('.matrix-summary-row')).toHaveTextContent('SUM')
  })

  it('uses the latest month in Branch view and shows totals above every column', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('combobox', { name: 'เดือน' })).toHaveValue('latest')
    expect(screen.getByRole('option', { name: 'เดือนล่าสุด · Aug 2026' })).toBeInTheDocument()

    const summaryRow = document.querySelector('.matrix-summary-row')
    expect(summaryRow).not.toBeNull()
    expect(summaryRow).toHaveTextContent('SUM')
    expect(summaryRow).toHaveTextContent('942,009.00')

    await user.click(screen.getByRole('button', { name: 'Qty' }))
    expect(summaryRow).toHaveTextContent('232')
  })

  it('shows every Branch for one selected date', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'รายวัน' }))
    await user.click(screen.getByRole('button', { name: 'ทุกวันที่มีข้อมูล' }))
    const dateDialog = screen.getByRole('dialog', { name: 'เลือกช่วงวันที่' })
    fireEvent.change(within(dateDialog).getByLabelText('วันที่เริ่มต้น'), { target: { value: '16/08/2026' } })
    fireEvent.change(within(dateDialog).getByLabelText('วันที่สิ้นสุด'), { target: { value: '16/08/2026' } })
    await user.click(within(dateDialog).getByRole('button', { name: 'แสดงผล' }))

    expect(screen.getByRole('heading', { name: 'Sales ตาม Branch' })).toBeInTheDocument()
    const bangNaHeader = screen.getByRole('columnheader', { name: /60920.*บางนา/ })
    expect(within(bangNaHeader).getByText('60920')).toBeInTheDocument()
    expect(within(bangNaHeader).getByText('บางนา')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /60926.*ลำปาง/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '60424005' }).closest('tr')).toHaveTextContent('53,500.00')
  })
  it('shows Month for TWD Inventory and keeps the selected monthly matrix', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'Month' }))
    expect(screen.getByRole('heading', { name: 'Sales ตาม Month' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Aug 2026' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Inventory' }))
    expect(screen.getByRole('button', { name: 'Month' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { name: 'Inventory ตาม Month' })).toBeInTheDocument()
  })

  it('hides both description columns without hiding item identities', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('columnheader', { name: 'TWD description' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'WA description' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Description' }))

    expect(screen.queryByRole('columnheader', { name: 'TWD description' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'WA description' })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'WA item' })).toBeInTheDocument()
  })

  it('keeps TWD TOM and TOD sticky columns visible when descriptions are hidden', async () => {
    const user = userEvent.setup()
    const inventoryData: PerformanceResponse = {
      ...samplePerformanceResponse,
      inventorySummary: {
        stockOh: 10,
        stockOnOrder: 0,
        stockValue: 0,
        averageTom: 5.99,
        averageTod: 179.7,
        turnoverSkuCount: 1,
        turnoverReferenceDate: '2026-08-17',
      },
      items: samplePerformanceResponse.items.map((item, index) => ({
        ...item,
        tom: index === 0 ? 5.99 : null,
        tod: index === 0 ? 179.7 : null,
      })),
    }
    render(<PerformancePage initialData={inventoryData} />)

    await user.click(screen.getByRole('button', { name: 'Inventory' }))
    expect(screen.getByRole('columnheader', { name: 'TOM' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'TOD' })).toBeInTheDocument()
    expect(document.querySelector('.matrix-summary-row')).toHaveTextContent('AVG 5.99')
    expect(document.querySelector('.matrix-summary-row')).toHaveTextContent('AVG 179.70')

    await user.click(screen.getByRole('button', { name: 'Description' }))
    expect(screen.queryByRole('columnheader', { name: 'WA description' })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'TOM' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'TOD' })).toBeInTheDocument()
  })

  it('restores the current view after leaving and returning to the report', async () => {
    const user = userEvent.setup()
    const firstRender = render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'Qty' }))
    await user.click(screen.getByRole('button', { name: 'รายวัน' }))
    await user.click(screen.getByRole('button', { name: 'ทุกวันที่มีข้อมูล' }))
    const dateDialog = screen.getByRole('dialog', { name: 'เลือกช่วงวันที่' })
    fireEvent.change(within(dateDialog).getByLabelText('วันที่เริ่มต้น'), { target: { value: '16/08/2026' } })
    fireEvent.change(within(dateDialog).getByLabelText('วันที่สิ้นสุด'), { target: { value: '16/08/2026' } })
    await user.click(within(dateDialog).getByRole('button', { name: 'แสดงผล' }))
    await user.click(screen.getByRole('button', { name: 'ทุก Branch' }))
    const branchDialog = screen.getByRole('dialog', { name: 'เลือก Branch' })
    await user.click(within(branchDialog).getByRole('button', { name: 'ล้างการเลือก' }))
    await user.click(within(branchDialog).getByRole('checkbox', { name: /60920.*บางนา/ }))
    await user.click(within(branchDialog).getByRole('button', { name: 'แสดงผล' }))
    await user.click(screen.getByRole('button', { name: 'ทุก SKU' }))
    const skuDialog = screen.getByRole('dialog', { name: 'เลือก SKU' })
    await user.click(within(skuDialog).getByRole('button', { name: 'ล้างการเลือก' }))
    await user.click(within(skuDialog).getByRole('checkbox', { name: /60424005/ }))
    await user.click(within(skuDialog).getByRole('button', { name: 'แสดงผล' }))
    await user.click(screen.getByRole('checkbox', { name: 'Heatmap' }))
    await user.click(screen.getByRole('button', { name: 'Description' }))

    await waitFor(() => expect(window.localStorage.getItem('mtpulse.performance.twd.current-view')).toContain('60424005'))
    firstRender.unmount()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('button', { name: 'Qty' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'รายวัน' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '16/08/2026' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '60920 - บางนา' })).toBeInTheDocument()
    expect(document.querySelector('.sku-filter-field .filter-trigger')).toHaveTextContent('60424005')
    expect(screen.getByRole('checkbox', { name: 'Heatmap' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Description' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('columnheader', { name: 'TWD description' })).not.toBeInTheDocument()
  }, 15_000)

  it('filters items and opens item detail', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'ทุก SKU' }))
    const skuDialog = screen.getByRole('dialog', { name: 'เลือก SKU' })
    await user.type(within(skuDialog).getByRole('searchbox', { name: 'ค้นหา SKU' }), '60358971')
    await user.click(within(skuDialog).getByRole('button', { name: 'ล้างการเลือก' }))
    await user.click(within(skuDialog).getByRole('checkbox', { name: /60358971/ }))
    await user.click(within(skuDialog).getByRole('button', { name: 'แสดงผล' }))
    expect(screen.getByText('แสดง 1 จาก 2,043 SKU')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: '60358971' }).find((button) => button.classList.contains('item-link'))!)
    expect(screen.getByRole('dialog', { name: '60358971' })).toBeInTheDocument()
    expect(screen.getByText('SKU × Branch × Day')).toBeInTheDocument()
  })

  it('searches by TWD description and displays mapped codes above the description', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'ทุก SKU' }))
    const skuDialog = screen.getByRole('dialog', { name: 'เลือก SKU' })
    await user.type(within(skuDialog).getByRole('searchbox', { name: 'ค้นหา SKU' }), 'WINDOW ASIA 4')

    const option = within(skuDialog).getByRole('checkbox', { name: /60424005/ }).closest('label')
    const primaryLine = option?.querySelector('.sku-option-codes')
    expect(within(primaryLine as HTMLElement).getByText('60424005')).toBeInTheDocument()
    expect(within(primaryLine as HTMLElement).getByText('-')).toBeInTheDocument()
    expect(within(primaryLine as HTMLElement).getByText('FAE32-W22512-180110')).toBeInTheDocument()
    expect(option?.querySelector('.sku-option-label > small')).toHaveTextContent('WINDOW ASIA')
    expect(within(skuDialog).queryByRole('checkbox', { name: /60358971/ })).not.toBeInTheDocument()
  })
  it('marks trial items in the identity area without changing metric cells', () => {
    const trialData = {
      ...samplePerformanceResponse,
      items: samplePerformanceResponse.items.map((item, index) => index === 0 ? { ...item, itemType: 'trial' as const } : item),
    }
    render(<PerformancePage initialData={trialData} />)

    expect(screen.getByText('สินค้าทดลอง')).toBeInTheDocument()
    const trialRow = screen.getByRole('button', { name: '60424005' }).closest('tr')
    expect(trialRow).toHaveAttribute('data-item-type', 'trial')
    expect(trialRow?.querySelector('.numeric-column')).not.toHaveClass('trial-item')
  })
  it('uses a compact SKU cell and synchronizes both horizontal scrollbars', () => {
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    const skuButton = screen.getByRole('button', { name: '60424005' })
    expect(skuButton.querySelector('svg')).toBeNull()

    const topScroll = screen.getByRole('region', { name: 'เลื่อนตารางแนวนอนด้านบน' })
    const bottomScroll = document.querySelector<HTMLElement>('.matrix-scroll')
    expect(bottomScroll).not.toBeNull()

    topScroll.scrollLeft = 120
    fireEvent.scroll(topScroll)
    expect(bottomScroll?.scrollLeft).toBe(120)

    if (bottomScroll) {
      bottomScroll.scrollLeft = 40
      fireEvent.scroll(bottomScroll)
    }
    expect(topScroll.scrollLeft).toBe(40)
  })
})

describe('Sho/Pro Phase 3 interactions', () => {
  const flaggedData = (): PerformanceResponse => ({
    ...samplePerformanceResponse,
    items: samplePerformanceResponse.items.map((item, index) => ({
      ...item,
      isSho: index === 0 || index === 2,
      isPro: index === 1 || index === 2,
    })),
  })

  it('groups the SKU status beside Item and shows the latest data date in the compact page context', () => {
    render(<PerformancePage initialData={flaggedData()} />)

    const filterBar = screen.getByRole('region', { name: 'ตัวกรอง Performance' })
    const fields = [...filterBar.children]
    const itemField = within(filterBar).getByText('Item').closest('.sku-filter-field')
    const statusField = screen.getByRole('combobox', { name: 'สถานะ Sho/Pro' }).closest('label')
    expect(fields.indexOf(statusField!)).toBe(fields.indexOf(itemField!) + 1)
    expect(statusField?.querySelector('svg')).not.toBeNull()
    expect(screen.getByText('วันที่ข้อมูลล่าสุด')).toBeInTheDocument()
    expect(screen.getByText('17/08/2026')).toBeInTheDocument()
  })

  it('shows sticky Sho/Pro controls in every TWD and HP view', async () => {
    const user = userEvent.setup()
    const twd = render(<PerformancePage initialData={flaggedData()} />)

    const headers = screen.getAllByRole('columnheader')
    expect(headers.findIndex((header) => header.textContent === 'Sho')).toBeLessThan(
      headers.findIndex((header) => header.textContent === 'TWD SKU'),
    )
    expect(headers.findIndex((header) => header.textContent === 'Pro')).toBeLessThan(
      headers.findIndex((header) => header.textContent === 'TWD SKU'),
    )
    expect(screen.getByRole('checkbox', { name: 'Sho TWD SKU 60424005' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Pro TWD SKU 60424006' })).toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Date' }))
    expect(screen.getByRole('checkbox', { name: 'Sho TWD SKU 60424005' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Inventory' }))
    expect(screen.getByRole('checkbox', { name: 'Pro TWD SKU 60424006' })).toBeInTheDocument()

    twd.unmount()
    render(<PerformancePage mtCode="HP" initialData={{ ...flaggedData(), mtCode: 'HP', mtName: 'HomePro' }} />)
    expect(screen.getByRole('columnheader', { name: 'Sho' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Pro' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'สถานะ Sho/Pro' })).toBeInTheDocument()
  })

  it('updates a flag optimistically and keeps the selected row treatment', async () => {
    let resolveSave!: (response: Response) => void
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise((resolve) => { resolveSave = resolve }))
    const user = userEvent.setup()
    render(<PerformancePage initialData={flaggedData()} />)

    const checkbox = screen.getByRole('checkbox', { name: 'Sho TWD SKU 60424006' })
    const row = checkbox.closest('tr')!
    await user.click(checkbox)

    expect(checkbox).toBeChecked()
    expect(checkbox).toBeDisabled()
    expect(row).toHaveAttribute('data-sku-flag', 'both')
    await user.click(within(row).getByRole('button', { name: '60424006' }))
    expect(row).toHaveAttribute('data-selected', 'true')
    expect(screen.getByLabelText('สถานะความสนใจ SKU')).toHaveTextContent('Sho')
    expect(screen.getByLabelText('สถานะความสนใจ SKU')).toHaveTextContent('Pro')
    expect(within(screen.getByLabelText('สถานะความสนใจ SKU')).getByText('Sho')).toHaveAttribute('data-active', 'true')
    expect(within(screen.getByLabelText('สถานะความสนใจ SKU')).getByText('Pro')).toHaveAttribute('data-active', 'true')

    resolveSave(new Response(JSON.stringify({
      mtCode: 'TWD', sku: '60424006', isSho: true, isPro: true, updatedAt: '2026-09-09T07:00:00+07:00',
    }), { status: 200 }))
    await waitFor(() => expect(checkbox).not.toBeDisabled())
  })

  it('rolls back only the failed flag and tells the user what failed', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'บันทึกสถานะไม่ได้' }), { status: 500 }),
    )
    const user = userEvent.setup()
    render(<PerformancePage initialData={flaggedData()} />)

    const sho = screen.getByRole('checkbox', { name: 'Sho TWD SKU 60424006' })
    const pro = screen.getByRole('checkbox', { name: 'Pro TWD SKU 60424006' })
    await user.click(sho)

    await waitFor(() => expect(sho).not.toBeChecked())
    expect(pro).toBeChecked()
    expect(screen.getByRole('alert')).toHaveTextContent('บันทึกสถานะไม่ได้')
  })

  it('requests a fresh server scope when the Sho/Pro filter changes', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/sku-options')) {
        return new Response(JSON.stringify({ items: [] }), { status: 200 })
      }
      return new Response(JSON.stringify(flaggedData()), { status: 200 })
    })
    const user = userEvent.setup()
    render(<PerformancePage />)

    await user.selectOptions(await screen.findByRole('combobox', { name: 'สถานะ Sho/Pro' }), 'flagged')

    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => {
      const url = new URL(String(input), 'http://localhost')
      return url.pathname === '/api/performance' && url.searchParams.get('sku_flag') === 'flagged'
    })).toBe(true))
  })

  it('shows every SKU with Sho or Pro while excluding unflagged SKUs', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={flaggedData()} />)

    await user.selectOptions(screen.getByRole('combobox', { name: 'สถานะ Sho/Pro' }), 'flagged')

    expect(screen.getByRole('button', { name: '60424005' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '60424006' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '60406627' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '60406629' })).not.toBeInTheDocument()
  })
})
