import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  History,
  LayoutList,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import {
  confirmFileShareImport,
  confirmHpMhImport,
  confirmImport,
  fetchFileShareReady,
  fetchImportActivity,
  previewFileShareImport,
  previewHpMhImport,
  previewImport,
  type FileShareReadyFile,
  type HpMhImportPreview,
  type ImportActivity,
  type ImportPreview,
  type UploadProgress,
} from './importApi'
import { ImportCorrectivePanel } from './ImportCorrectivePanel'
import { formatDisplayDate, formatDisplayDateTime } from '../../shared/dateFormat'

const number = new Intl.NumberFormat('th-TH', { maximumFractionDigits: 2 })
type SourceMode = 'upload' | 'fileshare'
type ImportWorkspaceTab = 'overview' | 'TWD' | 'HP' | 'MH'

const workspaceTabs: Array<{
  code: ImportWorkspaceTab
  label: string
  name: string
}> = [
  { code: 'overview', label: 'ภาพรวม', name: 'ทุก Modern Trade' },
  { code: 'TWD', label: 'TWD', name: 'Thai Watsadu' },
  { code: 'HP', label: 'HP', name: 'HomePro' },
  { code: 'MH', label: 'MH', name: 'MegaHome' },
]
type WorkProgress = UploadProgress | {
  phase: 'fileshare' | 'importing'
  loaded: number
  total: number
  percent: number
}

