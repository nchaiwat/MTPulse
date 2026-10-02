import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DhPriceMasterPanel } from './DhPriceMasterPanel'
import * as api from './dhPriceMasterApi'

vi.mock('./dhPriceMasterApi', async () => {
  const actual = await vi.importActual<typeof import('./dhPriceMasterApi')>('./dhPriceMasterApi')
  return {
    ...actual,
    downloadDhPriceTemplate: vi.fn(),
    previewDhPriceMaster: vi.fn(),
    confirmDhPriceMaster: vi.fn(),
    fetchDhPrices: vi.fn(),
  }
})

const emptyPage = { items: [], total: 0, page: 1, page_size: 25 }
const validPreview = {
  row_count: 3,
  candidate_count: 3,
  inserted: 1,
  updated: 1,
  unchanged: 1,
  source_checksum_sha256: 'a'.repeat(64),
  preview_fingerprint: 'b'.repeat(64),
  errors: [],
}

describe('DhPriceMasterPanel', () => {
  afterEach(() => vi.clearAllMocks())

  it('previews then confirms a valid workbook and reports actor and time', async () => {
    vi.mocked(api.fetchDhPrices).mockResolvedValue(emptyPage)
    vi.mocked(api.previewDhPriceMaster).mockResolvedValue(validPreview)
    vi.mocked(api.confirmDhPriceMaster).mockResolvedValue({
      ...validPreview,
      confirmed_by: 'data-operator@test',
      confirmed_at: '2026-09-16T10:15:00+07:00',
    })
    const user = userEvent.setup()
    render(<DhPriceMasterPanel />)

    expect(screen.getByRole('heading', { name: 'DH Price Master' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ยืนยัน Price Master' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: /แก้ไข|ลบ/ })).not.toBeInTheDocument()

    const file = new File(['price'], 'dh-prices.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    await user.upload(screen.getByLabelText('เลือกไฟล์ DH Price Master'), file)
    await user.click(screen.getByRole('button', { name: 'Preview ราคา' }))

    expect(await screen.findByText('เพิ่มใหม่')).toBeInTheDocument()
    expect(screen.getByLabelText('เพิ่มใหม่')).toHaveTextContent('1')
    expect(screen.getByLabelText('อัปเดต')).toHaveTextContent('1')
    expect(screen.getByLabelText('ไม่เปลี่ยนแปลง')).toHaveTextContent('1')

    await user.click(screen.getByRole('button', { name: 'ยืนยัน Price Master' }))

    expect(await screen.findByRole('status')).toHaveTextContent('data-operator@test')
    expect(screen.getByRole('status')).toHaveTextContent('16 ก.ย. 2569')
    expect(api.confirmDhPriceMaster).toHaveBeenCalledWith(file, validPreview.preview_fingerprint)
  })

  it('keeps confirm disabled and exposes blocking errors', async () => {
    vi.mocked(api.fetchDhPrices).mockResolvedValue(emptyPage)
    vi.mocked(api.previewDhPriceMaster).mockResolvedValue({
      ...validPreview,
      candidate_count: 0,
      inserted: 0,
      updated: 0,
      unchanged: 0,
      errors: ['แถว 2: Price Ex VAT ต้องมากกว่า 0'],
    })
    const user = userEvent.setup()
    render(<DhPriceMasterPanel />)

    await user.upload(
      screen.getByLabelText('เลือกไฟล์ DH Price Master'),
      new File(['price'], 'invalid.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
    )
    await user.click(screen.getByRole('button', { name: 'Preview ราคา' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Price Ex VAT ต้องมากกว่า 0')
    expect(screen.getByRole('button', { name: 'ยืนยัน Price Master' })).toBeDisabled()
    expect(api.confirmDhPriceMaster).not.toHaveBeenCalled()
  })

  it('loads a read-only filtered price table', async () => {
    vi.mocked(api.fetchDhPrices).mockResolvedValue({
      items: [{
        source_sku: '00123',
        unit_price_ex_vat: '125.5000',
        effective_from: '2026-09-01',
        effective_to: null,
        status: 'current',
        source_filename: 'prices.xlsx',
        changed_by: 'admin@test',
        changed_at: '2026-09-15T11:00:00+07:00',
      }],
      total: 30,
      page: 1,
      page_size: 25,
    })
    const user = userEvent.setup()
    render(<DhPriceMasterPanel />)

    expect(await screen.findByRole('rowheader', { name: '00123' })).toBeInTheDocument()
    expect(screen.getAllByText('ใช้งานปัจจุบัน')).toHaveLength(2)
    expect(screen.getByRole('searchbox', { name: 'ค้นหา SKU' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'กรองสถานะราคา' })).toBeInTheDocument()
    await waitFor(() => expect(api.fetchDhPrices).toHaveBeenCalledWith(expect.objectContaining({ page: 1, pageSize: 25 }), expect.any(AbortSignal)))

    await user.type(screen.getByRole('searchbox', { name: 'ค้นหา SKU' }), '00123')
    await user.selectOptions(screen.getByRole('combobox', { name: 'กรองสถานะราคา' }), 'current')
    await waitFor(() => expect(api.fetchDhPrices).toHaveBeenCalledWith(
      expect.objectContaining({ query: '00123', status: 'current', page: 1 }),
      expect.any(AbortSignal),
    ))

    await user.click(screen.getByRole('button', { name: 'หน้าถัดไป' }))
    await waitFor(() => expect(api.fetchDhPrices).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2 }),
      expect.any(AbortSignal),
    ))
  })
})
