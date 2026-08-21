import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Clock3, Download, FileCheck2, TriangleAlert, Upload } from 'lucide-react'
import { ItemDetailDrawer } from './ItemDetailDrawer'
import { PerformanceMatrix } from './PerformanceMatrix'
import { PerformanceToolbar } from './PerformanceToolbar'
import { exportItemMappings, fetchPerformance, importItemMappings } from './performanceApi'
import { formatMetric, monthKey, monthKeys, pointsForView, sumMetric } from './performanceMath'
import type { Branch, Dimension, MappingStatus, Metric, Mode, PerformanceItem, PerformanceResponse, SelectedCell } from './types'

const emptyDates: string[] = []
const emptyBranches: Branch[] = []
const emptyItems: PerformanceItem[] = []
const branchMatrixPageSize = 25
const compactMatrixPageSize = 100
const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}

interface PerformancePageProps {
  initialData?: PerformanceResponse
}

export function PerformancePage({ initialData }: PerformancePageProps) {
  const [data, setData] = useState<PerformanceResponse | null>(initialData ?? null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(!initialData)
  const [mode, setMode] = useState<Mode>('sales')
  const [metric, setMetric] = useState<Metric>('amount')
  const [dimension, setDimension] = useState<Dimension>('branch')
  const [dateRange, setDateRange] = useState('all')
  const [branchMonth, setBranchMonth] = useState('latest')
  const [branchId, setBranchId] = useState('all')
  const [mappingStatus, setMappingStatus] = useState<MappingStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [heatmap, setHeatmap] = useState(true)
  const [showDescriptions, setShowDescriptions] = useState(true)
  const [hideUnmapped, setHideUnmapped] = useState(false)
  const [selected, setSelected] = useState<SelectedCell | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [isExporting, setIsExporting] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [exchangeMessage, setExchangeMessage] = useState<{ kind: 'success' | 'error', text: string } | null>(null)
  const importInputRef = useRef<HTMLInputElement>(null)
  const pageSize = dimension === 'branch' && branchId === 'all'
    ? branchMatrixPageSize
    : compactMatrixPageSize

  useEffect(() => {
    const normalizedSearch = search.trim()
    if (normalizedSearch === debouncedSearch) return
    const timer = window.setTimeout(() => {
      setIsLoading(true)
      setDebouncedSearch(normalizedSearch)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [debouncedSearch, search])

  useEffect(() => {
    if (initialData) return
    const controller = new AbortController()
    fetchPerformance({
      dateRange,
      branchId,
      mappingStatus,
      hideUnmapped,
      search: debouncedSearch,
      page,
      pageSize,
      dimension,
      mode,
      branchMonth,
      signal: controller.signal,
    })
      .then(setData)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(error instanceof Error ? error.message : 'โหลดข้อมูลไม่สำเร็จ')
        }
      })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false) })
    return () => controller.abort()
  }, [branchId, branchMonth, dateRange, debouncedSearch, dimension, hideUnmapped, initialData, mappingStatus, mode, page, pageSize, refreshKey])

  const handleExport = async () => {
    setIsExporting(true)
    setExchangeMessage(null)
    try {
      const { blob, filename } = await exportItemMappings(dateRange)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
      setExchangeMessage({ kind: 'success', text: 'Export Item และ Branch Mapping แล้ว' })
    } catch (error) {
      setExchangeMessage({ kind: 'error', text: error instanceof Error ? error.message : 'Export Mapping ไม่สำเร็จ' })
    } finally {
      setIsExporting(false)
    }
  }

  const handleImport = async (file: File) => {
    setIsImporting(true)
    setExchangeMessage(null)
    try {
      const report = await importItemMappings(file, dateRange)
      const details = [`Item ใหม่ ${report.inserted_pending}`, `Item เดิม ${report.unchanged}`]
      if (report.conflicts) details.push(`ขัดแย้ง ${report.conflicts}`)
      if (report.new_source_skus) details.push(`SKU ใหม่ ${report.new_source_skus}`)
      details.push(`Branch ใหม่ ${report.branch_inserted_pending}`, `Branch อัปเดตชื่อ ${report.branch_updated}`, `Branch เดิม ${report.branch_unchanged}`)
      if (report.branch_conflicts) details.push(`Branch ขัดแย้ง ${report.branch_conflicts}`)
      setExchangeMessage({ kind: report.conflicts || report.branch_conflicts ? 'error' : 'success', text: `Import สำเร็จ: ${details.join(' · ')}` })
      setIsLoading(true)
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setExchangeMessage({ kind: 'error', text: error instanceof Error ? error.message : 'Import Mapping ไม่สำเร็จ' })
    } finally {
      setIsImporting(false)
      if (importInputRef.current) importInputRef.current.value = ''
    }
  }

  const dates = data?.dates ?? emptyDates
  const months = data?.months ?? monthKeys(dates)
  const branches = data?.branches ?? emptyBranches
  const performanceItems = data?.items ?? emptyItems

  const selectedBranchMonth = branchMonth === 'latest' ? data?.selectedMonth ?? months.at(-1) : branchMonth
  const selectedDates = useMemo(() => (
    mode === 'sales' && dimension === 'branch' && selectedBranchMonth
      ? dates.filter((value) => monthKey(value) === selectedBranchMonth)
      : dateRange === 'all' ? dates : [dateRange]
  ), [dateRange, dates, dimension, mode, selectedBranchMonth])
  const visibleItems = useMemo(() => {
    if (!initialData) return performanceItems
    const term = search.trim().toLowerCase()
    return performanceItems.filter((item) => {
      const matchesSearch = !term || [item.sku, item.twdDescription, item.waItem, item.waDescription]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(term))
      const matchesMapping = mappingStatus === 'all' || item.mappingStatus === mappingStatus
      const matchesUnmappedVisibility = !hideUnmapped || item.mappingStatus !== 'unmatched'
      const hasData = item.points.some((point) => selectedDates.includes(point.date) && (branchId === 'all' || point.branchId === branchId))
      return matchesSearch && matchesMapping && matchesUnmappedVisibility && hasData
    })
  }, [branchId, hideUnmapped, initialData, mappingStatus, performanceItems, search, selectedDates])

  const allPoints = visibleItems.flatMap((item) => pointsForView(item, selectedDates, branchId, mode, 'branch'))
  const hasServerSummary = !initialData && data?.summary
  const totalAmount = hasServerSummary ? hasServerSummary.amount : sumMetric(allPoints, 'amount')
  const totalQty = hasServerSummary ? hasServerSummary.qty : sumMetric(allPoints, 'qty')
  const pendingCount = hasServerSummary
    ? hasServerSummary.mappingAttention
    : visibleItems.filter((item) => item.mappingStatus !== 'confirmed').length
  const activeBranches = !initialData && data
    ? data.meta.totalBranches
    : new Set(allPoints.map((point) => point.branchId)).size
  const selectedItem = selected ? performanceItems.find((item) => item.sku === selected.sku) : undefined
  const latestImport = data?.latestImport
  const latestDate = latestImport?.dataDate
    ? new Intl.DateTimeFormat('th-TH-u-ca-gregory', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${latestImport.dataDate}T00:00:00`))
    : 'กำลังโหลด'

  return (
    <>
      <section className="pulse-strip" aria-label="สถานะข้อมูล">
        <div><CheckCircle2 size={17} aria-hidden="true" /><span><small>วันที่ข้อมูลล่าสุด</small><strong>{latestDate}</strong></span></div>
        <div><Clock3 size={17} aria-hidden="true" /><span><small>แหล่งข้อมูล</small><strong>PostgreSQL · TWD</strong></span></div>
        <div className={latestImport?.warnings.length ? 'status-warning' : undefined}><TriangleAlert size={17} aria-hidden="true" /><span><small>Data Quality</small><strong>{latestImport?.warnings.length ? `${latestImport.warnings.length} Warning` : 'ผ่าน'}</strong></span></div>
        <div><FileCheck2 size={17} aria-hidden="true" /><span><small>Import ล่าสุด</small><strong>{latestImport ? `${latestImport.rowCount.toLocaleString('en-US')} แถว` : 'กำลังโหลด'}</strong></span></div>
      </section>

      <div className="page-content">
        <div className="page-intro">
          <div><span className="eyebrow">ข้อมูล Sales และ Inventory</span><h2>Matrix Performance ของ TWD</h2><p>ติดตามแต่ละ Item ตาม Branch และวัน โดยยังเห็นรหัสจากต้นทางครบถ้วน</p></div>
          <div className="data-grain"><span>ระดับข้อมูล</span><strong>SKU × BRANCH × DAY</strong></div>
        </div>

        <PerformanceToolbar
          mode={mode}
          metric={metric}
          dimension={dimension}
          dateRange={dateRange}
          branchMonth={branchMonth}
          selectedBranchMonth={selectedBranchMonth}
          branchId={branchId}
          mappingStatus={mappingStatus}
          search={search}
          heatmap={heatmap}
          showDescriptions={showDescriptions}
          hideUnmapped={hideUnmapped}
          branches={branches}
          dates={dates}
          months={months}
          onModeChange={setMode}
          onMetricChange={setMetric}
          onDimensionChange={(value) => { setDimension(value); if (value === 'month') setDateRange('all'); setPage(1); setIsLoading(true); setLoadError(null) }}
          onDateRangeChange={(value) => { setDateRange(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchMonthChange={(value) => { setBranchMonth(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchChange={(value) => { setBranchId(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onMappingStatusChange={(value) => { setMappingStatus(value); if (value === 'unmatched') setHideUnmapped(false); setPage(1); setIsLoading(true); setLoadError(null) }}
          onSearchChange={(value) => { setSearch(value); setPage(1); setLoadError(null) }}
          onHeatmapChange={setHeatmap}
          onShowDescriptionsChange={setShowDescriptions}
          onHideUnmappedChange={(value) => { setHideUnmapped(value); if (value && mappingStatus === 'unmatched') setMappingStatus('all'); setPage(1); setIsLoading(true); setLoadError(null) }}
        />

        {loadError && <div className="empty-state" role="alert"><strong>เชื่อมต่อ Backend ไม่สำเร็จ</strong><span>{loadError}</span></div>}

        <section className="kpi-ledger" aria-label="สรุป Performance">
          <article><span>Amount</span><strong>{formatMetric(totalAmount, 'amount')}</strong><small>{hasServerSummary ? 'รวมทุก SKU ในช่วงวันที่เลือก' : 'รวมข้อมูลที่แสดง'}</small></article>
          <article><span>Sales Qty</span><strong>{formatMetric(totalQty, 'qty')}</strong><small>{totalQty < 0 ? 'ยอด Return สุทธิ' : 'รวม Return และ Adjustment'}</small></article>
          <article><span>SKU ที่แสดง</span><strong>{visibleItems.length.toLocaleString('en-US')}</strong><small>จาก {(data?.meta.totalSkus ?? 0).toLocaleString('en-US')} SKU</small></article>
          <article><span>Branch ที่มียอด</span><strong>{activeBranches}</strong><small>จาก {data?.meta.totalBranches ?? 0} Branch ของ TWD</small></article>
          <article data-attention={pendingCount > 0 || undefined}><span>Mapping ที่ต้องตรวจ</span><strong>{pendingCount}</strong><small>Item ที่ต้องตรวจสอบ</small></article>
        </section>

        <div className="matrix-heading">
          <div><h3>{mode === 'sales' ? 'Sales' : 'Inventory'} ตาม {dimension === 'branch' ? 'Branch' : dimension === 'month' ? 'Month' : 'Date'}</h3><span>{metric === 'amount' ? 'Amount' : metric === 'qty' ? 'Qty' : metric === 'stockOh' ? 'Stock On Hand' : 'Stock On Order'} · {dimension === 'month' ? 'ทุกเดือนที่มีข้อมูล' : mode === 'sales' && dimension === 'branch' && selectedBranchMonth ? formatMonth(selectedBranchMonth) : selectedDates.length === 1 ? selectedDates[0] : '16–17 ส.ค. 2026'}</span></div>
          <div className="matrix-heading-tools">
            <div className="heat-legend" aria-label="คำอธิบาย Heatmap"><span>ต่ำ</span><i className="heat-low" /><i className="heat-medium" /><i className="heat-high" /><span>สูง</span><i className="heat-negative" /><span>Return</span></div>
            <div className="matrix-actions">
              <button type="button" disabled={isExporting || isImporting} onClick={handleExport}><Download size={15} />{isExporting ? 'กำลัง Export…' : 'Export Mapping'}</button>
              <button type="button" disabled={isExporting || isImporting} onClick={() => importInputRef.current?.click()}><Upload size={15} />{isImporting ? 'กำลัง Import…' : 'Import Mapping'}</button>
              <input ref={importInputRef} className="sr-only" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleImport(file) }} />
            </div>
          </div>
        </div>

        {exchangeMessage && <div className={`exchange-message exchange-${exchangeMessage.kind}`} role="status">{exchangeMessage.text}</div>}

        <PerformanceMatrix
          items={data ? visibleItems : null}
          branches={branches}
          totalSkus={data?.meta.totalSkus ?? 0}
          page={data?.meta.page ?? page}
          totalPages={data?.meta.totalPages ?? 1}
          isLoading={isLoading}
          dates={selectedDates}
          branchId={branchId}
          mode={mode}
          metric={metric}
          dimension={dimension}
          heatmap={heatmap}
          showDescriptions={showDescriptions}
          columnTotals={data?.columnTotals}
          grandTotal={metric === 'amount' ? totalAmount : metric === 'qty' ? totalQty : undefined}
          selected={selected}
          onSelect={setSelected}
          onPageChange={(value) => { setPage(value); setIsLoading(true); setLoadError(null) }}
        />
      </div>

      {selected && selectedItem && (
        <ItemDetailDrawer item={selectedItem} selected={selected} dates={selectedDates} branchId={branchId} metric={metric} branches={branches} onClose={() => setSelected(null)} />
      )}
    </>
  )
}
