import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Clock3, Download, FileCheck2, TriangleAlert } from 'lucide-react'
import { ItemDetailDrawer } from './ItemDetailDrawer'
import { PerformanceMatrix } from './PerformanceMatrix'
import { PerformanceToolbar } from './PerformanceToolbar'
import { downloadPerformanceReport, fetchPerformance, fetchPerformanceItemDetail, fetchSkuOptions } from './performanceApi'
import { formatMetric, monthKey, monthKeys, pointsForView, sumMetric } from './performanceMath'
import type { Branch, BranchPeriod, Dimension, Metric, Mode, PerformanceItem, PerformanceResponse, SalesBasis, SelectedCell, SkuOption } from './types'
import { formatDisplayDate } from '../../shared/dateFormat'

const emptyDates: string[] = []
const emptyBranches: Branch[] = []
const emptyItems: PerformanceItem[] = []
const performanceViewStorageKey = 'mtpulse.performance.twd.current-view'

interface PerformanceViewState {
  mode: Mode
  salesBasis: SalesBasis
  metric: Metric
  monthFrom: string
  monthTo: string
  dimension: Dimension
  dateFrom: string
  dateTo: string
  branchMonth: string
  branchPeriod: BranchPeriod
  branchIds: string[]
  skuIds: string[]
  page: number
  heatmap: boolean
  showDescriptions: boolean
}

const defaultPerformanceView: PerformanceViewState = {
  mode: 'sales',
  salesBasis: 'net',
  metric: 'amount',
  dimension: 'branch',
  monthFrom: '',
  monthTo: '',
  dateFrom: '',
  dateTo: '',
  branchMonth: 'latest',
  branchPeriod: 'month',
  branchIds: [],
  skuIds: [],
  page: 1,
  heatmap: true,
  showDescriptions: true,
}

const loadPerformanceView = (): PerformanceViewState => {
  try {
    const saved = window.localStorage.getItem(performanceViewStorageKey)
    if (!saved) return defaultPerformanceView
    const parsed = JSON.parse(saved) as Partial<PerformanceViewState> & {
      dateRange?: string
      branchDate?: string
      branchId?: string
    }
    const legacyDate = parsed.branchDate && !['all', 'latest'].includes(parsed.branchDate)
      ? parsed.branchDate
      : parsed.dateRange && parsed.dateRange !== 'all' ? parsed.dateRange : ''
    const branchIds = Array.isArray(parsed.branchIds) ? parsed.branchIds : parsed.branchId && parsed.branchId !== 'all' ? [parsed.branchId] : []
    return { ...defaultPerformanceView, ...parsed, dateFrom: parsed.dateFrom ?? legacyDate, dateTo: parsed.dateTo ?? legacyDate, branchIds }
  } catch {
    return defaultPerformanceView
  }
}

const formatDateRange = (dates: string[]) => {
  if (dates.length === 0) return 'ไม่มีข้อมูล'
  return dates.length === 1 ? formatDisplayDate(dates[0]) : formatDisplayDate(dates[0]) + ' – ' + formatDisplayDate(dates.at(-1)!)
}

const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}

interface PerformancePageProps {
  initialData?: PerformanceResponse
}

