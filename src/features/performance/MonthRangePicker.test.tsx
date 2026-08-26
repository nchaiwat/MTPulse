import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MonthRangePicker } from './MonthRangePicker'

describe('MonthRangePicker', () => {
  it('applies a chronological month range', async () => {
    const onApply = vi.fn()
    render(
      <MonthRangePicker
        monthFrom=""
        monthTo=""
        months={['2025-01', '2026-08']}
        onApply={onApply}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /ทุกเดือนที่มีข้อมูล/ }))
    await userEvent.type(screen.getByLabelText('เดือนเริ่มต้น'), '2025-01')
    await userEvent.type(screen.getByLabelText('เดือนสิ้นสุด'), '2026-08')
    await userEvent.click(screen.getByRole('button', { name: 'แสดงผล' }))

    expect(onApply).toHaveBeenCalledWith('2025-01', '2026-08')
  })
})
