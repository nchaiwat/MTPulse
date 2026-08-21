import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { PerformancePage } from './PerformancePage'
import { samplePerformanceResponse } from './sampleData'

describe('PerformancePage', () => {
  it('switches between branch and day matrix views', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('heading', { name: 'Sales ตาม Branch' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Date' }))

    expect(screen.getByRole('heading', { name: 'Sales ตาม Date' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /16 ส\.ค\./ })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /17 ส\.ค\./ })).toBeInTheDocument()
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

  it('filters items and opens item detail', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    await user.type(screen.getByRole('searchbox', { name: 'ค้นหา Item' }), '60358971')
    expect(screen.getByText('แสดง 1 จาก 2,043 SKU')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '60358971' }))
    expect(screen.getByRole('dialog', { name: '60358971' })).toBeInTheDocument()
    expect(screen.getByText('SKU × Branch × Day')).toBeInTheDocument()
  })

  it('hides only items that are not mapped', async () => {
    const user = userEvent.setup()
    render(<PerformancePage initialData={samplePerformanceResponse} />)

    expect(screen.getByRole('button', { name: '60358968' })).toBeInTheDocument()
    const unmapButton = screen.getByRole('button', { name: 'Unmap' })
    expect(unmapButton).toHaveAttribute('aria-pressed', 'true')
    await user.click(unmapButton)

    expect(screen.queryByRole('button', { name: '60358968' })).not.toBeInTheDocument()
    expect(unmapButton).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('แสดง 7 จาก 2,043 SKU')).toBeInTheDocument()
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