export function PerformancePage({ initialData }: PerformancePageProps) {
  const [savedView] = useState(loadPerformanceView)
  const [data, setData] = useState<PerformanceResponse | null>(initialData ?? null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(!initialData)
  const [mode, setMode] = useState<Mode>(savedView.mode)
  const [salesBasis, setSalesBasis] = useState<SalesBasis>(savedView.salesBasis)
  const [metric, setMetric] = useState<Metric>(savedView.metric)
  const [dimension, setDimension] = useState<Dimension>(savedView.dimension)
  const [dateFrom, setDateFrom] = useState(savedView.dateFrom)
  const [dateTo, setDateTo] = useState(savedView.dateTo)
  const [branchMonth, setBranchMonth] = useState(savedView.branchMonth)
  const [branchPeriod, setBranchPeriod] = useState<BranchPeriod>(savedView.branchPeriod)
  const [monthFrom, setMonthFrom] = useState(savedView.monthFrom)
  const [monthTo, setMonthTo] = useState(savedView.monthTo)
  const [branchIds, setBranchIds] = useState(savedView.branchIds)
  const [skuIds, setSkuIds] = useState(savedView.skuIds)
  const [skuOptions, setSkuOptions] = useState<SkuOption[]>(() => (initialData?.items ?? []).map((item) => ({
    sku: item.sku,
    twdDescription: item.twdDescription,
    waItem: item.waItem,
    waDescription: item.waDescription,
    itemType: item.itemType ?? 'normal',
  })))
  const [skuOptionsLoading, setSkuOptionsLoading] = useState(!initialData)
  const [page, setPage] = useState(savedView.page)
  const [heatmap, setHeatmap] = useState(savedView.heatmap)
  const [showDescriptions, setShowDescriptions] = useState(savedView.showDescriptions)
  const [selected, setSelected] = useState<SelectedCell | null>(null)
  const [detailResult, setDetailResult] = useState<{ key: string, item: PerformanceItem | null, error: string | null } | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadMessage, setDownloadMessage] = useState<{ kind: 'success' | 'error', text: string } | null>(null)
  const availableDates = data?.availableDates ?? data?.dates ?? emptyDates

  useEffect(() => {
    const currentView: PerformanceViewState = {
      mode,
      salesBasis,
      metric,
      dimension,
      dateFrom,
      dateTo,
      branchMonth,
      branchPeriod,
      monthFrom,
      monthTo,
      branchIds,
      skuIds,
      page,
      heatmap,
      showDescriptions,
    }
    window.localStorage.setItem(performanceViewStorageKey, JSON.stringify(currentView))
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateTo, dimension, heatmap, metric, mode, monthFrom, monthTo, page, salesBasis, showDescriptions, skuIds])


  useEffect(() => {
    if (initialData) return
    const controller = new AbortController()
    fetchSkuOptions(controller.signal)
      .then(setSkuOptions)
      .finally(() => { if (!controller.signal.aborted) setSkuOptionsLoading(false) })
    return () => controller.abort()
  }, [initialData])

  useEffect(() => {
    if (initialData) return
    const controller = new AbortController()
    fetchPerformance({
      dateFrom,
      dateTo,
      branchIds,
      skuIds,
      search: '',
      page,
      monthFrom,
      monthTo,
      dimension,
      mode,
      salesBasis,
      branchMonth,
      branchPeriod,
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
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateTo, dimension, initialData, mode, monthFrom, monthTo, page, salesBasis, skuIds])

  const needsDailyDetail = Boolean(
    selected
    && !initialData
    && dimension === 'branch'
    && (mode === 'inventory' || (mode === 'sales' && branchPeriod === 'day')),
  )
  const detailRequestKey = needsDailyDetail && selected
    ? [selected.sku, mode, salesBasis, dateFrom, dateTo, branchIds.join(','), monthFrom, monthTo].join('|')
    : ''
  useEffect(() => {
    if (!selected?.sku || !detailRequestKey) return
    const controller = new AbortController()
    fetchPerformanceItemDetail({
      dateFrom,
      dateTo,
      branchIds,
      skuIds,
      search: '',
      page: 1,
      monthFrom,
      monthTo,
      dimension,
      mode,
      salesBasis,
      branchMonth,
      branchPeriod,
    }, selected.sku, controller.signal)
      .then((item) => setDetailResult({ key: detailRequestKey, item, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setDetailResult({ key: detailRequestKey, item: null, error: error instanceof Error ? error.message : 'โหลดรายละเอียดรายวันไม่สำเร็จ' })
      })
    return () => controller.abort()
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateTo, detailRequestKey, dimension, mode, monthFrom, monthTo, salesBasis, selected?.sku, skuIds])

  const handleDownload = async () => {
    setIsDownloading(true)
    setDownloadMessage(null)
    try {
      const { blob, filename } = await downloadPerformanceReport({
        dateFrom,
        dateTo,
        branchIds,
        skuIds,
        search: '',
        page,
        monthFrom,
        monthTo,
        dimension,
        mode,
        salesBasis,
        branchMonth,
        branchPeriod,
      }, metric, showDescriptions)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
      setDownloadMessage({ kind: 'success', text: 'Download รายงาน Excel ตามข้อมูลที่แสดงแล้ว' })
    } catch (error) {
      setDownloadMessage({ kind: 'error', text: error instanceof Error ? error.message : 'Download รายงานไม่สำเร็จ' })
    } finally {
      setIsDownloading(false)
    }
  }
  const dates = data?.dates ?? emptyDates
  const months = data?.months ?? monthKeys(dates)
  const branches = data?.branches ?? emptyBranches
  const performanceItems = data?.items ?? emptyItems

  const selectedBranchMonth = branchMonth === 'latest' ? data?.selectedMonth ?? months.at(-1) : branchMonth
  const selectedDates = useMemo(() => (
    dimension === 'month'
      ? dates.filter((value) => (!monthFrom || monthKey(value) >= monthFrom) && (!monthTo || monthKey(value) <= monthTo))
      : mode === 'sales' && dimension === 'branch' && branchPeriod === 'month' && selectedBranchMonth
      ? dates.filter((value) => monthKey(value) === selectedBranchMonth)
      : dates.filter((value) => (!dateFrom || value >= dateFrom) && (!dateTo || value <= dateTo))
  ), [branchPeriod, dateFrom, dateTo, dates, dimension, mode, monthFrom, monthTo, selectedBranchMonth])
  const visibleItems = useMemo(() => {
    if (!initialData) return performanceItems
    return performanceItems.filter((item) => {
      const matchesSku = skuIds.length === 0 || skuIds.includes(item.sku)
      const hasData = item.points.some((point) => selectedDates.includes(point.date) && (branchIds.length === 0 || branchIds.includes(point.branchId)))
      return matchesSku && hasData
    })
  }, [branchIds, initialData, performanceItems, selectedDates, skuIds])

  const allPoints = visibleItems.flatMap((item) => pointsForView(item, selectedDates, branchIds, mode, 'branch'))
  const hasServerSummary = !initialData && data?.summary
  const totalAmount = hasServerSummary ? hasServerSummary.amount : sumMetric(allPoints, 'amount')
  const totalQty = hasServerSummary ? hasServerSummary.qty : sumMetric(allPoints, 'qty')
  const activeBranches = !initialData && data
    ? data.meta.totalBranches
    : new Set(allPoints.map((point) => point.branchId)).size
  const selectedItem = selected ? performanceItems.find((item) => item.sku === selected.sku) : undefined
  const currentDetail = detailResult?.key === detailRequestKey ? detailResult : null
  const detailLoading = Boolean(detailRequestKey && !currentDetail)
  const latestImport = data?.latestImport
  const latestDate = latestImport?.dataDate
    ? formatDisplayDate(latestImport.dataDate)
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
          salesBasis={salesBasis}
          metric={metric}
          dimension={dimension}
          dateFrom={dateFrom}
          dateTo={dateTo}
          branchMonth={branchMonth}
          selectedBranchMonth={selectedBranchMonth}
          monthFrom={monthFrom}
          monthTo={monthTo}
          branchPeriod={branchPeriod}
          branchIds={branchIds}
          skuIds={skuIds}
          skuOptions={skuOptions}
          skuOptionsLoading={skuOptionsLoading}
          heatmap={heatmap}
          showDescriptions={showDescriptions}
          branches={branches}
          availableDates={availableDates}
          months={months}
          onModeChange={setMode}
          onSalesBasisChange={(value) => { setSalesBasis(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onMetricChange={setMetric}
          onDimensionChange={(value) => { setDimension(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onDateRangeChange={(from, to) => { setDateFrom(from); setDateTo(to); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchMonthChange={(value) => { setBranchMonth(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchPeriodChange={(value) => { setBranchPeriod(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchChange={(value) => { setBranchIds(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onSkuChange={(value) => { setSkuIds(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onHeatmapChange={setHeatmap}
          onShowDescriptionsChange={setShowDescriptions}
          onMonthRangeChange={(from, to) => { setMonthFrom(from); setMonthTo(to); setPage(1); setIsLoading(true); setLoadError(null) }}
        />

        {loadError && <div className="empty-state" role="alert"><strong>เชื่อมต่อ Backend ไม่สำเร็จ</strong><span>{loadError}</span></div>}

        <section className="kpi-ledger" aria-label="สรุป Performance">
          <article><span>Amount · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(totalAmount, 'amount')}</strong><small>{salesBasis === 'gross' ? 'เฉพาะยอดมากกว่า 0 ไม่รวม Return' : hasServerSummary ? 'ยอดสุทธิ รวม Return และ Adjustment' : 'ยอดสุทธิของข้อมูลที่แสดง'}</small></article>
          <article><span>Sales Qty · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(totalQty, 'qty')}</strong><small>{salesBasis === 'gross' ? 'เฉพาะจำนวนมากกว่า 0 ไม่รวม Return' : totalQty < 0 ? 'ยอด Return สุทธิ' : 'รวม Return และ Adjustment'}</small></article>
          <article><span>SKU ที่แสดง</span><strong>{visibleItems.length.toLocaleString('en-US')}</strong><small>จาก {(data?.meta.totalSkus ?? 0).toLocaleString('en-US')} SKU</small></article>
          <article><span>Branch ที่มียอด</span><strong>{activeBranches}</strong><small>จาก {data?.meta.totalBranches ?? 0} Branch ของ TWD</small></article>
        </section>

        <div className="matrix-heading">
          <div><h3>{mode === 'sales' ? 'Sales' : 'Inventory'} ตาม {dimension === 'branch' ? 'Branch' : dimension === 'month' ? 'Month' : 'Date'}</h3><span>{metric === 'amount' ? 'Amount' : metric === 'qty' ? 'Qty' : metric === 'stockOh' ? 'Stock On Hand' : 'Stock On Order'}{mode === 'sales' ? ` · ${salesBasis === 'gross' ? 'Gross Sale Out' : 'Net Sales'}` : ''} · {dimension === 'month' ? (monthFrom && monthTo ? `${formatMonth(monthFrom)} – ${formatMonth(monthTo)}` : 'ทุกเดือนที่มีข้อมูล') : mode === 'sales' && dimension === 'branch' && branchPeriod === 'month' && selectedBranchMonth ? formatMonth(selectedBranchMonth) : formatDateRange(selectedDates)}</span></div>
          <div className="matrix-heading-tools">
            <div className="heat-legend" aria-label="คำอธิบาย Heatmap"><span>ต่ำ</span><i className="heat-low" /><i className="heat-medium" /><i className="heat-high" /><span>สูง</span>{mode !== 'sales' || salesBasis === 'net' ? <><i className="heat-negative" /><span>Return</span></> : null}</div>
            <div className="matrix-actions">
              <button type="button" disabled={isDownloading} onClick={() => void handleDownload()}><Download size={15} />{isDownloading ? 'กำลัง Download…' : 'Download Excel'}</button>
            </div>
          </div>
        </div>

        {downloadMessage && <div className={`exchange-message exchange-${downloadMessage.kind}`} role="status">{downloadMessage.text}</div>}

        <PerformanceMatrix
          items={data ? visibleItems : null}
          branches={branches}
          totalSkus={data?.meta.totalSkus ?? 0}
          page={data?.meta.page ?? page}
          totalPages={data?.meta.totalPages ?? 1}
          isLoading={isLoading}
          dates={selectedDates}
          branchIds={branchIds}
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
        <ItemDetailDrawer item={currentDetail?.item ?? selectedItem} selected={selected} dates={selectedDates} branchIds={branchIds} metric={metric} salesBasis={salesBasis} branches={branches} isLoading={detailLoading} loadError={currentDetail?.error} onClose={() => setSelected(null)} />
      )}
    </>
  )
}
