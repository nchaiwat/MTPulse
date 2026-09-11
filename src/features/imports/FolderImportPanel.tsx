import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, FolderOpen, LoaderCircle } from 'lucide-react'
import {
  MANUAL_UPLOAD_LIMITS,
  confirmFolderImportBatch,
  createFolderImportBatch,
  fetchFolderImportBatch,
  finalizeFolderImportBatch,
  uploadFolderImportFile,
  type ManualUploadBatchContract,
} from './importApi'

const terminalStatuses = new Set(['completed', 'completed_with_issues', 'failed'])
const maxStatusPolls = 300

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

function directFiles(fileList: FileList | null) {
  return Array.from(fileList ?? []).filter((file) => {
    const relativePath = file.webkitRelativePath
    return !relativePath || relativePath.split('/').length === 2
  })
}

export function FolderImportPanel({
  expectedSourceGroup,
  onCompleted,
}: {
  expectedSourceGroup: 'TWD' | 'HP_MH' | 'HH'
  onCompleted: () => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [batch, setBatch] = useState<ManualUploadBatchContract | null>(null)
  const [busy, setBusy] = useState<'upload' | 'confirm' | null>(null)
  const [uploadedCount, setUploadedCount] = useState(0)
  const [message, setMessage] = useState<string | null>(null)
  const exceptionFiles = useMemo(
    () => batch?.files.filter((file) => !['uploaded', 'imported'].includes(file.status)) ?? [],
    [batch],
  )

  const selectFolder = (fileList: FileList | null) => {
    const selected = directFiles(fileList)
    setBatch(null)
    setMessage(null)
    setUploadedCount(0)
    if (selected.length > MANUAL_UPLOAD_LIMITS.maxFolderFiles) {
      setFiles([])
      setMessage(
        `Folder มี ${selected.length} ไฟล์ เกินกำหนดสูงสุด ${MANUAL_UPLOAD_LIMITS.maxFolderFiles} ไฟล์`,
      )
      return
    }
    setFiles(selected)
    if (selected.length === 0) {
      setMessage('ไม่พบไฟล์ระดับแรกใน Folder ที่เลือก')
    }
  }

  const inspectFolder = async () => {
    if (files.length === 0) return
    setBusy('upload')
    setMessage(null)
    setBatch(null)
    setUploadedCount(0)
    try {
      const created = await createFolderImportBatch(files.length)
      let cursor = 0
      let completed = 0
      const uploadWithRetry = async (file: File, index: number) => {
        let lastError: unknown
        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            await uploadFolderImportFile(
              created.id,
              file,
              `${index + 1}-${file.size}-${file.lastModified}`,
            )
            return
          } catch (error) {
            lastError = error
            if (attempt < 2) await wait(500 * (attempt + 1))
          }
        }
        throw lastError
      }
      const uploadWorker = async () => {
        while (cursor < files.length) {
          const index = cursor
          cursor += 1
          const file = files[index]
          await uploadWithRetry(file, index)
          completed += 1
          setUploadedCount(completed)
        }
      }
      await Promise.all(
        Array.from(
          { length: Math.min(MANUAL_UPLOAD_LIMITS.uploadConcurrency, files.length) },
          () => uploadWorker(),
        ),
      )
      const validated = await finalizeFolderImportBatch(created.id, expectedSourceGroup)
      setBatch(validated)
      if (validated.status === 'failed') {
        setMessage(validated.errorMessage ?? 'ตรวจสอบ Folder ไม่ผ่าน')
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบ Folder ไม่สำเร็จ')
    } finally {
      setBusy(null)
    }
  }

  const confirmFolder = async () => {
    if (!batch || batch.status !== 'awaiting_confirmation') return
    setBusy('confirm')
    setMessage(null)
    try {
      let current = await confirmFolderImportBatch(batch.id)
      setBatch(current)
      let pollCount = 0
      while (!terminalStatuses.has(current.status) && pollCount < maxStatusPolls) {
        await wait(2_000)
        current = await fetchFolderImportBatch(batch.id)
        setBatch(current)
        pollCount += 1
      }
      if (!terminalStatuses.has(current.status)) {
        setMessage('Batch ยังประมวลผลอยู่เบื้องหลัง สามารถกลับมาตรวจสอบในประวัติได้')
        return
      }
      setMessage(current.summaryMessage ?? current.errorMessage ?? 'ประมวลผล Batch เสร็จแล้ว')
      onCompleted()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'นำเข้า Folder ไม่สำเร็จ')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="folder-import-panel" aria-labelledby={`folder-import-${expectedSourceGroup}`}>
      <header>
        <div>
          <span className="eyebrow">Admin folder import</span>
          <h3 id={`folder-import-${expectedSourceGroup}`}>นำเข้าข้อมูลทั้ง Folder</h3>
          <p>อ่านเฉพาะไฟล์ระดับแรก · สูงสุด {MANUAL_UPLOAD_LIMITS.maxFolderFiles} ไฟล์ · Upload พร้อมกัน {MANUAL_UPLOAD_LIMITS.uploadConcurrency} ไฟล์</p>
        </div>
        <span className="folder-admin-badge">Admin only</span>
      </header>

      <div className="folder-import-controls">
        <input
          ref={(element) => {
            element?.setAttribute('webkitdirectory', '')
            element?.setAttribute('directory', '')
          }}
          type="file"
          multiple
          disabled={busy !== null}
          aria-label={`เลือก Folder สำหรับ ${expectedSourceGroup}`}
          onChange={(event) => selectFolder(event.target.files)}
        />
        <div>
          <strong>{files.length > 0 ? `${files.length} ไฟล์พร้อมตรวจสอบ` : 'ยังไม่ได้เลือก Folder'}</strong>
          <small>
            {expectedSourceGroup === 'TWD'
              ? 'ระบบต้องตรวจพบไฟล์ TWD .xls/.xlsx เท่านั้น'
              : expectedSourceGroup === 'HH'
                ? 'ระบบจะจับคู่ StockReport.xlsx และ SaleReport.xlsx ของ HH ตามวันที่ข้อมูล'
              : 'ระบบจะจับคู่ Inventory ZIP และ Sales ZIP ของ HP/MH'}
          </small>
        </div>
        <button
          className="primary-action"
          type="button"
          disabled={files.length === 0 || busy !== null}
          onClick={() => void inspectFolder()}
        >
          {busy === 'upload' ? <LoaderCircle className="is-spinning" size={15} /> : <FolderOpen size={15} />}
          {busy === 'upload' ? `กำลังส่ง ${uploadedCount}/${files.length}` : 'ตรวจสอบ Folder'}
        </button>
      </div>

      {batch && (
        <div className="folder-batch-result" data-status={batch.status}>
          <div className="folder-batch-summary">
            {batch.status === 'failed'
              ? <AlertTriangle size={18} aria-hidden="true" />
              : <CheckCircle2 size={18} aria-hidden="true" />}
            <div>
              <strong>Batch {batch.id} · {batch.detectedSourceGroup ?? 'ยังระบุ MT ไม่ได้'}</strong>
              <small>{batch.summaryMessage ?? batch.errorMessage ?? 'กำลังประมวลผลข้อมูล'}</small>
            </div>
            <dl>
              <div><dt>ทั้งหมด</dt><dd>{batch.counts.total}</dd></div>
              <div><dt>พร้อมนำเข้า</dt><dd>{batch.counts.eligible}</dd></div>
              <div><dt>สำเร็จ</dt><dd>{batch.counts.imported}</dd></div>
              <div><dt>ซ้ำ</dt><dd>{batch.counts.duplicate}</dd></div>
              <div><dt>ผิดพลาด</dt><dd>{batch.counts.failed + batch.counts.needsReview}</dd></div>
            </dl>
          </div>

          {exceptionFiles.length > 0 && (
            <div className="folder-exception-list">
              <strong>ไฟล์ที่ต้องตรวจสอบ</strong>
              {exceptionFiles.map((file) => (
                <div key={file.id}>
                  <span>{file.filename}</span>
                  <b>{file.status === 'duplicate' ? 'ข้อมูลซ้ำ' : 'ไม่ผ่าน'}</b>
                  <small>{file.reason ?? 'ระบบไม่สามารถระบุรูปแบบข้อมูลได้'}</small>
                </div>
              ))}
            </div>
          )}

          {batch.status === 'awaiting_confirmation' && (
            <footer>
              <small>ระบบจะข้ามไฟล์ผิดพลาดและประมวลผลเฉพาะไฟล์ที่ผ่านการตรวจสอบ</small>
              <button className="primary-action" type="button" disabled={busy !== null} onClick={() => void confirmFolder()}>
                ยืนยันนำเข้า Folder
              </button>
            </footer>
          )}
        </div>
      )}

      {message && <div className="import-message" role="status">{message}</div>}
    </section>
  )
}
