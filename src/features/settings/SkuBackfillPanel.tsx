import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowUpRight,
  CalendarRange,
  CheckCircle2,
  DatabaseZap,
  PauseCircle,
  Play,
  RefreshCw,
} from 'lucide-react'
import type { ImportRun } from './fileShareSettingsApi'
import {
  fetchImportRun,
  fetchLatestBackfillRun,
  fetchSkuBackfillOptions,
  previewSkuBackfill,
  refreshSourceRegistry,
  resumeSkuBackfill,
  startSkuBackfill,
  stopSkuBackfill,
  type SkuBackfillOptions,
  type SkuBackfillPreview,
} from './skuBackfillApi'

const activeStatuses = new Set(['queued', 'running', 'stop_requested'])
const interestStatusLabels = {
  active: 'สนใจแล้ว',
  pending: 'รอตัดสินใจ',
  ignored: 'เคย Ignore',
} as const

function formatDate(value: string | null) {
  if (!value) return 'ยังไม่มีข้อมูล'
  return new Intl.DateTimeFormat('th-TH', { dateStyle: 'medium' }).format(
    new Date(`${value}T00:00:00+07:00`),
  )
}

function formatDateTime(value: string | null) {
  if (!value) return 'ยังไม่เคยอัปเดต'
  return new Intl.DateTimeFormat('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function runStatus(run: ImportRun) {
  if (run.status === 'queued') return 'รอ Worker เริ่มงาน'
  if (run.status === 'running') return 'กำลังดึงข้อมูลย้อนหลัง'
  if (run.status === 'stop_requested') return 'กำลังจบไฟล์ปัจจุบันก่อนหยุด'
  if (run.status === 'stopped') return 'หยุดแล้ว — สามารถทำต่อได้'
  if (run.status === 'success') return 'เสร็จสมบูรณ์'
  if (run.status === 'success_with_warnings') return 'เสร็จพร้อมรายการที่ต้องตรวจ'
  return 'ไม่สำเร็จ'
}

export function SkuBackfillPanel() {
  const [expanded, setExpanded] = useState(false)
  const [options, setOptions] = useState<SkuBackfillOptions | null>(null)
  const [sourceSku, setSourceSku] = useState('')
  const [startMode, setStartMode] = useState<'earliest' | 'custom'>('earliest')
  const [customStart, setCustomStart] = useState('')
  const [preview, setPreview] = useState<SkuBackfillPreview | null>(null)
  const [run, setRun] = useState<ImportRun | null>(null)
  const [busy, setBusy] = useState<'load' | 'preview' | 'start' | 'registry' | 'stop' | 'resume' | null>(null)
  const [message, setMessage] = useState<{ tone: 'error' | 'success', text: string } | null>(null)

  const loadOptions = useCallback(async (signal?: AbortSignal) => {
    const [loaded, latestRun] = await Promise.all([
      fetchSkuBackfillOptions(signal),
      fetchLatestBackfillRun(signal),
    ])
    setOptions(loaded)
    setRun(latestRun)
    if (loaded.registry.earliestDate) {
      setCustomStart((current) => current || loaded.registry.earliestDate || '')
    }
  }, [])

  const openPanel = async () => {
    setExpanded(true)
    setBusy('load')
    setMessage(null)
    try {
      await loadOptions()
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'โหลดข้อมูล Backfill ไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const activeRunId = run?.runId
  const activeRunStatus = run?.status
  useEffect(() => {
    if (!activeRunId || !activeRunStatus || !activeStatuses.has(activeRunStatus)) return
    const timer = window.setInterval(() => {
      fetchImportRun(activeRunId)
        .then((updated) => {
          setRun(updated)
          if (!activeStatuses.has(updated.status)) {
            void loadOptions()
          }
        })
        .catch(() => undefined)
    }, 2_000)
    return () => window.clearInterval(timer)
  }, [activeRunId, activeRunStatus, loadOptions])

  const selectedStart = startMode === 'custom' ? customStart || null : null
  const selectedUnmapped = options?.unmappedSkus?.find((item) => item.sourceSku === sourceSku)
  const needsMapping = Boolean(selectedUnmapped)

  const goToMapping = () => {
    document.getElementById('twd-item-mapping')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => document.getElementById('mapping-export-button')?.focus({ preventScroll: true }), 250)
  }

  const createPreview = async () => {
    if (!sourceSku) return
    setBusy('preview')
    setMessage(null)
    try {
      setPreview(await previewSkuBackfill(sourceSku, selectedStart))
    } catch (error) {
      setPreview(null)
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Preview ไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const start = async () => {
    setBusy('start')
    setMessage(null)
    try {
      const created = await startSkuBackfill(sourceSku, selectedStart)
      setRun(created)
      setPreview(null)
      setMessage({ tone: 'success', text: 'ส่งงานเข้าคิวแล้ว ระบบจะเติมเฉพาะวันที่ยังไม่มี SKU นี้' })
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'เริ่ม Backfill ไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const refreshRegistry = async () => {
    setBusy('registry')
    setMessage(null)
    try {
      const created = await refreshSourceRegistry()
      setRun(created)
      setPreview(null)
      setMessage({ tone: 'success', text: 'ส่งงานอัปเดต File Registry เข้าคิวแล้ว' })
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'อัปเดต File Registry ไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const stop = async () => {
    if (!run) return
    setBusy('stop')
    try {
      setRun(await stopSkuBackfill(run.runId))
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'ขอหยุดไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const resume = async () => {
    if (!run) return
    setBusy('resume')
    try {
      setRun(await resumeSkuBackfill(run.runId))
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'ทำต่อไม่สำเร็จ' })
    } finally {
      setBusy(null)
    }
  }

  const isRunning = Boolean(run && activeStatuses.has(run.status))
  const progress = run?.progress

  return (
    <section className="sku-backfill-settings" aria-labelledby="sku-backfill-heading">
      <header>
        <span className="setting-icon"><DatabaseZap size={19} aria-hidden="true" /></span>
        <div>
          <span className="eyebrow">Historical data</span>
          <h3 id="sku-backfill-heading">ดึงข้อมูลย้อนหลังเฉพาะ SKU</h3>
          <p>เติมเฉพาะวันที่ยังไม่มีข้อมูล โดยไม่แก้ทับ Fact เดิมและไม่ Import ทั้งไฟล์ซ้ำ</p>
        </div>
        {expanded
          ? <button className="secondary-action" type="button" disabled={busy !== null || isRunning} onClick={() => void refreshRegistry()}>
              <RefreshCw size={15} aria-hidden="true" className={busy === 'registry' ? 'is-spinning' : undefined} />
              {busy === 'registry' ? 'กำลังส่งงาน…' : 'อัปเดตรายการไฟล์'}
            </button>
          : <button className="secondary-action" type="button" onClick={() => void openPanel()}>
              <Play size={15} aria-hidden="true" />เปิดเครื่องมือ Backfill
            </button>}
      </header>

      {expanded && (
        <>
      <div className="sku-backfill-registry">
        <CalendarRange size={16} aria-hidden="true" />
        <span><small>ช่วงข้อมูลใน File Registry</small><strong>{formatDate(options?.registry.earliestDate ?? null)} – {formatDate(options?.registry.latestDate ?? null)}</strong></span>
        <time>อัปเดตล่าสุด {formatDateTime(options?.registry.refreshedAt ?? null)}</time>
      </div>

      <div className="sku-backfill-form">
        <label>
          SKU ที่สนใจ
          <select aria-label="SKU สำหรับ Backfill" value={sourceSku} disabled={busy === 'load' || isRunning} onChange={(event) => { setSourceSku(event.target.value); setPreview(null) }}>
            <option value="">เลือก SKU</option>
            {Boolean(options?.mappings.length) && <optgroup label="พร้อม Backfill — Mapping แล้ว">
              {options?.mappings.map((item) => (
                <option key={item.sourceSku} value={item.sourceSku}>
                  {item.sourceSku} — {item.sourceDescription ?? item.waItemDescription ?? item.waItemCode}
                </option>
              ))}
            </optgroup>}
            {Boolean(options?.unmappedSkus?.length) && <optgroup label="ต้อง Mapping ก่อน">
              {options?.unmappedSkus?.map((item) => (
                <option key={item.sourceSku} value={item.sourceSku}>
                  {item.sourceSku} — {item.sourceDescription ?? 'ไม่มีรายละเอียด'} ({interestStatusLabels[item.interestStatus]})
                </option>
              ))}
            </optgroup>}
          </select>
        </label>
        <fieldset disabled={needsMapping || isRunning}>
          <legend>เริ่มจาก</legend>
          <label><input type="radio" name="backfill-start" checked={startMode === 'earliest'} onChange={() => { setStartMode('earliest'); setPreview(null) }} />วันแรกใน File Registry</label>
          <label><input type="radio" name="backfill-start" checked={startMode === 'custom'} onChange={() => { setStartMode('custom'); setPreview(null) }} />กำหนดวันที่</label>
        </fieldset>
        <label>
          วันที่เริ่มต้น
          <input aria-label="วันที่เริ่ม Backfill" type="date" value={customStart} min={options?.registry.earliestDate ?? undefined} max={options?.registry.latestDate ?? undefined} disabled={startMode !== 'custom' || needsMapping || isRunning} onChange={(event) => { setCustomStart(event.target.value); setPreview(null) }} />
        </label>
        <button className="primary-action" type="button" disabled={!sourceSku || needsMapping || busy !== null || isRunning} onClick={() => void createPreview()}>
          {busy === 'preview' ? 'กำลังตรวจสอบ…' : 'Preview ก่อนเริ่ม'}
        </button>
      </div>

      {selectedUnmapped && (
        <div className="sku-backfill-mapping-gate" role="status">
          <AlertTriangle size={17} aria-hidden="true" />
          <div>
            <strong>SKU {selectedUnmapped.sourceSku} ยังไม่ได้ Mapping</strong>
            <span>สถานะปัจจุบัน: {interestStatusLabels[selectedUnmapped.interestStatus]} · ต้อง Export/แก้ไข/Import Mapping และยืนยันเป็น Active ก่อน Preview</span>
            {selectedUnmapped.interestStatus === 'ignored' && <small>เมื่อ Mapping ยืนยันแล้ว ระบบจะเปลี่ยน SKU นี้เป็น Active โดยอัตโนมัติ</small>}
          </div>
          <button className="secondary-action" type="button" onClick={goToMapping}>
            ไปกำหนด Mapping <ArrowUpRight size={15} aria-hidden="true" />
          </button>
        </div>
      )}

      {preview && (
        <div className="sku-backfill-preview">
          <div className="sku-backfill-counts" aria-label="สรุป Preview Backfill">
            <span data-tone="primary"><small>พร้อมเติม</small><strong>{preview.counts.candidate}</strong></span>
            <span><small>มีข้อมูลแล้ว</small><strong>{preview.counts.already_present}</strong></span>
            <span data-tone="warning"><small>รอ Import วันนั้น</small><strong>{preview.counts.waiting_for_batch}</strong></span>
            <span data-tone="danger"><small>ไฟล์ขัดแย้ง</small><strong>{preview.counts.source_conflict}</strong></span>
          </div>
          {preview.mappingWillMoveTo && !preview.mappingConflict && (
            <p className="sku-backfill-note"><CheckCircle2 size={15} />ระบบจะปรับ Mapping effective date ย้อนเป็น {formatDate(preview.mappingWillMoveTo)} เมื่อยืนยัน</p>
          )}
          {preview.mappingConflict && (
            <p className="sku-backfill-note" data-tone="error"><AlertTriangle size={15} />ช่วงวันที่นี้ชนกับ Mapping เดิม จึงยังเริ่มงานไม่ได้</p>
          )}
          <div className="sku-backfill-preview-footer">
            <span>ช่วง {formatDate(preview.rangeStart)} – {formatDate(preview.rangeEnd)}</span>
            <button className="primary-action" type="button" disabled={preview.mappingConflict || preview.counts.candidate === 0 || busy !== null} onClick={() => void start()}>
              <Play size={15} aria-hidden="true" />{busy === 'start' ? 'กำลังส่งงาน…' : 'ยืนยันและเริ่ม Backfill'}
            </button>
          </div>
        </div>
      )}

      {run && (run.mode === 'sku_backfill' || run.mode === 'registry') && (
        <div className="sku-backfill-run" data-status={run.status}>
          <div>
            <small>{run.mode === 'registry' ? 'File Registry' : 'Backfill'} Run #{run.runId}</small>
            <strong>{run.mode === 'registry' ? 'ตรวจรายการไฟล์ต้นทาง' : run.targetSku} · {runStatus(run)}</strong>
            <span>{run.message}</span>
          </div>
          <div className="sku-backfill-progress" aria-label={`ดำเนินการแล้ว ${progress?.percent ?? 0}%`}>
            <i style={{ width: `${progress?.percent ?? (run.status === 'success' || run.status === 'success_with_warnings' ? 100 : 0)}%` }} />
          </div>
          <b>{progress?.processed ?? run.results.length} / {progress?.total ?? run.counts.found} วัน</b>
          {run.mode === 'sku_backfill' && (run.status === 'queued' || run.status === 'running') && (
            <button className="secondary-action" type="button" disabled={busy !== null} onClick={() => void stop()}>
              <PauseCircle size={15} />{busy === 'stop' ? 'กำลังขอหยุด…' : 'หยุดหลังจบไฟล์ปัจจุบัน'}
            </button>
          )}
          {run.mode === 'sku_backfill' && run.status === 'stopped' && (
            <button className="primary-action" type="button" disabled={busy !== null} onClick={() => void resume()}>
              <Play size={15} />{busy === 'resume' ? 'กำลังส่งงาน…' : 'ทำต่อจากที่เหลือ'}
            </button>
          )}
        </div>
      )}

      {message && <div className="settings-message" data-tone={message.tone === 'error' ? 'error' : undefined} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div>}
        </>
      )}
    </section>
  )
}