function formatDuration(milliseconds: number) {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`
  return `${(milliseconds / 1000).toFixed(1)} วินาที`
}

function TimingBreakdown({ preview }: { preview: ImportPreview }) {
  const timings = preview.timings ?? {}
  const items = [
    ['อ่านจาก FileShare', timings.downloadMs],
    ['รับไฟล์บน Server', timings.serverReadMs],
    ['อ่านและตรวจ Excel', timings.parseMs],
    ['ตรวจข้อมูลซ้ำ', timings.duplicateCheckMs],
  ].filter((item): item is [string, number] => typeof item[1] === 'number')
  if (items.length === 0) return null
  return (
    <div className="import-timings" aria-label="เวลาประมวลผล">
      {items.map(([label, value]) => (
        <span key={label}>{label}<strong>{formatDuration(value)}</strong></span>
      ))}
    </div>
  )
}

function ImportProgress({ progress }: { progress: WorkProgress }) {
  const uploading = progress.phase === 'uploading'
  const label = progress.phase === 'fileshare'
    ? 'กำลังอ่านไฟล์จาก FileShare'
    : progress.phase === 'importing'
      ? 'กำลังตรวจสอบและนำเข้าข้อมูล'
      : uploading
        ? 'กำลังส่งไฟล์เข้า Server'
        : 'กำลังอ่าน Excel และตรวจข้อมูล'
  return (
    <div className="import-transfer" role="status">
      <div><span>{label}</span><strong>{uploading ? `${progress.percent}%` : 'โปรดรอสักครู่'}</strong></div>
      <div
        className="import-transfer-track"
        data-indeterminate={!uploading || undefined}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={uploading ? progress.percent : undefined}
      >
        <span style={{ width: uploading ? `${progress.percent}%` : '38%' }} />
      </div>
      {uploading && progress.total > 0 && (
        <small>{number.format(progress.loaded / 1024)} / {number.format(progress.total / 1024)} KB</small>
      )}
    </div>
  )
}

function statusLabel(status: string) {
  if (status === 'imported' || status === 'imported_with_warnings') return 'สำเร็จ'
  if (status === 'validated') return 'ตรวจสอบแล้ว'
  if (status === 'duplicate') return 'ข้อมูลซ้ำ'
  return 'ไม่สำเร็จ'
}

export function ImportPage({ correctiveBatchId = null }: { correctiveBatchId?: number | null }) {
  const [activeTab, setActiveTab] = useState<ImportWorkspaceTab>('TWD')
  const [sourceMode, setSourceMode] = useState<SourceMode>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [activities, setActivities] = useState<ImportActivity[]>([])
  const [readyFiles, setReadyFiles] = useState<FileShareReadyFile[]>([])
  const [readyState, setReadyState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [selectedSourceFileId, setSelectedSourceFileId] = useState<number | null>(null)
  const [busy, setBusy] = useState<'preview' | 'confirm' | null>(null)
  const [progress, setProgress] = useState<WorkProgress | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [hpMhFiles, setHpMhFiles] = useState<{
    inventory: File | null
    sales: File | null
  }>({ inventory: null, sales: null })
  const [hpMhPreview, setHpMhPreview] = useState<HpMhImportPreview | null>(null)
  const [hpMhMessage, setHpMhMessage] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const visibleActivities = activeTab === 'overview'
    ? activities
    : activities.filter((item) => item.mtCode.toUpperCase() === activeTab)
  const selectedTab = workspaceTabs.find((tab) => tab.code === activeTab) ?? workspaceTabs[0]

  const loadActivity = () => fetchImportActivity().then(setActivities).catch(() => undefined)
  useEffect(() => { void loadActivity() }, [])

  const loadReadyFiles = useCallback(async () => {
    setReadyState('loading')
    try {
      setReadyFiles(await fetchFileShareReady())
      setReadyState('ready')
    } catch {
      setReadyState('error')
    }
  }, [])
  const moveWorkspaceFocus = (nextTab: ImportWorkspaceTab) => {
    if (busy !== null) return
    setActiveTab(nextTab)
    window.requestAnimationFrame(() => {
      document.getElementById('import-tab-' + nextTab)?.focus()
    })
  }
  const changeSourceMode = (nextMode: SourceMode) => {
    if (busy !== null || nextMode === sourceMode) return
    setSourceMode(nextMode)
    setFile(null)
    setSelectedSourceFileId(null)
    setPreview(null)
    setProgress(null)
    setMessage(null)
    if (inputRef.current) inputRef.current.value = ''
    if (nextMode === 'fileshare') void loadReadyFiles()
  }

  const inspect = async (selectedFile: File) => {
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    try {
      setPreview(await previewImport(selectedFile, setProgress))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบไฟล์ไม่สำเร็จ')
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
      void loadActivity()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  const inspectFileShare = async (sourceFileId: number) => {
    setBusy('preview')
    setMessage(null)
    setPreview(null)
    setSelectedSourceFileId(sourceFileId)
    setProgress({ phase: 'fileshare', loaded: 0, total: 0, percent: 0 })
    try {
      setPreview(await previewFileShareImport(sourceFileId))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ตรวจสอบไฟล์จาก FileShare ไม่สำเร็จ')
      setSelectedSourceFileId(null)
      void loadReadyFiles()
      void loadActivity()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  const confirm = async () => {
    if (!preview?.canImport) return
    if (sourceMode === 'upload' && !file) return
    if (sourceMode === 'fileshare' && selectedSourceFileId === null) return
    setBusy('confirm')
    setMessage(null)
    try {
      let result
      if (sourceMode === 'fileshare' && selectedSourceFileId !== null) {
        setProgress({ phase: 'importing', loaded: 0, total: 0, percent: 0 })
        result = await confirmFileShareImport(selectedSourceFileId, preview.checksum)
      } else if (file) {
        result = await confirmImport(file, preview.checksum, setProgress)
      } else {
        return
      }
      setMessage(`${result.message} · ${result.notification.message}`)
      setFile(null)
      setSelectedSourceFileId(null)
      setPreview(null)
      if (inputRef.current) inputRef.current.value = ''
      if (sourceMode === 'fileshare') void loadReadyFiles()
      void loadActivity()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'นำเข้าข้อมูลไม่สำเร็จ')
      void loadActivity()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  const inspectHpMh = async () => {
    if (!hpMhFiles.inventory || !hpMhFiles.sales) return
    setBusy('preview')
    setHpMhMessage(null)
    setHpMhPreview(null)
    try {
      setHpMhPreview(
        await previewHpMhImport(
          hpMhFiles.inventory,
          hpMhFiles.sales,
          setProgress,
        ),
      )
    } catch (error) {
      setHpMhMessage(
        error instanceof Error ? error.message : 'ตรวจสอบคู่ไฟล์ HP/MH ไม่สำเร็จ',
      )
      void loadActivity()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  const confirmHpMh = async () => {
    if (
      !hpMhPreview?.canImport
      || !hpMhFiles.inventory
      || !hpMhFiles.sales
    ) return
    setBusy('confirm')
    setHpMhMessage(null)
    try {
      const result = await confirmHpMhImport(
        hpMhFiles.inventory,
        hpMhFiles.sales,
        hpMhPreview.businessFingerprint,
        setProgress,
      )
      setHpMhMessage(`${result.message} · ${result.notification.message}`)
      setHpMhFiles({ inventory: null, sales: null })
      setHpMhPreview(null)
      void loadActivity()
    } catch (error) {
      setHpMhMessage(
        error instanceof Error ? error.message : 'นำเข้าข้อมูล HP/MH ไม่สำเร็จ',
      )
      void loadActivity()
    } finally {
      setProgress(null)
      setBusy(null)
    }
  }

  return (
    <div className="import-page page-content">
      <header className="import-operations-header">
        <div>
          <span className="eyebrow">Data operations</span>
          <h1>นำเข้าข้อมูล</h1>
          <p>ตรวจสอบ Modern Trade และความถูกต้องของไฟล์ก่อนบันทึกข้อมูลจริง</p>
        </div>
        <div className="import-safety-context" aria-label="มาตรฐานการนำเข้าข้อมูล">
          <ShieldCheck size={17} aria-hidden="true" />
          <span><small>Data protection</small><strong>Strict validation</strong></span>
        </div>
      </header>

      <nav className="import-workspace-tabs" role="tablist" aria-label="Modern Trade">
        {workspaceTabs.map((tab) => {
          const activityCount = tab.code === 'overview'
            ? activities.length
            : activities.filter((item) => item.mtCode.toUpperCase() === tab.code).length
          const selected = activeTab === tab.code
          return (
            <button
              key={tab.code}
              id={'import-tab-' + tab.code}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={'import-panel-' + tab.code}
              tabIndex={selected ? 0 : -1}
              disabled={busy !== null}
              onClick={() => setActiveTab(tab.code)}
              onKeyDown={(event) => {
                const currentIndex = workspaceTabs.findIndex((item) => item.code === tab.code)
                if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                  event.preventDefault()
                  const step = event.key === 'ArrowRight' ? 1 : -1
                  const nextIndex = (
                    currentIndex + step + workspaceTabs.length
                  ) % workspaceTabs.length
                  moveWorkspaceFocus(workspaceTabs[nextIndex].code)
                }
                if (event.key === 'Home' || event.key === 'End') {
                  event.preventDefault()
                  moveWorkspaceFocus(
                    event.key === 'Home'
                      ? workspaceTabs[0].code
                      : workspaceTabs[workspaceTabs.length - 1].code,
                  )
                }
              }}
            >
              {tab.code === 'overview'
                ? <LayoutList size={16} aria-hidden="true" />
                : <Building2 size={16} aria-hidden="true" />}
              <span><strong>{tab.label}</strong><small>{tab.name}</small></span>
              <b>{activityCount}</b>
            </button>
          )
        })}
      </nav>

      {correctiveBatchId !== null && <ImportCorrectivePanel batchId={correctiveBatchId} onCompleted={() => void loadActivity()} />}
      {activeTab === 'TWD' && <section
        id="import-panel-TWD"
        className="import-workflow"
        role="tabpanel"
        aria-labelledby="import-tab-TWD"
      >
        <header className="import-workflow-heading">
          <div>
            <span className="eyebrow">TWD manual import</span>
            <h2>Thai Watsadu (TWD)</h2>
          </div>
          <span className="import-format-note">Excel · .xls / .xlsx</span>
        </header>

        <div className="import-source-bar">
          <div className="import-source-switch" role="group" aria-label="แหล่งข้อมูล">
            <button type="button" aria-pressed={sourceMode === 'upload'} disabled={busy !== null} onClick={() => changeSourceMode('upload')}>
              <FileSpreadsheet size={16} aria-hidden="true" />จากเครื่อง
            </button>
            <button type="button" aria-pressed={sourceMode === 'fileshare'} disabled={busy !== null} onClick={() => changeSourceMode('fileshare')}>
              <Database size={16} aria-hidden="true" />จาก FileShare
            </button>
          </div>
          <ol className="import-pipeline" aria-label="ขั้นตอนนำเข้าข้อมูล">
            <li data-active={!preview || undefined}><span>1</span>{sourceMode === 'upload' ? 'ส่งไฟล์' : 'อ่านไฟล์'}</li>
            <li data-active={preview ? true : undefined}><span>2</span>ตรวจสอบ</li>
            <li><span>3</span>ยืนยัน</li>
          </ol>
        </div>

        {sourceMode === 'upload' ? (
          <div className="upload-stage">
            <span className="stage-number">1</span>
            <FileSpreadsheet size={28} aria-hidden="true" />
            <div className="file-control">
              <label htmlFor="raw-data-file">เลือกไฟล์ Raw Data จากเครื่อง</label>
              <input
                ref={inputRef}
                id="raw-data-file"
                type="file"
                accept=".xls,.xlsx"
                disabled={busy !== null}
                onChange={(event) => {
                  const selectedFile = event.target.files?.[0] ?? null
                  setFile(selectedFile)
                  setPreview(null)
                  setMessage(null)
                  if (selectedFile) void inspect(selectedFile)
                }}
              />
              <small>{file ? `${file.name} · ${number.format(file.size / 1024)} KB` : 'รองรับไฟล์ TWD .xls / .xlsx ขนาดไม่เกิน 25 MB'}</small>
            </div>
          </div>
        ) : (
          <section className="fileshare-ready-stage" aria-labelledby="fileshare-ready-heading">
            <header>
              <div>
                <span className="stage-number">1</span>
                <div><span className="eyebrow">File registry</span><h3 id="fileshare-ready-heading">ไฟล์พร้อมนำเข้า</h3></div>
              </div>
              <button type="button" className="secondary-action" disabled={readyState === 'loading' || busy !== null} onClick={() => void loadReadyFiles()}>
                <RefreshCw size={14} className={readyState === 'loading' ? 'is-spinning' : undefined} aria-hidden="true" />Refresh
              </button>
            </header>
            {readyState === 'loading' && <div className="fileshare-ready-state" role="status"><LoaderCircle className="is-spinning" size={18} />กำลังอ่านทะเบียนไฟล์…</div>}
            {readyState === 'error' && <div className="fileshare-ready-state error" role="alert"><AlertTriangle size={18} />โหลดรายการไม่สำเร็จ <button type="button" onClick={() => void loadReadyFiles()}>ลองใหม่</button></div>}
            {readyState === 'ready' && readyFiles.length === 0 && <div className="fileshare-ready-state">ยังไม่มีไฟล์พร้อมนำเข้า กรุณาใช้ Initial Scan หรือ Run ทันทีที่หน้าการตั้งค่า</div>}
            {readyState === 'ready' && readyFiles.length > 0 && (
              <div className="fileshare-ready-table-wrap">
                <table className="fileshare-ready-table">
                  <thead><tr><th>วันที่ข้อมูล</th><th>ไฟล์</th><th>ขนาด</th><th>พบล่าสุด</th><th><span className="sr-only">การทำงาน</span></th></tr></thead>
                  <tbody>
                    {readyFiles.map((readyFile) => (
                      <tr key={readyFile.id} data-selected={selectedSourceFileId === readyFile.id || undefined}>
                        <td>{readyFile.dataDate ? formatDisplayDate(readyFile.dataDate) : '—'}</td>
                        <td><strong>{readyFile.filename}</strong></td>
                        <td>{number.format(readyFile.sizeBytes / 1024)} KB</td>
                        <td>{formatDisplayDateTime(readyFile.discoveredAt)}</td>
                        <td><button type="button" disabled={busy !== null} onClick={() => void inspectFileShare(readyFile.id)}>ตรวจสอบ</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {progress && <ImportProgress progress={progress} />}
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
            <TimingBreakdown preview={preview} />
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
      </section>}

      {activeTab === 'overview' && (
        <section
          id="import-panel-overview"
          className="import-overview-panel"
          role="tabpanel"
          aria-labelledby="import-tab-overview"
        >
          <header><span className="eyebrow">Import overview</span><h2>สถานะล่าสุดแยกตาม Modern Trade</h2></header>
          <div className="import-mt-ledger">
            {workspaceTabs.slice(1).map((tab) => {
              const mtActivities = activities.filter(
                (item) => item.mtCode.toUpperCase() === tab.code,
              )
              const latest = mtActivities[0]
              return (
                <article key={tab.code}>
                  <span className="mt-ledger-code">{tab.code}</span>
                  <div><strong>{tab.name}</strong><small>{latest ? latest.message : 'ยังไม่มีประวัติการนำเข้า'}</small></div>
                  <div><b>{mtActivities.length}</b><small>รายการล่าสุด</small></div>
                  <time>{latest ? formatDisplayDateTime(latest.occurredAt) : '—'}</time>
                </article>
              )
            })}
          </div>
        </section>
      )}

      {(activeTab === 'HP' || activeTab === 'MH') && (
        <section
          id={'import-panel-' + activeTab}
          className="import-workflow import-hp-mh-workflow"
          role="tabpanel"
          aria-labelledby={'import-tab-' + activeTab}
        >
          <header className="import-workflow-heading">
            <div>
              <span className="eyebrow">HP/MH manual import</span>
              <h2>{selectedTab.name} ({activeTab})</h2>
            </div>
            <span className="import-format-note">Shared pair · 2 ZIP files</span>
          </header>

          <div className="hp-mh-source-note">
            <Building2 size={18} aria-hidden="true" />
            <p>
              HP และ MH ใช้คู่ไฟล์เดียวกัน ระบบจะตรวจ Inventory/Sales และนำเข้าทั้งสอง MT
              พร้อมกัน โดยแยกข้อมูลของแต่ละ MT ตาม Logic เดิม
            </p>
          </div>

          <div className="hp-mh-file-grid">
            <label>
              <span>1 · Inventory ZIP</span>
              <input
                type="file"
                accept=".zip"
                disabled={busy !== null}
                onChange={(event) => {
                  const selectedFile = event.target.files?.[0] ?? null
                  setHpMhFiles((current) => ({ ...current, inventory: selectedFile }))
                  setHpMhPreview(null)
                  setHpMhMessage(null)
                }}
              />
              <small>
                {hpMhFiles.inventory
                  ? `${hpMhFiles.inventory.name} · ${number.format(hpMhFiles.inventory.size / 1024)} KB`
                  : 'ZIP ที่ภายในมี InventoryData.csv'}
              </small>
            </label>
            <label>
              <span>2 · Sales ZIP</span>
              <input
                type="file"
                accept=".zip"
                disabled={busy !== null}
                onChange={(event) => {
                  const selectedFile = event.target.files?.[0] ?? null
                  setHpMhFiles((current) => ({ ...current, sales: selectedFile }))
                  setHpMhPreview(null)
                  setHpMhMessage(null)
                }}
              />
              <small>
                {hpMhFiles.sales
                  ? `${hpMhFiles.sales.name} · ${number.format(hpMhFiles.sales.size / 1024)} KB`
                  : 'ZIP ที่ภายในมี SalesData.csv'}
              </small>
            </label>
            <button
              className="primary-action hp-mh-preview-action"
              type="button"
              disabled={!hpMhFiles.inventory || !hpMhFiles.sales || busy !== null}
              onClick={() => void inspectHpMh()}
            >
              {busy === 'preview' ? 'กำลังตรวจสอบ…' : 'ตรวจสอบคู่ไฟล์'}
            </button>
          </div>

          {progress && <ImportProgress progress={progress} />}
          {hpMhMessage && <div className="import-message" role="status">{hpMhMessage}</div>}

          {hpMhPreview && (
            <div className="preview-stage hp-mh-preview" data-blocked={!hpMhPreview.canImport || undefined}>
              <header>
                <div>
                  <span className="stage-number">3</span>
                  <div>
                    <span className="eyebrow">ผลการตรวจสอบ</span>
                    <h3>HP + MH · {formatDisplayDate(hpMhPreview.dataDate)}</h3>
                  </div>
                </div>
                <span className={`preview-state ${hpMhPreview.canImport ? 'ready' : 'blocked'}`}>
                  {hpMhPreview.canImport ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  {hpMhPreview.canImport ? 'พร้อมนำเข้า' : 'ไม่สามารถนำเข้า'}
                </span>
              </header>
              <div className="hp-mh-summary-grid">
                {(['HP', 'MH'] as const).map((code) => {
                  const summary = hpMhPreview.summaries[code]
                  return (
                    <article key={code}>
                      <strong>{code === 'HP' ? 'HomePro (HP)' : 'MegaHome (MH)'}</strong>
                      <dl>
                        <div><dt>รายการ</dt><dd>{number.format(summary.rowCount)}</dd></div>
                        <div><dt>SKU</dt><dd>{number.format(summary.skuCount)}</dd></div>
                        <div><dt>Branch</dt><dd>{number.format(summary.branchCount)}</dd></div>
                        <div><dt>Amount</dt><dd>{number.format(summary.amount)}</dd></div>
                        <div><dt>Sales Qty</dt><dd>{number.format(summary.salesQty)}</dd></div>
                        <div><dt>Stock</dt><dd>{number.format(summary.stockOnHand)}</dd></div>
                      </dl>
                    </article>
                  )
                })}
              </div>
              {hpMhPreview.warnings.length > 0 && (
                <div className="preview-warning">
                  <AlertTriangle size={16} />{hpMhPreview.warnings.join(' · ')}
                </div>
              )}
              {hpMhPreview.duplicateReason && (
                <div className="preview-warning blocked">
                  <AlertTriangle size={16} />{hpMhPreview.duplicateReason}
                </div>
              )}
              <footer>
                <small>ยืนยันครั้งเดียว ระบบจะบันทึก HP และ MH พร้อมกันจากคู่ไฟล์ที่ตรวจแล้ว</small>
                <button
                  className="primary-action"
                  type="button"
                  disabled={!hpMhPreview.canImport || busy !== null}
                  onClick={() => void confirmHpMh()}
                >
                  {busy === 'confirm' ? 'กำลังนำเข้า…' : 'ยืนยันนำเข้า HP และ MH'}
                </button>
              </footer>
            </div>
          )}
        </section>
      )}

      <section className="activity-panel" aria-labelledby="activity-heading">
        <header><div><History size={18} aria-hidden="true" /><div><span className="eyebrow">Activity ledger</span><h3 id="activity-heading">ประวัติการทำงาน · {selectedTab.label}</h3></div></div><button type="button" onClick={() => void loadActivity()}>Refresh</button></header>
        <div className="activity-list">
          {visibleActivities.length === 0 && <p className="empty-activity">ยังไม่มีประวัติการนำเข้าข้อมูลของ {selectedTab.label}</p>}
          {visibleActivities.map((item) => (
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
