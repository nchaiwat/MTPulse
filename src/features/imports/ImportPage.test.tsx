import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ImportPage } from './ImportPage'

const preview = {
  detectedMt: 'TWD',
  detectedMtName: 'ไทวัสดุ',
  filename: 'twd.xls',
  checksum: 'a'.repeat(64),
  dataDate: '2026-08-18',
  rowCount: 12560,
  skuCount: 2043,
  branchCount: 102,
  sourceAmount: 1101053.72,
  amount: 1029022.17,
  salesQty: 353,
  stockOnHand: 77790,
  stockOnOrder: 5902,
  negativeRowCount: 4,
  warnings: [],
  canImport: true,
  duplicateReason: null,
}

describe('ImportPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('previews one TWD file and requires confirmation', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/activity')) return new Response(JSON.stringify({ items: [] }))
      if (url.includes('/preview')) return new Response(JSON.stringify(preview))
      return new Response(JSON.stringify({
        message: 'นำเข้าข้อมูลสำเร็จ',
        notification: { status: 'skipped', message: 'ยังไม่ได้ตั้งค่า Telegram' },
      }))
    })
    render(<ImportPage />)
    const file = new File(['raw'], 'twd.xls', { type: 'application/vnd.ms-excel' })
    await userEvent.upload(screen.getByLabelText('เลือกไฟล์ Raw Data'), file)
    expect(await screen.findByText('ไทวัสดุ · 18/08/2026')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ตรวจสอบไฟล์' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ยืนยันนำเข้าข้อมูล' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'ยืนยันนำเข้าข้อมูล' }))
    expect(await screen.findByText(/นำเข้าข้อมูลสำเร็จ/)).toBeInTheDocument()
  })
})
