import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileWarning, RefreshCw, ShieldCheck } from 'lucide-react'
import { formatDisplayDate, formatDisplayDateTime } from '../../shared/dateFormat'
import {
  acknowledgeImportWarning,
  fetchImportBatch,
  previewBatchReplacement,
  replaceImportBatch,
  type ImportBatchDetail,
  type ReplacementPreview,
} from './importApi'
import './importCorrective.css'

const number = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })

interface ImportCorrectivePanelProps {
  batchId: number
  onCompleted?: () => void
}

export function ImportCorrectivePanel({ batchId, onCompleted }: ImportCorrectivePanelProps) {
  const [batch, setBatch] = useState<ImportBatchDetail | null>(null)
  const [note, setNote] = useState('')
  const [replacementFile, setReplacementFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ReplacementPreview | null>(null)
  const [busy, setBusy] = useState<'load' | 'acknowledge' | 'preview' | 'replace' | null>('load')
  const [message, setMessage] = useState<{ tone: 'success' | 'error', text: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchImportBatch(batchId, controller.signal)
      .then(setBatch)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'อ่านรายละเอียด Batch ไม่สำเร็จ' })
        }
      })
      .finally(() => { if (!controller.signal.aborted) setBusy(null) })
    return () => controller.abort()
  }, [batchId])

  const acknowledge = async () => {
    if (!batch || note.trim().length < 3) return
    setBusy('acknowledge')
    setMessage(null)
    try {
      setBatch(await acknowledgeImportWarning(batch.batchId, note.trim()))
      setMessage({ tone: 'success', text: `รับทราบคำเตือน Batch ${batch.batchId} แล้ว` })
      onCompleted?.()
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'บันทึกการรับทราบไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const inspectReplacement = async () => {
    if (!batch || !replacementFile) return
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    try {
      setPreview(await previewBatchReplacement(batch.batchId, replacementFile))
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'ตรวจสอบไฟล์ทดแทนไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const confirmReplacement = async () => {
    if (!batch || !replacementFile || !preview?.canReplace) return
    setBusy('replace')
    setMessage(null)
    try {
      setBatch(await replaceImportBatch(batch.batchId, replacementFile, preview.checksum))
      setPreview(null)
      setReplacementFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setMessage({ tone: 'success', text: `แทนที่ข้อมูล Batch ${batch.batchId} สำเร็จ` })
      onCompleted?.()
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'แทนที่ข้อมูลไม่สำเร็จ ข้อมูลเดิมยังคงอยู่' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="corrective-panel" aria-labelledby="corrective-heading">
      <header>
        <span className="corrective-icon"><FileWarning size={20} aria-hidden="true" /></span>
        <div><span className="eyebrow">Corrective action</span><h3 id="corrective-heading">แก้ไข Import Batch {batchId}</h3><p>ตรวจสอบสาเหตุ แล้วเลือกวิธีดำเนินการเพียงหนึ่งวิธี</p></div>
      </header>

      {busy === 'load' && <div className="corrective-loading" role="status"><RefreshCw size={16} className="is-spinning" />กำลังอ่านรายละเอียด…</div>}
      {message && <div className="corrective-message" data-tone={message.tone} role="status">{message.text}</div>}

      {batch && (
        <>
          <dl className="corrective-batch-summary">
            <div><dt>Batch</dt><dd>{batch.batchId}</dd></div>
            <div><dt>วันที่ข้อมูล</dt><dd>{formatDisplayDate(batch.dataDate)}</dd></div>
            <div><dt>ไฟล์</dt><dd title={batch.filename}>{batch.filename}</dd></div>
            <div><dt>รายการ</dt><dd>{number.format(batch.summary.rowCount)}</dd></div>
          </dl>

          <div className="corrective-warning-list">
            {batch.warnings.map((warning) => <p key={warning}><AlertTriangle size={16} />{warning}</p>)}
            {batch.warnings.length === 0 && <p data-resolved><CheckCircle2 size={16} />Batch นี้ไม่มีคำเตือนคงค้าง</p>}
          </div>

          {batch.resolution ? (
            <div className="corrective-resolution">
              <ShieldCheck size={18} />
              <div><strong>รับทราบแล้ว</strong><span>{batch.resolution.note}</span><small>{formatDisplayDateTime(batch.resolution.resolvedAt)} · {batch.resolution.resolvedBy}</small></div>
            </div>
          ) : batch.warnings.length > 0 && (
            <div className="corrective-options">
              <section>
                <div><span className="corrective-step">A</span><h4>ยืนยันว่ารายละเอียดถูกต้อง</h4></div>
                <p>ใช้เมื่อข้อมูลแต่ละแถวถูกต้อง แต่ยอด Total ในไฟล์ต้นทางไม่ตรง</p>
                <label htmlFor="corrective-note">หมายเหตุการตรวจสอบ</label>
                <textarea id="corrective-note" value={note} maxLength={1_000} placeholder="ระบุสิ่งที่ตรวจสอบและเหตุผลที่รับทราบ" onChange={(event) => setNote(event.target.value)} />
                <button className="secondary-action" type="button" disabled={busy !== null || note.trim().length < 3} onClick={() => void acknowledge()}>ยืนยันรับทราบ</button>
              </section>

              <section>
                <div><span className="corrective-step">B</span><h4>แทนที่ด้วยไฟล์ที่แก้ไขแล้ว</h4></div>
                <p>ระบบตรวจวันที่และเปรียบเทียบข้อมูลก่อนเปิดให้ยืนยัน ข้อมูลเดิมจะถูกเปลี่ยนใน Transaction เดียว</p>
                <label htmlFor="replacement-file">ไฟล์ Raw Data ที่แก้ไขแล้ว</label>
                <input ref={fileInputRef} id="replacement-file" type="file" accept=".xls" onChange={(event) => { setReplacementFile(event.target.files?.[0] ?? null); setPreview(null); setMessage(null) }} />
                <button className="secondary-action" type="button" disabled={busy !== null || !replacementFile} onClick={() => void inspectReplacement()}>{busy === 'preview' ? 'กำลังตรวจสอบ…' : 'Preview เปรียบเทียบ'}</button>
              </section>
            </div>
          )}

          {preview && (
            <div className="replacement-preview" data-blocked={!preview.canReplace || undefined}>
              <header><strong>ผลเปรียบเทียบก่อนแทนที่</strong><span>{preview.filename}</span></header>
              <table>
                <thead><tr><th>รายการ</th><th>ข้อมูลเดิม</th><th>ไฟล์ใหม่</th></tr></thead>
                <tbody>
                  <tr><td>จำนวนแถว</td><td>{number.format(preview.current.rowCount)}</td><td>{number.format(preview.replacement.rowCount)}</td></tr>
                  <tr><td>Amount</td><td>{number.format(preview.current.amount)}</td><td>{number.format(preview.replacement.amount)}</td></tr>
                  <tr><td>Qty</td><td>{number.format(preview.current.salesQty)}</td><td>{number.format(preview.replacement.salesQty)}</td></tr>
                  <tr><td>Stock On Hand</td><td>{number.format(preview.current.stockOnHand)}</td><td>{number.format(preview.replacement.stockOnHand)}</td></tr>
                  <tr><td>Source Total: Stock On Hand</td><td>{number.format(preview.current.reportedStockOnHand)}</td><td>{number.format(preview.replacement.reportedStockOnHand)}</td></tr>
                </tbody>
              </table>
              {preview.blockedReason && <p className="replacement-blocked"><AlertTriangle size={15} />{preview.blockedReason}</p>}
              {preview.warnings.length > 0 && <p className="replacement-blocked"><AlertTriangle size={15} />ไฟล์ใหม่ยังมีคำเตือน: {preview.warnings.join(' · ')}</p>}
              <footer><small>เมื่อยืนยัน ระบบจะเก็บค่าก่อนและหลังไว้ใน Audit Log</small><button className="primary-action" type="button" disabled={!preview.canReplace || busy !== null} onClick={() => void confirmReplacement()}>{busy === 'replace' ? 'กำลังแทนที่…' : `ยืนยันแทนที่ Batch ${batch.batchId}`}</button></footer>
            </div>
          )}
        </>
      )}
    </section>
  )
}
