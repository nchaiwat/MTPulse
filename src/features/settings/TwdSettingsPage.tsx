import { useEffect, useRef, useState } from 'react'
import { Building2, CalendarDays, Download, FileSpreadsheet, PackageSearch, Rows3, Upload } from 'lucide-react'
import {
  downloadDataCoverage,
  exportItemMappings,
  fetchUnmatchedVisibility,
  importItemMappings,
  updateUnmatchedVisibility,
  updateReportPageSize,
  type UnmatchedVisibility,
} from './twdSettingsApi'
import { SkuBackfillPanel } from './SkuBackfillPanel'

const defaultSettings: UnmatchedVisibility = {
  showUnmatchedItems: false,
  showUnmatchedBranches: false,
  mappingAttentionItems: 0,
  mappingAttentionBranches: 0,
  reportPageSize: 25,
  hasData: false,
}

const currentYear = new Date().getFullYear()
const coverageYears = Array.from({ length: currentYear - 2025 + 1 }, (_, index) => currentYear - index)

export function TwdSettingsPage({
  embedded = false,
  mtCode = 'TWD',
  mtName = 'ไทวัสดุ',
}: {
  embedded?: boolean
  mtCode?: 'TWD' | 'HP' | 'MH'
  mtName?: string
}) {
  const [settings, setSettings] = useState(defaultSettings)
  const [isLoading, setIsLoading] = useState(true)
  const [updating, setUpdating] = useState<'item' | 'branch' | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [mappingMessage, setMappingMessage] = useState<{ tone: 'success' | 'error', text: string } | null>(null)
  const [mappingRevision, setMappingRevision] = useState(0)
  const [coverageYear, setCoverageYear] = useState(currentYear)
  const [isCoverageDownloading, setIsCoverageDownloading] = useState(false)
  const [isPageSizeUpdating, setIsPageSizeUpdating] = useState(false)
  const [coverageMessage, setCoverageMessage] = useState<{ tone: 'success' | 'error', text: string } | null>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchUnmatchedVisibility(mtCode, controller.signal)
      .then((loaded) => setSettings({
        ...defaultSettings,
        ...loaded,
        hasData: loaded.hasData ?? true,
      }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(error instanceof Error ? error.message : 'โหลดการตั้งค่าไม่สำเร็จ')
        }
      })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false) })
    return () => controller.abort()
  }, [mtCode])

  const changeSetting = async (
    target: 'item' | 'branch',
    nextValue: boolean,
  ) => {
    const nextSettings = {
      ...settings,
      [target === 'item' ? 'showUnmatchedItems' : 'showUnmatchedBranches']: nextValue,
    }
    setUpdating(target)
    setMessage(null)
    try {
      const saved = await updateUnmatchedVisibility(nextSettings, mtCode)
      setSettings(saved)
      setMessage(
        nextValue
          ? `เปิดแสดง ${target === 'item' ? 'Item' : 'Branch'} Unmatch แล้ว ข้อมูลจะถูกนำไปรวมในรายงาน`
          : `ปิดแสดง ${target === 'item' ? 'Item' : 'Branch'} Unmatch แล้ว ข้อมูลจะไม่ถูกนำไปรวมในรายงาน`,
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'บันทึกการตั้งค่าไม่สำเร็จ')
    } finally {
      setUpdating(null)
    }
  }

  const handleExport = async () => {
    setIsExporting(true)
    setMappingMessage(null)
    try {
      const { blob, filename } = await exportItemMappings(mtCode)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
      setMappingMessage({ tone: 'success', text: 'Export Item และ Branch Mapping แล้ว' })
    } catch (error) {
      setMappingMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Export Mapping ไม่สำเร็จ' })
    } finally {
      setIsExporting(false)
    }
  }

  const handleImport = async (file: File) => {
    setIsImporting(true)
    setMappingMessage(null)
    try {
      const report = await importItemMappings(file, mtCode)
      const details = [`Item ใหม่ ${report.inserted_pending}`, `Item เดิม ${report.unchanged}`]
      if (report.conflicts) details.push(`ขัดแย้ง ${report.conflicts}`)
      details.push(`Branch ใหม่ ${report.branch_inserted_pending}`, `Branch อัปเดต ${report.branch_updated}`, `Branch เดิม ${report.branch_unchanged}`)
      if (report.branch_conflicts) details.push(`Branch ขัดแย้ง ${report.branch_conflicts}`)
      setMappingMessage({ tone: report.conflicts || report.branch_conflicts ? 'error' : 'success', text: `Import สำเร็จ: ${details.join(' · ')}` })
      setMappingRevision((current) => current + 1)
    } catch (error) {
      setMappingMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Import Mapping ไม่สำเร็จ' })
    } finally {
      setIsImporting(false)
      if (importInputRef.current) importInputRef.current.value = ''
    }
  }

  const handlePageSizeChange = async (reportPageSize: number) => {
    setIsPageSizeUpdating(true)
    setMessage(null)
    try {
      const saved = await updateReportPageSize(reportPageSize, mtCode)
      setSettings((current) => ({
        ...current,
        reportPageSize: saved.reportPageSize,
      }))
      setMessage(saved.reportPageSize === 0 ? 'ตั้งค่ารายงานให้แสดง SKU ทั้งหมดแล้ว' : `ตั้งค่ารายงานให้แสดง ${saved.reportPageSize} SKU ต่อหน้าแล้ว`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'บันทึกจำนวน SKU ต่อหน้าไม่สำเร็จ')
    } finally {
      setIsPageSizeUpdating(false)
    }
  }
  const handleCoverageDownload = async () => {
    setIsCoverageDownloading(true)
    setCoverageMessage(null)
    try {
      const { blob, filename } = await downloadDataCoverage(mtCode, coverageYear)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
      setCoverageMessage({ tone: 'success', text: `Download สถานะข้อมูลปี ${coverageYear} แล้ว` })
    } catch (error) {
      setCoverageMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Download สถานะข้อมูลไม่สำเร็จ' })
    } finally {
      setIsCoverageDownloading(false)
    }
  }

  return (
    <div className={embedded ? 'settings-page settings-page-embedded' : 'settings-page page-content'}>
      {!embedded && <div className="settings-intro">
        <div>
          <span className="eyebrow">การตั้งค่า / {mtCode}</span>
          <h2>การตั้งค่า{mtName}</h2>
          <p>Mapping ที่ยืนยันจากไฟล์ Excel จะแสดงในรายงานโดยอัตโนมัติ</p>
        </div>
        <div className="scope-rule">
          <span>กฎการคำนวณ</span>
          <strong>Unmatch ที่ไม่แสดง จะไม่ถูกนำไปรวมใน SUM และ KPI</strong>
        </div>
      </div>
}
      <section id={`${mtCode.toLowerCase()}-item-mapping`} className="mapping-settings" aria-labelledby="mapping-exchange-heading">
        <header>
          <span className="setting-icon"><FileSpreadsheet size={19} aria-hidden="true" /></span>
          <div>
            <span className="eyebrow">Mapping Excel</span>
            <h3 id="mapping-exchange-heading">Item และ Branch Mapping</h3>
            <p>Export ไปตรวจสอบหรือแก้ไขใน Excel แล้ว Import กลับเข้าการตั้งค่า {mtName}</p>
          </div>
          <div className="mapping-settings-actions">
            <button id="mapping-export-button" className="secondary-action" type="button" disabled={isExporting || isImporting} onClick={() => void handleExport()}><Download size={15} />{isExporting ? 'กำลัง Export…' : 'Export Mapping'}</button>
            <button className="primary-action" type="button" disabled={isExporting || isImporting} onClick={() => importInputRef.current?.click()}><Upload size={15} />{isImporting ? 'กำลัง Import…' : 'Import Mapping'}</button>
            <input ref={importInputRef} className="sr-only" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleImport(file) }} />
          </div>
        </header>
        <div className="mapping-attention-summary" aria-label="รายการ Mapping ที่ต้องตรวจ">
          {isLoading
            ? <span><PackageSearch size={15} aria-hidden="true" /><strong>กำลังโหลดข้อมูล…</strong></span>
            : settings.hasData === false
            ? <span><PackageSearch size={15} aria-hidden="true" /><strong>ยังไม่มีข้อมูล</strong></span>
            : <>
                <span><PackageSearch size={15} aria-hidden="true" /><strong>{settings.mappingAttentionItems.toLocaleString('en-US')}</strong> Item</span>
                <span><Building2 size={15} aria-hidden="true" /><strong>{settings.mappingAttentionBranches.toLocaleString('en-US')}</strong> Branch</span>
                <small>ตรวจสอบโดย Export Mapping แก้ไขใน Excel แล้ว Import กลับ</small>
              </>}
        </div>
        {mappingMessage && <div className="settings-message" data-tone={mappingMessage.tone === 'error' ? 'error' : undefined} role="status">{mappingMessage.text}</div>}
      </section>
      <SkuBackfillPanel key={mappingRevision} mtCode={mtCode} />
      <section className="report-display-settings" aria-labelledby="report-display-heading">
        <header>
          <span className="setting-icon"><Rows3 size={19} aria-hidden="true" /></span>
          <div>
            <span className="eyebrow">Report display</span>
            <h3 id="report-display-heading">การแสดงผลรายงาน</h3>
            <p>จำกัดจำนวนแถวที่โหลดในแต่ละหน้า เพื่อให้ Matrix ทำงานได้ลื่นเมื่อข้อมูลเพิ่มขึ้น</p>
          </div>
          <div className="report-display-actions">
            <label htmlFor="report-page-size">SKU ต่อหน้า</label>
            <select id="report-page-size" aria-label="จำนวน SKU ต่อหน้า" value={settings.reportPageSize} disabled={isLoading || isPageSizeUpdating} onChange={(event) => void handlePageSizeChange(Number(event.target.value))}>
              <option value={0}>ทั้งหมด</option>
              {[25, 50, 100].map((size) => <option key={size} value={size}>{size} SKU</option>)}
            </select>
          </div>
        </header>
      </section>
      <section className="data-coverage-settings" aria-labelledby="data-coverage-heading">
        <header>
          <span className="setting-icon"><CalendarDays size={19} aria-hidden="true" /></span>
          <div>
            <span className="eyebrow">Data coverage</span>
            <h3 id="data-coverage-heading">ความครบถ้วนของข้อมูล</h3>
            <p>Download เพื่อตรวจสอบว่าวันใดมีข้อมูลหรือขาดข้อมูลในระบบ</p>
          </div>
          <div className="data-coverage-actions">
            <label htmlFor="coverage-year">ปี</label>
            <select id="coverage-year" value={coverageYear} onChange={(event) => setCoverageYear(Number(event.target.value))}>
              {coverageYears.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
            <button className="secondary-action" type="button" disabled={isCoverageDownloading} onClick={() => void handleCoverageDownload()}><Download size={15} />{isCoverageDownloading ? 'กำลัง Download…' : 'Download สถานะข้อมูล'}</button>
          </div>
        </header>
        {coverageMessage && <div className="settings-message" data-tone={coverageMessage.tone === 'error' ? 'error' : undefined} role="status">{coverageMessage.text}</div>}
      </section>
      <section className="unmatched-settings" aria-labelledby="unmatched-heading">
        <header>
          <span className="eyebrow">Unmatched data</span>
          <h3 id="unmatched-heading">ข้อมูลที่ยังไม่ Mapping</h3>
          <p>เปิดเฉพาะเมื่อต้องการตรวจสอบข้อมูลต้นทางที่ยังไม่ได้ยืนยันใน Excel</p>
        </header>

        <div className="unmatched-options" data-loading={isLoading || undefined}>
          <article>
            <span className="setting-icon"><Building2 size={19} aria-hidden="true" /></span>
            <div>
              <h4>Branch Unmatch</h4>
              <p>Branch ที่ยังไม่มี WA Branch Mapping</p>
              <small>{settings.showUnmatchedBranches ? 'แสดงและรวมยอดในรายงาน' : 'ไม่แสดงและไม่รวมยอด'}</small>
            </div>
            <button
              className="global-scope-switch"
              type="button"
              role="switch"
              aria-checked={settings.showUnmatchedBranches}
              aria-label="แสดง Branch Unmatch"
              disabled={isLoading || updating !== null}
              onClick={() => void changeSetting('branch', !settings.showUnmatchedBranches)}
            >
              <span aria-hidden="true"><i /></span>
              {settings.showUnmatchedBranches ? 'แสดง' : 'ไม่แสดง'}
            </button>
          </article>

          <article>
            <span className="setting-icon"><PackageSearch size={19} aria-hidden="true" /></span>
            <div>
              <h4>Item Unmatch</h4>
              <p>Item ที่ยังไม่มี WA Item Mapping</p>
              <small>{settings.showUnmatchedItems ? 'แสดงและรวมยอดในรายงาน' : 'ไม่แสดงและไม่รวมยอด'}</small>
            </div>
            <button
              className="global-scope-switch"
              type="button"
              role="switch"
              aria-checked={settings.showUnmatchedItems}
              aria-label="แสดง Item Unmatch"
              disabled={isLoading || updating !== null}
              onClick={() => void changeSetting('item', !settings.showUnmatchedItems)}
            >
              <span aria-hidden="true"><i /></span>
              {settings.showUnmatchedItems ? 'แสดง' : 'ไม่แสดง'}
            </button>
          </article>
        </div>

        {message && <div className="settings-message" role="status">{message}</div>}
      </section>
    </div>
  )
}
