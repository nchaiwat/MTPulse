import { useState } from 'react'
import { AlertTriangle, Building2, CheckCircle2 } from 'lucide-react'
import {
  confirmHhImport,
  previewHhImport,
  type HhImportPreview,
  type UploadProgress,
} from './importApi'
import { formatDisplayDate } from '../../shared/dateFormat'

const number = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

export function HhImportPanel({ onCompleted }: { onCompleted: () => void }) {
  const [files, setFiles] = useState<{ stock: File | null; sales: File | null }>({
    stock: null,
    sales: null,
  })
  const [preview, setPreview] = useState<HhImportPreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'confirm' | null>(null)
  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const inspect = async () => {
    if (!files.stock || !files.sales) return
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    try {
      setPreview(await previewHhImport(files.stock, files.sales, setProgress))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบคู่ไฟล์ HomeHub ไม่สำเร็จ')
      onCompleted()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  const confirm = async () => {
    if (!preview?.canImport || !files.stock || !files.sales) return
    setBusy('confirm')
    setMessage(null)
    try {
      const result = await confirmHhImport(
        files.stock,
        files.sales,
        preview.businessFingerprint,
        setProgress,
      )
      setMessage(result.message)
      setFiles({ stock: null, sales: null })
      setPreview(null)
      onCompleted()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'นำเข้าข้อมูล HomeHub ไม่สำเร็จ')
      onCompleted()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  return (
    <section
      id="import-panel-HH"
      className="import-workflow import-hp-mh-workflow"
      role="tabpanel"
      aria-labelledby="import-tab-HH"
    >
      <header className="import-workflow-heading">
        <div><span className="eyebrow">HH manual import</span><h2>HomeHub (HH)</h2></div>
        <span className="import-format-note">Daily pair · 2 Excel files</span>
      </header>

      <div className="hp-mh-source-note">
        <Building2 size={18} aria-hidden="true" />
        <p>
          เลือก StockReport.xlsx และ SaleReport.xlsx ของวันเดียวกัน ระบบจะตรวจวันที่
          โครงสร้าง และ Modern Trade ก่อนบันทึก โดยเก็บ SKU ทุกความยาวเป็นข้อความ
        </p>
      </div>

      <div className="hp-mh-file-grid">
        <label>
          <span>1 · StockReport.xlsx</span>
          <input
            type="file"
            accept=".xlsx"
            disabled={busy !== null}
            onChange={(event) => {
              setFiles((current) => ({ ...current, stock: event.target.files?.[0] ?? null }))
              setPreview(null)
              setMessage(null)
            }}
          />
          <small>{files.stock ? `${files.stock.name} · ${number.format(files.stock.size / 1024)} KB` : 'ไฟล์ Stock ของ HomeHub'}</small>
        </label>
        <label>
          <span>2 · SaleReport.xlsx</span>
          <input
            type="file"
            accept=".xlsx"
            disabled={busy !== null}
            onChange={(event) => {
              setFiles((current) => ({ ...current, sales: event.target.files?.[0] ?? null }))
              setPreview(null)
              setMessage(null)
            }}
          />
          <small>{files.sales ? `${files.sales.name} · ${number.format(files.sales.size / 1024)} KB` : 'ไฟล์ Sale ของ HomeHub'}</small>
        </label>
        <button className="primary-action hp-mh-preview-action" type="button" disabled={!files.stock || !files.sales || busy !== null} onClick={() => void inspect()}>
          {busy === 'preview' ? 'กำลังตรวจสอบ…' : 'ตรวจสอบคู่ไฟล์'}
        </button>
      </div>

      {progress && (
        <div className="import-transfer" role="status">
          <div><span>{progress.phase === 'uploading' ? 'กำลังส่งไฟล์เข้า Server' : 'กำลังอ่านและตรวจข้อมูล'}</span><strong>{progress.phase === 'uploading' ? `${progress.percent}%` : 'โปรดรอสักครู่'}</strong></div>
          <div className="import-transfer-track" data-indeterminate={progress.phase !== 'uploading' || undefined}><span style={{ width: progress.phase === 'uploading' ? `${progress.percent}%` : '38%' }} /></div>
        </div>
      )}
      {message && <div className="import-message" role="status">{message}</div>}

      {preview && (
        <div className="preview-stage hp-mh-preview" data-blocked={!preview.canImport || undefined}>
          <header>
            <div><span className="stage-number">3</span><div><span className="eyebrow">ผลการตรวจสอบ</span><h3>HomeHub · {formatDisplayDate(preview.dataDate)}</h3></div></div>
            <span className={`preview-state ${preview.canImport ? 'ready' : 'blocked'}`}>
              {preview.canImport ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {preview.canImport
                ? preview.operation === 'replace' ? 'พร้อมแทนที่ข้อมูลเดิม' : 'พร้อมนำเข้า'
                : 'ไม่สามารถนำเข้า'}
            </span>
          </header>
          <div className="hp-mh-summary-grid">
            <article>
              <strong>HomeHub (HH)</strong>
              <dl>
                <div><dt>รายการ</dt><dd>{number.format(preview.summary.rowCount)}</dd></div>
                <div><dt>SKU</dt><dd>{number.format(preview.summary.skuCount)}</dd></div>
                <div><dt>Branch</dt><dd>{number.format(preview.summary.branchCount)}</dd></div>
                <div><dt>Amount</dt><dd>{number.format(preview.summary.amount)}</dd></div>
                <div><dt>Sales Qty</dt><dd>{number.format(preview.summary.salesQty)}</dd></div>
                <div><dt>Stock</dt><dd>{number.format(preview.summary.stockOnHand)}</dd></div>
              </dl>
            </article>
          </div>
          {preview.warnings.length > 0 && <div className="preview-warning"><AlertTriangle size={16} />{preview.warnings.join(' · ')}</div>}
          {preview.operation === 'replace' && (
            <div className="preview-warning"><AlertTriangle size={16} />วันนี้มีข้อมูลใน Batch {preview.replacementBatchId} แล้ว เมื่อยืนยันระบบจะแทนที่วันเดิมและเก็บ Audit Log</div>
          )}
          {preview.duplicateReason && <div className="preview-warning blocked"><AlertTriangle size={16} />{preview.duplicateReason}</div>}
          <footer>
            <small>SKU ที่ยังไม่ Mapping จะยังแสดงใน Report ด้วย WA Item “–” และสถานะ “ยังไม่ Mapping”</small>
            <button className="primary-action" type="button" disabled={!preview.canImport || busy !== null} onClick={() => void confirm()}>
              {busy === 'confirm'
                ? 'กำลังบันทึก…'
                : preview.operation === 'replace' ? 'ยืนยันแทนที่ข้อมูล HomeHub' : 'ยืนยันนำเข้า HomeHub'}
            </button>
          </footer>
        </div>
      )}
    </section>
  )
}
