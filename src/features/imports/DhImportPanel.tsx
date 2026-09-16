import { useState } from 'react'
import { AlertTriangle, Building2, CheckCircle2 } from 'lucide-react'
import {
  confirmDhImport,
  previewDhImport,
  type DhImportPreview,
  type UploadProgress,
} from './importApi'
import { formatDisplayDate } from '../../shared/dateFormat'

const number = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

export function DhImportPanel({ onCompleted }: { onCompleted: () => void }) {
  const [files, setFiles] = useState<{ stock: File | null; sales: File | null }>({
    stock: null,
    sales: null,
  })
  const [preview, setPreview] = useState<DhImportPreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'confirm' | null>(null)
  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const inspect = async () => {
    if (!files.stock || !files.sales) return
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    try {
      setPreview(await previewDhImport(files.stock, files.sales, setProgress))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบคู่ไฟล์ DoHome ไม่สำเร็จ')
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
      const result = await confirmDhImport(
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
      setMessage(error instanceof Error ? error.message : 'นำเข้าข้อมูล DoHome ไม่สำเร็จ')
      onCompleted()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  return (
    <section
      id="import-panel-DH"
      className="import-workflow import-hp-mh-workflow"
      role="tabpanel"
      aria-labelledby="import-tab-DH"
    >
      <header className="import-workflow-heading">
        <div><span className="eyebrow">DH manual import</span><h2>DoHome (DH)</h2></div>
        <span className="import-format-note">Daily pair · 2 Excel files</span>
      </header>

      <div className="hp-mh-source-note">
        <Building2 size={18} aria-hidden="true" />
        <p>
          เลือกไฟล์ Stock และ Sale ของ DoHome ระบบจะตรวจวันที่ โครงสร้าง ราคาใน DH
          Price Master และ Modern Trade ก่อนบันทึกข้อมูล
        </p>
      </div>

      <div className="hp-mh-file-grid">
        <label>
          <span>1 · Stock workbook (.xlsx)</span>
          <input
            aria-label="Stock workbook (.xlsx)"
            type="file"
            accept=".xlsx"
            disabled={busy !== null}
            onChange={(event) => {
              setFiles((current) => ({ ...current, stock: event.target.files?.[0] ?? null }))
              setPreview(null)
              setMessage(null)
            }}
          />
          <small>{files.stock ? files.stock.name + ' · ' + number.format(files.stock.size / 1024) + ' KB' : 'ไฟล์ Stock ของ DoHome'}</small>
        </label>
        <label>
          <span>2 · Sales workbook (.xlsx)</span>
          <input
            aria-label="Sales workbook (.xlsx)"
            type="file"
            accept=".xlsx"
            disabled={busy !== null}
            onChange={(event) => {
              setFiles((current) => ({ ...current, sales: event.target.files?.[0] ?? null }))
              setPreview(null)
              setMessage(null)
            }}
          />
          <small>{files.sales ? files.sales.name + ' · ' + number.format(files.sales.size / 1024) + ' KB' : 'ไฟล์ Sale ของ DoHome'}</small>
        </label>
        <button className="primary-action hp-mh-preview-action" type="button" disabled={!files.stock || !files.sales || busy !== null} onClick={() => void inspect()}>
          {busy === 'preview' ? 'กำลังตรวจสอบ…' : 'ตรวจสอบคู่ไฟล์ DH'}
        </button>
      </div>

      {progress && (
        <div className="import-transfer" role="status">
          <div><span>{progress.phase === 'uploading' ? 'กำลังส่งไฟล์เข้า Server' : 'กำลังอ่าน ตรวจราคา และตรวจข้อมูล'}</span><strong>{progress.phase === 'uploading' ? progress.percent + '%' : 'โปรดรอสักครู่'}</strong></div>
          <div className="import-transfer-track" data-indeterminate={progress.phase !== 'uploading' || undefined}><span style={{ width: progress.phase === 'uploading' ? progress.percent + '%' : '38%' }} /></div>
        </div>
      )}
      {message && <div className="import-message" role="status">{message}</div>}

      {preview && (
        <div className="preview-stage hp-mh-preview" data-blocked={!preview.canImport || undefined}>
          <header>
            <div><span className="stage-number">3</span><div><span className="eyebrow">ผลการตรวจสอบ</span><h3>DoHome · {formatDisplayDate(preview.dataDate)}</h3></div></div>
            <span className={'preview-state ' + (preview.canImport ? 'ready' : 'blocked')}>
              {preview.canImport ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {preview.canImport
                ? preview.operation === 'replace' ? 'พร้อมแทนที่ข้อมูลเดิม' : 'พร้อมนำเข้า'
                : 'ไม่สามารถนำเข้า'}
            </span>
          </header>
          <div className="hp-mh-summary-grid">
            <article>
              <strong>DoHome (DH)</strong>
              <dl>
                <div><dt>รายการ</dt><dd>{number.format(preview.summary.rowCount)}</dd></div>
                <div><dt>SKU</dt><dd>{number.format(preview.summary.skuCount)}</dd></div>
                <div><dt>Branch</dt><dd>{number.format(preview.summary.branchCount)}</dd></div>
                <div><dt>Amount Ex VAT</dt><dd>{number.format(preview.summary.amount)}</dd></div>
                <div><dt>Source Footer</dt><dd>{number.format(preview.summary.sourceAmount)}</dd></div>
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
            <small>Amount คำนวณจาก DH Price Master ตาม Sale Date; SKU ที่ไม่มีราคาจะไม่สามารถ Confirm ได้</small>
            <button className="primary-action" type="button" disabled={!preview.canImport || busy !== null} onClick={() => void confirm()}>
              {busy === 'confirm'
                ? 'กำลังบันทึก…'
                : preview.operation === 'replace' ? 'ยืนยันแทนที่ข้อมูล DoHome' : 'ยืนยันนำเข้า DoHome'}
            </button>
          </footer>
        </div>
      )}
    </section>
  )
}
