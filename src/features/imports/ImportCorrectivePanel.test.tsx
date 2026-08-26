import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ImportCorrectivePanel } from './ImportCorrectivePanel'

const batch = {
  batchId: 18,
  dataDate: '2026-08-02',
  filename: 'source.xls',
  status: 'imported_with_warnings',
  warnings: ['Stock On Hand: calculated=77904, source=77379'],
  summary: { rowCount: 12530, skuCount: 113, branchCount: 90, amount: 100, salesQty: 10, stockOnHand: 77904, reportedStockOnHand: 77379, stockOnOrder: 20, negativeRowCount: 0 },
  resolution: null,
}

describe('ImportCorrectivePanel', () => {
  afterEach(() => vi.restoreAllMocks())

  it('loads a warning and requires a note before acknowledgement', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
      if (init?.method === 'POST') {
        return new Response(JSON.stringify({ ...batch, resolution: { type: 'acknowledged', note: 'ตรวจ Total แล้ว', resolvedAt: '2026-08-26T01:00:00Z', resolvedBy: 'manual-user' } }))
      }
      return new Response(JSON.stringify(batch))
    })
    render(<ImportCorrectivePanel batchId={18} />)
    expect(await screen.findByText('Stock On Hand: calculated=77904, source=77379')).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'ยืนยันรับทราบ' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('หมายเหตุการตรวจสอบ'), 'ตรวจ Total แล้ว')
    await userEvent.click(button)
    expect(await screen.findByText('รับทราบแล้ว')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(expect.stringContaining('/acknowledge'), expect.objectContaining({ method: 'POST' }))
  })
})
