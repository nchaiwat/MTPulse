import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Search,
  Upload,
} from 'lucide-react'
import {
  confirmDhPriceMaster,
  downloadDhPriceTemplate,
  fetchDhPrices,
  previewDhPriceMaster,
  type DhPriceConfirmation,
  type DhPriceListPage,
  type DhPricePreview,
  type DhPriceStatus,
} from './dhPriceMasterApi'
import './dhPriceMaster.css'

const pageSize = 25
const emptyPage: DhPriceListPage = { items: [], total: 0, page: 1, page_size: pageSize }

const statusLabels: Record<DhPriceStatus, string> = {
  current: 'ใช้งานปัจจุบัน',
  upcoming: 'รอเริ่มใช้งาน',
  expired: 'หมดอายุ',
}

function formatDate(value: string | null) {
  if (!value) return 'ไม่กำหนด'
  return new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric' })
    .format(new Date(`${value}T00:00:00+07:00`))
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('th-TH', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

export function DhPriceMasterPanel() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<DhPricePreview | null>(null)
  const [confirmation, setConfirmation] = useState<DhPriceConfirmation | null>(null)
  const [action, setAction] = useState<'download' | 'preview' | 'confirm' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [status, setStatus] = useState<DhPriceStatus | ''>('')
  const [page, setPage] = useState(1)
  const [prices, setPrices] = useState<DhPriceListPage>(emptyPage)
  const [isLoadingPrices, setIsLoadingPrices] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 250)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    fetchDhPrices({ query: debouncedQuery, status, page, pageSize }, controller.signal)
      .then(setPrices)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setListError(error instanceof Error ? error.message : 'โหลดรายการราคาไม่สำเร็จ')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingPrices(false)
      })
    return () => controller.abort()
  }, [debouncedQuery, page, refreshKey, status])

  const handleDownload = async () => {
    setAction('download')
    setActionError(null)
    try {
      const result = await downloadDhPriceTemplate()
      saveBlob(result.blob, result.filename)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Download Template ไม่สำเร็จ')
    } finally {
      setAction(null)
    }
  }

  const handlePreview = async () => {
    if (!file) return
    setAction('preview')
    setActionError(null)
    setConfirmation(null)
    try {
      setPreview(await previewDhPriceMaster(file))
    } catch (error) {
      setPreview(null)
      setActionError(error instanceof Error ? error.message : 'Preview Price Master ไม่สำเร็จ')
    } finally {
      setAction(null)
    }
  }

  const handleConfirm = async () => {
    if (!file || !preview || preview.errors.length > 0) return
    setAction('confirm')
    setActionError(null)
    try {
      const result = await confirmDhPriceMaster(file, preview.preview_fingerprint)
      setConfirmation(result)
      setPreview(result)
      setIsLoadingPrices(true)
      setListError(null)
      setRefreshKey((current) => current + 1)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Confirm Price Master ไม่สำเร็จ')
    } finally {
      setAction(null)
    }
  }

  const totalPages = Math.max(1, Math.ceil(prices.total / pageSize))
  const hasBlockingErrors = Boolean(preview?.errors.length)

  return (
    <section className="dh-price-master settings-standard-section" aria-labelledby="dh-price-master-heading">
      <header>
        <span className="setting-icon"><FileSpreadsheet size={19} aria-hidden="true" /></span>
        <div>
          <span className="eyebrow">Effective-dated pricing</span>
          <h3 id="dh-price-master-heading">DH Price Master</h3>
          <p>ดูแลราคา Ex VAT สำหรับคำนวณยอดขาย DoHome โดย Preview ก่อนบันทึกทุกครั้ง</p>
        </div>
        <button className="secondary-action" type="button" disabled={action !== null} onClick={() => void handleDownload()}>
          <Download size={15} aria-hidden="true" />
          {action === 'download' ? 'กำลัง Download…' : 'Download Template'}
        </button>
      </header>

      <div className="dh-price-upload" aria-label="Upload DH Price Master">
        <div className="dh-price-file">
          <label htmlFor="dh-price-file">เลือกไฟล์ DH Price Master</label>
          <input
            ref={fileInputRef}
            id="dh-price-file"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              setPreview(null)
              setConfirmation(null)
              setActionError(null)
            }}
          />
          <small>รองรับ .xlsx ไม่เกิน 10 MB · SKU จะถูกอ่านเป็นข้อความ</small>
        </div>
        <div className="dh-price-upload-actions">
          <button className="secondary-action" type="button" disabled={!file || action !== null} onClick={() => void handlePreview()}>
            <FileCheck2 size={15} aria-hidden="true" />
            {action === 'preview' ? 'กำลัง Preview…' : 'Preview ราคา'}
          </button>
          <button className="primary-action" type="button" disabled={!file || !preview || hasBlockingErrors || action !== null} onClick={() => void handleConfirm()}>
            <Upload size={15} aria-hidden="true" />
            {action === 'confirm' ? 'กำลังยืนยัน…' : 'ยืนยัน Price Master'}
          </button>
        </div>
      </div>

      {actionError && <div className="dh-price-message" data-tone="error" role="alert">{actionError}</div>}

      {preview && (
        <div className="dh-price-preview" aria-label="ผล Preview DH Price Master">
          <div aria-label="เพิ่มใหม่"><span>เพิ่มใหม่</span><strong>{preview.inserted.toLocaleString('en-US')}</strong></div>
          <div aria-label="อัปเดต"><span>อัปเดต</span><strong>{preview.updated.toLocaleString('en-US')}</strong></div>
          <div aria-label="ไม่เปลี่ยนแปลง"><span>ไม่เปลี่ยนแปลง</span><strong>{preview.unchanged.toLocaleString('en-US')}</strong></div>
          <small>{preview.candidate_count.toLocaleString('en-US')} รายการพร้อมตรวจ · {preview.row_count.toLocaleString('en-US')} แถวในไฟล์</small>
        </div>
      )}

      {preview && hasBlockingErrors && (
        <div className="dh-price-blocking" role="alert">
          <AlertTriangle size={17} aria-hidden="true" />
          <div>
            <strong>ยังยืนยันไม่ได้</strong>
            <ul>{preview.errors.map((error) => <li key={error}>{error}</li>)}</ul>
          </div>
        </div>
      )}

      {confirmation && (
        <div className="dh-price-message" role="status">
          ยืนยัน Price Master แล้วโดย <strong>{confirmation.confirmed_by}</strong> เมื่อ {formatDateTime(confirmation.confirmed_at)} · เพิ่มใหม่ {confirmation.inserted.toLocaleString('en-US')} · อัปเดต {confirmation.updated.toLocaleString('en-US')} · ไม่เปลี่ยนแปลง {confirmation.unchanged.toLocaleString('en-US')}
        </div>
      )}

      <div className="dh-price-list-heading">
        <div>
          <span className="eyebrow">Read-only ledger</span>
          <h4>รายการราคาตามช่วงวันที่</h4>
        </div>
        <span>{prices.total.toLocaleString('en-US')} รายการ</span>
      </div>

      <div className="dh-price-filters">
        <label>
          <span>ค้นหา SKU</span>
          <span className="dh-price-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              aria-label="ค้นหา SKU"
              value={query}
              placeholder="รหัส SKU"
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
                setIsLoadingPrices(true)
                setListError(null)
              }}
            />
          </span>
        </label>
        <label>
          <span>สถานะราคา</span>
          <select
            aria-label="กรองสถานะราคา"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as DhPriceStatus | '')
              setPage(1)
              setIsLoadingPrices(true)
              setListError(null)
            }}
          >
            <option value="">ทุกสถานะ</option>
            <option value="current">ใช้งานปัจจุบัน</option>
            <option value="upcoming">รอเริ่มใช้งาน</option>
            <option value="expired">หมดอายุ</option>
          </select>
        </label>
      </div>

      <div className="dh-price-table-shell">
        <table>
          <caption className="sr-only">รายการ DH Price Master แบบอ่านอย่างเดียว</caption>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">ราคา Ex VAT</th>
              <th scope="col">เริ่มใช้</th>
              <th scope="col">สิ้นสุด</th>
              <th scope="col">สถานะ</th>
              <th scope="col">แก้ไขล่าสุด</th>
            </tr>
          </thead>
          <tbody>
            {isLoadingPrices && <tr><td colSpan={6} className="dh-price-table-state">กำลังโหลดรายการราคา…</td></tr>}
            {!isLoadingPrices && listError && <tr><td colSpan={6} className="dh-price-table-state" data-tone="error">{listError}</td></tr>}
            {!isLoadingPrices && !listError && prices.items.length === 0 && (
              <tr><td colSpan={6} className="dh-price-table-state">ยังไม่พบราคาในเงื่อนไขนี้ ลองเปลี่ยนคำค้นหาหรือสถานะ</td></tr>
            )}
            {!isLoadingPrices && !listError && prices.items.map((item) => (
              <tr key={`${item.source_sku}-${item.effective_from}`}>
                <th scope="row">{item.source_sku}</th>
                <td className="dh-price-number">{Number(item.unit_price_ex_vat).toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}</td>
                <td>{formatDate(item.effective_from)}</td>
                <td>{formatDate(item.effective_to)}</td>
                <td><span className="dh-price-status" data-status={item.status}>{statusLabels[item.status]}</span></td>
                <td><strong>{item.changed_by}</strong><small>{formatDateTime(item.changed_at)}</small></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="dh-price-pagination">
        <span>หน้า {prices.page.toLocaleString('en-US')} / {totalPages.toLocaleString('en-US')}</span>
        <div>
          <button type="button" aria-label="หน้าก่อนหน้า" disabled={page <= 1 || isLoadingPrices} onClick={() => { setIsLoadingPrices(true); setListError(null); setPage((current) => Math.max(1, current - 1)) }}>
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <button type="button" aria-label="หน้าถัดไป" disabled={page >= totalPages || isLoadingPrices} onClick={() => { setIsLoadingPrices(true); setListError(null); setPage((current) => current + 1) }}>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </div>
      </footer>
    </section>
  )
}
