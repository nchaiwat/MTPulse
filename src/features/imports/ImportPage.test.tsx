import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ImportPage } from './ImportPage'

const api = vi.hoisted(() => ({
  confirmFileShareImport: vi.fn(),
  confirmFolderImportBatch: vi.fn(),
  confirmHpMhImport: vi.fn(),
  confirmImport: vi.fn(),
  createFolderImportBatch: vi.fn(),
  fetchFileShareReady: vi.fn(),
  fetchFolderImportBatch: vi.fn(),
  fetchImportActivity: vi.fn(),
  finalizeFolderImportBatch: vi.fn(),
  previewFileShareImport: vi.fn(),
  previewHpMhImport: vi.fn(),
  previewImport: vi.fn(),
  uploadFolderImportFile: vi.fn(),
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

const hpMhPreview = {
  detectedSourceGroup: 'HP_MH' as const,
  detectedMtCodes: ['HP', 'MH'] as ['HP', 'MH'],
  dataDate: '2026-09-09',
  inventoryFilename: 'Inventory.zip',
  salesFilename: 'Sales.zip',
  businessFingerprint: 'b'.repeat(64),
  summaries: {
    HP: {
      rowCount: 120,
      skuCount: 30,
      branchCount: 20,
      amount: 1000,
      salesQty: 40,
      stockOnHand: 500,
      stockValue: 7500,
      negativeRowCount: 0,
    },
    MH: {
      rowCount: 80,
      skuCount: 25,
      branchCount: 11,
      amount: 800,
      salesQty: 30,
      stockOnHand: 300,
      stockValue: 4500,
      negativeRowCount: 0,
    },
  },
  warnings: [],
  canImport: true,
  duplicateReason: null,
}

const folderBatch = {
  id: 50,
  sourceMode: 'folder',
  status: 'uploading',
  detectionStatus: 'pending',
  detectedSourceGroup: null,
  requestedBy: 'development-admin',
  createdAt: '2026-09-10T10:00:00+07:00',
  expiresAt: '2026-09-17T10:00:00+07:00',
  counts: {
    total: 2,
    uploaded: 0,
    new: 0,
    duplicate: 0,
    eligible: 0,
    imported: 0,
    failed: 0,
    needsReview: 0,
  },
  files: [],
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
    api.previewHpMhImport.mockResolvedValue(hpMhPreview)
    api.confirmImport.mockResolvedValue(success)
    api.confirmFileShareImport.mockResolvedValue(success)
    api.confirmHpMhImport.mockResolvedValue({
      ...success,
      batchIds: { HP: 31, MH: 32 },
      status: 'imported',
      dataDate: '2026-09-09',
    })
    api.createFolderImportBatch.mockResolvedValue(folderBatch)
    api.uploadFolderImportFile.mockResolvedValue({
      id: 1,
      filename: 'file.xls',
      status: 'uploaded',
      detectionStatus: 'detected',
      detectedSourceGroup: 'TWD',
      sourceKind: 'workbook',
      reason: null,
    })
    api.finalizeFolderImportBatch.mockResolvedValue({
      ...folderBatch,
      status: 'awaiting_confirmation',
      detectionStatus: 'detected',
      detectedSourceGroup: 'TWD',
      counts: { ...folderBatch.counts, uploaded: 2, eligible: 2, new: 2 },
    })
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

  it('separates overview and activity by Modern Trade without changing TWD workflow', async () => {
    api.fetchImportActivity.mockResolvedValue([
      {
        id: 1,
        occurredAt: '2026-09-10T08:00:00+07:00',
        action: 'import',
        status: 'imported',
        message: 'TWD import completed',
        filename: 'twd.xls',
        mtCode: 'TWD',
        dataDate: '2026-09-09',
        batchId: 10,
      },
      {
        id: 2,
        occurredAt: '2026-09-10T08:05:00+07:00',
        action: 'import',
        status: 'imported',
        message: 'HP import completed',
        filename: 'hp.zip',
        mtCode: 'HP',
        dataDate: '2026-09-09',
        batchId: 11,
      },
    ])

    render(<ImportPage />)

    expect(screen.getByRole('tab', { name: /TWD/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('เลือกไฟล์ Raw Data จากเครื่อง')).toBeInTheDocument()
    expect(await screen.findByText('TWD import completed')).toBeInTheDocument()
    expect(screen.queryByText('HP import completed')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /ภาพรวม/ }))
    expect(screen.getAllByText('HP import completed')).toHaveLength(2)
    expect(screen.queryByLabelText('เลือกไฟล์ Raw Data จากเครื่อง')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /HP/ }))
    expect(screen.getByText('HP import completed')).toBeInTheDocument()
    expect(screen.queryByText('TWD import completed')).not.toBeInTheDocument()
    expect(screen.getByText(/HP และ MH ใช้คู่ไฟล์เดียวกัน/)).toBeInTheDocument()
  })

  it('provides a real HP/MH pair upload action and confirms both MTs together', async () => {
    render(<ImportPage />)
    await userEvent.click(screen.getByRole('tab', { name: /HP/ }))

    const inventory = new File(['inventory'], 'Inventory.zip', { type: 'application/zip' })
    const sales = new File(['sales'], 'Sales.zip', { type: 'application/zip' })
    await userEvent.upload(screen.getByLabelText(/Inventory ZIP/), inventory)
    await userEvent.upload(screen.getByLabelText(/Sales ZIP/), sales)
    await userEvent.click(screen.getByRole('button', { name: 'ตรวจสอบคู่ไฟล์' }))

    expect(await screen.findByText('HP + MH · 09/09/2026')).toBeInTheDocument()
    expect(api.previewHpMhImport).toHaveBeenCalledWith(
      inventory,
      sales,
      expect.any(Function),
    )

    await userEvent.click(screen.getByRole('button', { name: 'ยืนยันนำเข้า HP และ MH' }))
    expect(api.confirmHpMhImport).toHaveBeenCalledWith(
      inventory,
      sales,
      hpMhPreview.businessFingerprint,
      expect.any(Function),
    )
    expect(await screen.findByText(/นำเข้าข้อมูลสำเร็จ/)).toBeInTheDocument()
  })

  it('offers Admin Folder Import for both TWD and HP/MH', async () => {
    render(<ImportPage />)
    await userEvent.click(screen.getByRole('button', { name: /ทั้ง Folder/ }))
    expect(screen.getByLabelText('เลือก Folder สำหรับ TWD')).toHaveAttribute('webkitdirectory')

    const files = [
      new File(['one'], 'one.xls'),
      new File(['two'], 'two.xls'),
    ]
    await userEvent.upload(screen.getByLabelText('เลือก Folder สำหรับ TWD'), files)
    await userEvent.click(screen.getByRole('button', { name: 'ตรวจสอบ Folder' }))
    expect(api.createFolderImportBatch).toHaveBeenCalledWith(2)
    expect(api.uploadFolderImportFile).toHaveBeenCalledTimes(2)
    expect(api.finalizeFolderImportBatch).toHaveBeenCalledWith(50, 'TWD')
    expect(await screen.findByRole('button', { name: 'ยืนยันนำเข้า Folder' })).toBeEnabled()

    await userEvent.click(screen.getByRole('tab', { name: /HP/ }))
    expect(screen.getByLabelText('เลือก Folder สำหรับ HP_MH')).toHaveAttribute('webkitdirectory')
  })
})
