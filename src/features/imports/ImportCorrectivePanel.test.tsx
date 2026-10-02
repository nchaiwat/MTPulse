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

  it('uses the DH stock and sales pair for corrective replacement', async () => {
    const dhBatch = { ...batch, mtCode: 'DH', filename: 'stock.xlsx + sales.xlsx' }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (!init?.method) return new Response(JSON.stringify(dhBatch))
      if (url.endsWith('/dh-replacement-preview')) {
        return new Response(JSON.stringify({
          batchId: 18,
          businessFingerprint: 'd'.repeat(64),
          stockFilename: 'stock-fixed.xlsx',
          salesFilename: 'sales-fixed.xlsx',
          dataDate: '2026-08-02',
          current: batch.summary,
          replacement: { rowCount: 10, skuCount: 2, branchCount: 1, sourceAmount: 100, amount: 99, salesQty: 4, stockOnHand: 20, negativeRowCount: 0 },
          warnings: [],
          canReplace: true,
          blockedReason: null,
        }))
      }
      return new Response(JSON.stringify({ ...dhBatch, warnings: [] }))
    })

    render(<ImportCorrectivePanel batchId={18} />)
    await screen.findByText('Stock On Hand: calculated=77904, source=77379')
    const stock = new File(['stock'], 'stock-fixed.xlsx')
    const sales = new File(['sales'], 'sales-fixed.xlsx')
    await userEvent.upload(screen.getByLabelText('ไฟล์ Stock ของ DH ที่แก้ไขแล้ว'), stock)
    await userEvent.upload(screen.getByLabelText('ไฟล์ Sale ของ DH ที่แก้ไขแล้ว'), sales)
    await userEvent.click(screen.getByRole('button', { name: 'Preview เปรียบเทียบ' }))

    expect(await screen.findByText('stock-fixed.xlsx + sales-fixed.xlsx')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'ยืนยันแทนที่ Batch 18' }))

    const previewCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/dh-replacement-preview'))
    const replaceCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/dh-replace'))
    expect((previewCall?.[1]?.body as FormData).get('stock_file')).toBe(stock)
    expect((previewCall?.[1]?.body as FormData).get('sales_file')).toBe(sales)
    expect((replaceCall?.[1]?.body as FormData).get('expected_fingerprint')).toBe('d'.repeat(64))
  })
})
