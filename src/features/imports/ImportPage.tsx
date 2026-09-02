import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileSpreadsheet, History, LoaderCircle } from 'lucide-react'
import { confirmImport, fetchImportActivity, previewImport, type ImportActivity, type ImportPreview } from './importApi'
import { ImportCorrectivePanel } from './ImportCorrectivePanel'
import { formatDisplayDate, formatDisplayDateTime } from '../../shared/dateFormat'

const number = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

function statusLabel(status: string) {
  if (status === 'imported' || status === 'imported_with_warnings') return 'สำเร็จ'
  if (status === 'validated') return 'ตรวจสอบแล้ว'
  if (status === 'duplicate') return 'ข้อมูลซ้ำ'
  return 'ไม่สำเร็จ'
}

export function ImportPage({ correctiveBatchId = null }: { correctiveBatchId?: number | null }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [activities, setActivities] = useState<ImportActivity[]>([])
  const [busy, setBusy] = useState<'preview' | 'confirm' | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const loadActivity = () => fetchImportActivity().then(setActivities).catch(() => undefined)
  useEffect(() => { void loadActivity() }, [])

  const inspect = async (selectedFile: File) => {
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    try {
      setPreview(await previewImport(selectedFile))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบไฟล์ไม่สำเร็จ')
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
      void loadActivity()
    } finally {
      setBusy(null)
    }
  }

  const confirm = async () => {
    if (!file || !preview?.canImport) return
    setBusy('confirm')
    setMessage(null)
    try {
      const result = await confirmImport(file, preview.checksum)
      setMessage(`${result.message} · ${result.notification.message}`)
      setFile(null)
      setPreview(null)
      if (inputRef.current) inputRef.current.value = ''
      void loadActivity()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'นำเข้าข้อมูลไม่สำเร็จ')
      void loadActivity()
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="import-page page-content">
      {correctiveBatchId !== null && <ImportCorrectivePanel batchId={correctiveBatchId} onCompleted={() => void loadActivity()} />}
      <section className="import-workflow" aria-labelledby="import-heading">
        <header className="import-intro">
          <div>
            <span className="eyebrow">Manual data import</span>
            <h2 id="import-heading">นำเข้าข้อมูล</h2>
            <p>เลือก Raw Data ครั้งละหนึ่งไฟล์ ระบบจะตรวจสอบและแสดงข้อมูลก่อนนำเข้าจริง</p>
          </div>
          <span className="import-scope"><strong>Phase 1</strong>TWD · .xls</span>
        </header>

        <div className="upload-stage">
          <span className="stage-number">1</span>
          <FileSpreadsheet size={28} aria-hidden="true" />
          <div className="file-control">
            <label htmlFor="raw-data-file">เลือกไฟล์ Raw Data</label>
            <input
              ref={inputRef}
              id="raw-data-file"
              type="file"
              accept=".xls"
              disabled={busy !== null}
              onChange={(event) => {
                const selectedFile = event.target.files?.[0] ?? null
                setFile(selectedFile)
                setPreview(null)
                setMessage(null)
                if (selectedFile) void inspect(selectedFile)
              }}
            />
            <small>{file ? `${file.name} · ${number.format(file.size / 1024)} KB` : 'รองรับไฟล์ TWD .xls ขนาดไม่เกิน 25 MB'}</small>
          </div>
          {busy === 'preview' && <span className="upload-auto-status" role="status"><LoaderCircle className="is-spinning" size={16} aria-hidden="true" />กำลังตรวจสอบไฟล์…</span>}
        </div>

        {message && <div className="import-message" role="status">{message}</div>}

        {preview && (
          <div className="preview-stage" data-blocked={!preview.canImport || undefined}>
            <header>
              <div><span className="stage-number">2</span><div><span className="eyebrow">ผลการตรวจสอบ</span><h3>{preview.detectedMtName} · {formatDisplayDate(preview.dataDate)}</h3></div></div>
              <span className={`preview-state ${preview.canImport ? 'ready' : 'blocked'}`}>
                {preview.canImport ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                {preview.canImport ? 'พร้อมนำเข้า' : 'ไม่สามารถนำเข้า'}
              </span>
            </header>
            <dl className="preview-grid">
              <div><dt>MT</dt><dd>{preview.detectedMt}</dd></div>
              <div><dt>วันที่ข้อมูล</dt><dd>{formatDisplayDate(preview.dataDate)}</dd></div>
              <div><dt>รายการ</dt><dd>{number.format(preview.rowCount)}</dd></div>
              <div><dt>SKU</dt><dd>{number.format(preview.skuCount)}</dd></div>
              <div><dt>Branch</dt><dd>{number.format(preview.branchCount)}</dd></div>
              <div><dt>Amount</dt><dd>{number.format(preview.amount)}</dd></div>
              <div><dt>Sales Qty</dt><dd>{number.format(preview.salesQty)}</dd></div>
              <div><dt>Return rows</dt><dd>{number.format(preview.negativeRowCount)}</dd></div>
            </dl>
            {preview.warnings.length > 0 && <div className="preview-warning"><AlertTriangle size={16} />{preview.warnings.join(' · ')}</div>}
            {preview.duplicateReason && <div className="preview-warning blocked"><AlertTriangle size={16} />{preview.duplicateReason}</div>}
            <footer>
              <small>ระบบจะตรวจ checksum และวันที่ข้อมูลซ้ำอีกครั้งก่อนบันทึก</small>
              <button className="primary-action" type="button" disabled={!preview.canImport || busy !== null} onClick={() => void confirm()}>
                {busy === 'confirm' ? 'กำลังนำเข้า…' : 'ยืนยันนำเข้าข้อมูล'}
              </button>
            </footer>
          </div>
        )}
      </section>

      <section className="activity-panel" aria-labelledby="activity-heading">
        <header><div><History size={18} aria-hidden="true" /><div><span className="eyebrow">Activity log</span><h3 id="activity-heading">ประวัติการทำงานล่าสุด</h3></div></div><button type="button" onClick={() => void loadActivity()}>Refresh</button></header>
        <div className="activity-list">
          {activities.length === 0 && <p className="empty-activity">ยังไม่มีประวัติ Manual Import</p>}
          {activities.map((item) => (
            <article key={item.id}>
              <span className={`activity-status ${item.status}`} aria-hidden="true" />
              <div><strong>{item.message}</strong><small>{item.mtCode} · {item.filename}{item.dataDate ? ` · ข้อมูล ${formatDisplayDate(item.dataDate)}` : ''}</small></div>
              <div className="activity-time"><span>{statusLabel(item.status)}</span><time>{formatDisplayDateTime(item.occurredAt)}</time></div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
