import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TwdSettingsPage } from './TwdSettingsPage'

describe('TwdSettingsPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses two global controls for unmatched Branch and Item', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: false,
        mappingAttentionItems: 5,
        mappingAttentionBranches: 2,
        reportPageSize: 25,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: true,
        mappingAttentionItems: 5,
        mappingAttentionBranches: 2,
        reportPageSize: 25,
      }), { status: 200 }))

    render(<TwdSettingsPage />)

    expect(screen.getByRole('heading', { name: 'การตั้งค่าไทวัสดุ' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Item และ Branch Mapping' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export Mapping' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import Mapping' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'ความครบถ้วนของข้อมูล' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'ปี' })).toHaveValue(String(new Date().getFullYear()))
    await waitFor(() => expect(screen.getByLabelText('รายการ Mapping ที่ต้องตรวจ')).toHaveTextContent('5 Item'))
    expect(screen.getByLabelText('รายการ Mapping ที่ต้องตรวจ')).toHaveTextContent('2 Branch')
    expect(screen.getByRole('heading', { name: 'การแสดงผลรายงาน' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'จำนวน SKU ต่อหน้า' })).toHaveValue('25')
    expect(screen.getByRole('option', { name: 'ทั้งหมด' })).toHaveValue('0')
    expect(screen.getByRole('option', { name: '2025' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download สถานะข้อมูล' })).toBeInTheDocument()
    const branchSwitch = await screen.findByRole('switch', { name: 'แสดง Branch Unmatch' })
    expect(screen.getByRole('switch', { name: 'แสดง Item Unmatch' })).toHaveAttribute('aria-checked', 'false')
    expect(branchSwitch).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()

    await userEvent.click(branchSwitch)

    await waitFor(() => expect(branchSwitch).toHaveAttribute('aria-checked', 'true'))
    expect(screen.getByRole('status')).toHaveTextContent('นำไปรวมในรายงาน')
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/settings/twd/unmatched-visibility'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          show_unmatched_items: false,
          show_unmatched_branches: true,
        }),
      }),
    )
  })

  it('saves the report page size for TWD', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: false,
        mappingAttentionItems: 0,
        mappingAttentionBranches: 0,
        reportPageSize: 25,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        reportPageSize: 50,
      }), { status: 200 }))

    render(<TwdSettingsPage />)

    const pageSize = await screen.findByRole('combobox', { name: 'จำนวน SKU ต่อหน้า' })
    await userEvent.selectOptions(pageSize, '50')

    await waitFor(() => expect(pageSize).toHaveValue('50'))
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/settings/twd/report-page-size'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ report_page_size: 50 }),
      }),
    )
  })

  it('saves all SKUs as the report page size', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: false,
        mappingAttentionItems: 0,
        mappingAttentionBranches: 0,
        reportPageSize: 25,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ reportPageSize: 0 }), { status: 200 }))

    render(<TwdSettingsPage />)
    const pageSize = await screen.findByRole('combobox', { name: 'จำนวน SKU ต่อหน้า' })
    await userEvent.selectOptions(pageSize, '0')

    await waitFor(() => expect(pageSize).toHaveValue('0'))
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/settings/twd/report-page-size'),
      expect.objectContaining({ body: JSON.stringify({ report_page_size: 0 }) }),
    )
  })
})
