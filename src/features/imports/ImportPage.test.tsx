import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ImportPage } from './ImportPage'

const api = vi.hoisted(() => ({
  confirmFileShareImport: vi.fn(),
  confirmImport: vi.fn(),
  fetchFileShareReady: vi.fn(),
  fetchImportActivity: vi.fn(),
  previewFileShareImport: vi.fn(),
  previewImport: vi.fn(),
}))

vi.mock('./importApi', async () => {
  const actual = await vi.importActual<typeof import('./importApi')>('./importApi')
  return { ...actual, ...api }
})

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
  timings: { parseMs: 420, duplicateCheckMs: 4 },
}

const success = {
  message: 'นำเข้าข้อมูลสำเร็จ',
  pendingSkus: [],
  notification: { status: 'skipped', message: 'ยังไม่ได้ตั้งค่า Telegram' },
}

describe('ImportPage', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset())
    api.fetchImportActivity.mockResolvedValue([])
    api.fetchFileShareReady.mockResolvedValue([])
    api.previewImport.mockResolvedValue(preview)
    api.previewFileShareImport.mockResolvedValue({
      ...preview,
      sourceMode: 'fileshare',
      sourceFileId: 21,
    })
    api.confirmImport.mockResolvedValue(success)
    api.confirmFileShareImport.mockResolvedValue(success)
  })

  it('previews one TWD file and requires confirmation', async () => {
    render(<ImportPage />)
    const file = new File(['raw'], 'twd.xls', { type: 'application/vnd.ms-excel' })
    await userEvent.upload(screen.getByLabelText('เลือกไฟล์ Raw Data จากเครื่อง'), file)
    expect(await screen.findByText('ไทวัสดุ · 18/08/2026')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ตรวจสอบไฟล์' })).not.toBeInTheDocument()
    expect(screen.getByText('อ่านและตรวจ Excel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ยืนยันนำเข้าข้อมูล' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'ยืนยันนำเข้าข้อมูล' }))
    expect(await screen.findByText(/นำเข้าข้อมูลสำเร็จ/)).toBeInTheDocument()
    expect(api.confirmImport).toHaveBeenCalledWith(file, preview.checksum, expect.any(Function))
  })

  it('shows byte progress while a local file is uploading', async () => {
    let finishPreview: (value: typeof preview) => void = () => undefined
    api.previewImport.mockImplementation((_file, onProgress) => {
      onProgress?.({
        phase: 'uploading',
        loaded: 42,
        total: 100,
        percent: 42,
      })
      return new Promise((resolve) => { finishPreview = resolve })
    })
    render(<ImportPage />)
    const file = new File(['raw'], 'twd.xls', { type: 'application/vnd.ms-excel' })
    await userEvent.upload(screen.getByLabelText('เลือกไฟล์ Raw Data จากเครื่อง'), file)
    expect(screen.getByText('กำลังส่งไฟล์เข้า Server')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42')
    await act(async () => finishPreview(preview))
    expect(await screen.findByText('ไทวัสดุ · 18/08/2026')).toBeInTheDocument()
  })

  it('previews and confirms a ready file from FileShare', async () => {
    api.fetchFileShareReady.mockResolvedValue([
      {
        id: 21,
        filename: 'latest.xls',
        dataDate: '2026-08-31',
        sizeBytes: 5_652_416,
        discoveredAt: '2026-09-03T08:00:00+07:00',
      },
    ])
    render(<ImportPage />)
    await userEvent.click(screen.getByRole('button', { name: 'จาก FileShare' }))
    expect(await screen.findByText('latest.xls')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'ตรวจสอบ' }))
    expect(await screen.findByText('ไทวัสดุ · 18/08/2026')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'ยืนยันนำเข้าข้อมูล' }))
    expect(api.previewFileShareImport).toHaveBeenCalledWith(21)
    expect(api.confirmFileShareImport).toHaveBeenCalledWith(21, preview.checksum)
    expect(await screen.findByText(/นำเข้าข้อมูลสำเร็จ/)).toBeInTheDocument()
  })

  it('explains how to populate an empty FileShare registry', async () => {
    render(<ImportPage />)
    await userEvent.click(screen.getByRole('button', { name: 'จาก FileShare' }))
    expect(await screen.findByText(/ยังไม่มีไฟล์พร้อมนำเข้า/)).toBeInTheDocument()
    expect(screen.getByText(/Initial Scan หรือ Run ทันที/)).toBeInTheDocument()
  })

  it('offers retry when the FileShare registry cannot be loaded', async () => {
    api.fetchFileShareReady
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce([])
    render(<ImportPage />)
    await userEvent.click(screen.getByRole('button', { name: 'จาก FileShare' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('โหลดรายการไม่สำเร็จ')
    await userEvent.click(screen.getByRole('button', { name: 'ลองใหม่' }))
    expect(await screen.findByText(/ยังไม่มีไฟล์พร้อมนำเข้า/)).toBeInTheDocument()
    expect(api.fetchFileShareReady).toHaveBeenCalledTimes(2)
  })
})
