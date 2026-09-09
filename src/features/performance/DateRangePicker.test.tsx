import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DateRangePicker } from './DateRangePicker'
import { validateDateRangeDrafts } from './dateRangeValidation'

describe('DateRangePicker', () => {
  it('validates overlaps immediately and allows the following day', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(<DateRangePicker dateRanges={[]} availableDates={['2026-09-01', '2026-09-30']} onApply={onApply} />)

    await user.click(screen.getByRole('button', { name: 'ทุกวันที่มีข้อมูล' }))
    const dialog = screen.getByRole('dialog', { name: 'เลือกช่วงวันที่' })
    fireEvent.change(within(dialog).getByLabelText('วันที่เริ่มต้น'), { target: { value: '01/09/2026' } })
    fireEvent.change(within(dialog).getByLabelText('วันที่สิ้นสุด'), { target: { value: '10/09/2026' } })
    await user.click(within(dialog).getByRole('button', { name: 'เพิ่มช่วงวันที่' }))
    fireEvent.change(within(dialog).getByLabelText('ช่วงที่ 2 วันที่เริ่มต้น'), { target: { value: '10/09/2026' } })
    fireEvent.change(within(dialog).getByLabelText('ช่วงที่ 2 วันที่สิ้นสุด'), { target: { value: '15/09/2026' } })

    expect(within(dialog).getAllByRole('alert')).toHaveLength(2)
    expect(within(dialog).getByRole('button', { name: 'แสดงผล' })).toBeDisabled()

    fireEvent.change(within(dialog).getByLabelText('ช่วงที่ 2 วันที่เริ่มต้น'), { target: { value: '11/09/2026' } })
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'แสดงผล' }))
    expect(onApply).toHaveBeenCalledWith([
      { from: '2026-09-01', to: '2026-09-10' },
      { from: '2026-09-11', to: '2026-09-15' },
    ])
  })

  it('supports no more than twelve ranges', () => {
    const validDrafts = Array.from({ length: 12 }, (_, index) => ({
      from: `${String(index + 1).padStart(2, '0')}/09/2026`,
      to: `${String(index + 1).padStart(2, '0')}/09/2026`,
    }))
    expect(validateDateRangeDrafts(validDrafts)).toEqual(Array(12).fill(''))
    expect(validateDateRangeDrafts([
      { from: '01/09/2026', to: '10/09/2026' },
      { from: '10/09/2026', to: '15/09/2026' },
    ])).toEqual(['ทับกับช่วงที่ 2', 'ทับกับช่วงที่ 1'])
  })
})
