import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { PerformancePage } from './PerformancePage'
import { samplePerformanceResponse } from './sampleData'
afterEach(() => window.localStorage.removeItem('mtpulse.performance.twd.current-view'))


describe('PerformancePage', () => {
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
  it('shows a monthly sales matrix and removes Month from Inventory', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.click(screen.getByRole('button', { name: 'Month' }))
    expect(screen.getByRole('heading', { name: 'Sales ตาม Month' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Aug 2026' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Inventory' }))
    expect(screen.queryByRole('button', { name: 'Month' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Inventory ตาม Branch' })).toBeInTheDocument()
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
