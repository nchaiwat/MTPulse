import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SkuBackfillPanel } from './SkuBackfillPanel'

describe('SkuBackfillPanel', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows an unmapped SKU but blocks Preview until Mapping is confirmed', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        mappings: [{
          sourceSku: 'SKU-MAPPED',
          sourceDescription: 'Mapped product',
          waItemCode: 'WA-1',
          waItemDescription: null,
          effectiveFrom: '2025-01-01',
        }],
        unmappedSkus: [{
          sourceSku: 'SKU-IGNORED',
          sourceDescription: 'Interesting later',
          interestStatus: 'ignored',
          firstSeenDate: '2025-02-01',
          lastSeenDate: '2026-09-01',
        }],
        registry: {
          earliestDate: '2025-01-01',
          latestDate: '2026-09-01',
          refreshedAt: '2026-09-07T09:00:00+07:00',
        },
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ runs: [] }), { status: 200 }))

    render(<SkuBackfillPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'เปิดเครื่องมือ Backfill' }))

    const skuSelect = await screen.findByRole('combobox', { name: 'SKU สำหรับ Backfill' })
    await userEvent.selectOptions(skuSelect, 'SKU-IGNORED')

    await waitFor(() => expect(screen.getByText('SKU SKU-IGNORED ยังไม่ได้ Mapping')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Preview ก่อนเริ่ม' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'ไปกำหนด Mapping' })).toBeEnabled()
    expect(screen.getByText(/เปลี่ยน SKU นี้เป็น Active โดยอัตโนมัติ/)).toBeInTheDocument()
  })
})
