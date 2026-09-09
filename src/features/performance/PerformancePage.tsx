import { useEffect, useMemo, useState } from 'react'
import { CalendarCheck2, Download } from 'lucide-react'
import { ItemDetailDrawer } from './ItemDetailDrawer'
import { PerformanceMatrix } from './PerformanceMatrix'
import { PerformanceToolbar } from './PerformanceToolbar'
import { downloadPerformanceReport, fetchPerformance, fetchPerformanceItemDetail, fetchSkuOptions, updateSkuAnalysisFlag } from './performanceApi'
import { formatMetric, metricLabel, monthKey, monthKeys, pointsForView, sumMetric } from './performanceMath'
import type { Branch, BranchPeriod, DateRange, Dimension, Metric, Mode, ModernTradeCode, PerformanceItem, PerformanceResponse, SalesBasis, SelectedCell, SkuAnalysisFlagName, SkuFlagFilter, SkuOption } from './types'
import { formatDisplayDate } from '../../shared/dateFormat'

const emptyDates: string[] = []
const emptyBranches: Branch[] = []
const emptyItems: PerformanceItem[] = []
const performanceViewStorageKey = (mtCode: ModernTradeCode) => `mtpulse.performance.${mtCode.toLowerCase()}.current-view`

const modernTrades: Record<ModernTradeCode, { name: string; inventoryMetrics: Metric[] }> = {
  TWD: { name: 'TWD', inventoryMetrics: ['stockOh', 'stockOnOrder'] },
  HP: { name: 'HomePro (HP)', inventoryMetrics: ['stockOh', 'stockValue'] },
  MH: { name: 'MegaHome (MH)', inventoryMetrics: ['stockOh', 'stockValue'] },
}

interface PerformanceViewState {
  mode: Mode
  salesBasis: SalesBasis
  metric: Metric
  monthFrom: string
  monthTo: string
  dimension: Dimension
  dateFrom: string
  dateTo: string
  dateRanges: DateRange[]
  branchMonth: string
  branchPeriod: BranchPeriod
  branchIds: string[]
  skuIds: string[]
  page: number
  heatmap: boolean
  showDescriptions: boolean
  skuFlag: SkuFlagFilter
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
  dateRanges: [],
  branchMonth: 'latest',
  branchPeriod: 'month',
  branchIds: [],
  skuIds: [],
  page: 1,
  heatmap: true,
  showDescriptions: true,
  skuFlag: 'all',
}

const skuFlagFilters = new Set<SkuFlagFilter>(['all', 'flagged', 'sho', 'pro', 'both', 'none'])

const matchesSkuFlag = (item: PerformanceItem, filter: SkuFlagFilter) => {
  if (filter === 'flagged') return Boolean(item.isSho || item.isPro)
  if (filter === 'sho') return Boolean(item.isSho)
  if (filter === 'pro') return Boolean(item.isPro)
  if (filter === 'both') return Boolean(item.isSho && item.isPro)
  if (filter === 'none') return !item.isSho && !item.isPro
  return true
}

const loadPerformanceView = (mtCode: ModernTradeCode): PerformanceViewState => {
  try {
    const saved = window.localStorage.getItem(performanceViewStorageKey(mtCode))
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
    const dateFrom = parsed.dateFrom ?? legacyDate
    const dateTo = parsed.dateTo ?? legacyDate
    const dateRanges = Array.isArray(parsed.dateRanges)
      ? parsed.dateRanges.filter((range): range is DateRange => Boolean(range?.from && range?.to))
      : dateFrom && dateTo ? [{ from: dateFrom, to: dateTo }] : []
    const skuFlag = skuFlagFilters.has(parsed.skuFlag as SkuFlagFilter) ? parsed.skuFlag as SkuFlagFilter : 'all'
    return { ...defaultPerformanceView, ...parsed, dateFrom, dateTo, dateRanges, branchIds, skuFlag }
  } catch {
    return defaultPerformanceView
  }
}

const formatDateRange = (dates: string[]) => {
  if (dates.length === 0) return 'ไม่มีข้อมูล'
  return dates.length === 1 ? formatDisplayDate(dates[0]) : formatDisplayDate(dates[0]) + ' – ' + formatDisplayDate(dates.at(-1)!)
}

const formatSelectedRanges = (ranges: DateRange[], dates: string[]) => {
  if (ranges.length <= 1) return formatDateRange(dates)
  return `${ranges.length} ช่วง · ${formatDisplayDate(ranges[0].from)} – ${formatDisplayDate(ranges.at(-1)!.to)}`
}

const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}

interface PerformancePageProps {
  initialData?: PerformanceResponse
  mtCode?: ModernTradeCode
}

export function PerformancePage({ initialData, mtCode = 'TWD' }: PerformancePageProps) {
  const mt = modernTrades[mtCode]
  const [savedView] = useState(() => loadPerformanceView(mtCode))
  const [data, setData] = useState<PerformanceResponse | null>(initialData ?? null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(!initialData)
  const [mode, setMode] = useState<Mode>(savedView.mode)
  const [salesBasis, setSalesBasis] = useState<SalesBasis>(savedView.salesBasis)
  const [metric, setMetric] = useState<Metric>(savedView.metric)
  const [dimension, setDimension] = useState<Dimension>(savedView.dimension)
  const [dateFrom, setDateFrom] = useState(savedView.dateFrom)
  const [dateTo, setDateTo] = useState(savedView.dateTo)
  const [dateRanges, setDateRanges] = useState(savedView.dateRanges)
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
  const [skuFlag, setSkuFlag] = useState<SkuFlagFilter>(savedView.skuFlag)
  const [pendingSkuFlags, setPendingSkuFlags] = useState<Set<string>>(() => new Set())
  const [flagMessage, setFlagMessage] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
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
      dateRanges,
      branchMonth,
      branchPeriod,
      monthFrom,
      monthTo,
      branchIds,
      skuIds,
      page,
      heatmap,
      showDescriptions,
      skuFlag,
    }
    window.localStorage.setItem(performanceViewStorageKey(mtCode), JSON.stringify(currentView))
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateRanges, dateTo, dimension, heatmap, metric, mode, monthFrom, monthTo, mtCode, page, salesBasis, showDescriptions, skuFlag, skuIds])


  useEffect(() => {
    if (initialData) return
    const controller = new AbortController()
    fetchSkuOptions(mtCode, controller.signal)
      .then(setSkuOptions)
      .finally(() => { if (!controller.signal.aborted) setSkuOptionsLoading(false) })
    return () => controller.abort()
  }, [initialData, mtCode])

  useEffect(() => {
    if (initialData) return
    const controller = new AbortController()
    fetchPerformance({
      dateFrom,
      dateTo,
      dateRanges,
      branchIds,
      skuIds,
      search: '',
      page,
      monthFrom,
      monthTo,
      dimension,
      mode,
      salesBasis,
      mtCode,
      skuFlag,
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
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateRanges, dateTo, dimension, initialData, mode, monthFrom, monthTo, mtCode, page, reloadToken, salesBasis, skuFlag, skuIds])

  const needsDailyDetail = Boolean(
    selected
    && !initialData
    && dimension === 'branch'
    && (mode === 'inventory' || (mode === 'sales' && branchPeriod === 'day')),
  )
  const detailRequestKey = needsDailyDetail && selected
    ? [selected.sku, mode, salesBasis, JSON.stringify(dateRanges), branchIds.join(','), monthFrom, monthTo].join('|')
    : ''
  useEffect(() => {
    if (!selected?.sku || !detailRequestKey) return
    const controller = new AbortController()
    fetchPerformanceItemDetail({
      dateFrom,
      dateTo,
      dateRanges,
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
      mtCode,
      skuFlag,
    }, selected.sku, controller.signal)
      .then((item) => setDetailResult({ key: detailRequestKey, item, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setDetailResult({ key: detailRequestKey, item: null, error: error instanceof Error ? error.message : 'โหลดรายละเอียดรายวันไม่สำเร็จ' })
      })
    return () => controller.abort()
  }, [branchIds, branchMonth, branchPeriod, dateFrom, dateRanges, dateTo, detailRequestKey, dimension, mode, monthFrom, monthTo, mtCode, salesBasis, selected?.sku, skuFlag, skuIds])

  const patchSkuFlag = (sku: string, flag: SkuAnalysisFlagName, enabled: boolean) => {
    const property = flag === 'sho' ? 'isSho' : 'isPro'
    setData((current) => current ? {
      ...current,
      items: current.items.map((item) => item.sku === sku ? { ...item, [property]: enabled } : item),
    } : current)
    setDetailResult((current) => current?.item?.sku === sku ? {
      ...current,
      item: { ...current.item, [property]: enabled },
    } : current)
  }

  const patchSkuFlags = (sku: string, isSho: boolean, isPro: boolean) => {
    setData((current) => current ? {
      ...current,
      items: current.items.map((item) => item.sku === sku ? { ...item, isSho, isPro } : item),
    } : current)
    setDetailResult((current) => current?.item?.sku === sku ? {
      ...current,
      item: { ...current.item, isSho, isPro },
    } : current)
  }

  const handleSkuFlagChange = async (item: PerformanceItem, flag: SkuAnalysisFlagName, enabled: boolean) => {
    const key = `${item.sku}:${flag}`
    if (pendingSkuFlags.has(key)) return
    const previous = flag === 'sho' ? Boolean(item.isSho) : Boolean(item.isPro)
    setFlagMessage(null)
    setPendingSkuFlags((current) => new Set(current).add(key))
    patchSkuFlag(item.sku, flag, enabled)
    try {
      const saved = await updateSkuAnalysisFlag(mtCode, item.sku, flag, enabled)
      patchSkuFlags(item.sku, saved.isSho, saved.isPro)
      if (skuFlag !== 'all' && !initialData) {
        setPage(1)
        setIsLoading(true)
        setReloadToken((current) => current + 1)
      }
    } catch (error) {
      patchSkuFlag(item.sku, flag, previous)
      setFlagMessage(error instanceof Error ? error.message : `บันทึกสถานะ ${flag === 'sho' ? 'Sho' : 'Pro'} ไม่สำเร็จ`)
    } finally {
      setPendingSkuFlags((current) => {
        const next = new Set(current)
        next.delete(key)
        return next
      })
    }
  }

  const handleDownload = async () => {
    setIsDownloading(true)
    setDownloadMessage(null)
    try {
      const { blob, filename } = await downloadPerformanceReport({
        dateFrom,
        dateTo,
        dateRanges,
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
        mtCode,
        skuFlag,
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
      : dates.filter((value) => dateRanges.length === 0 || dateRanges.some((range) => value >= range.from && value <= range.to))
  ), [branchPeriod, dateRanges, dates, dimension, mode, monthFrom, monthTo, selectedBranchMonth])
  const visibleItems = useMemo(() => {
    if (!initialData) return performanceItems.filter((item) => matchesSkuFlag(item, skuFlag))
    return performanceItems.filter((item) => {
      const matchesSku = skuIds.length === 0 || skuIds.includes(item.sku)
      const hasData = item.points.some((point) => selectedDates.includes(point.date) && (branchIds.length === 0 || branchIds.includes(point.branchId)))
      return matchesSku && hasData && matchesSkuFlag(item, skuFlag)
    })
  }, [branchIds, initialData, performanceItems, selectedDates, skuFlag, skuIds])

  const allPoints = useMemo(
    () => visibleItems.flatMap((item) => pointsForView(item, selectedDates, branchIds, mode, 'branch')),
    [branchIds, mode, selectedDates, visibleItems],
  )
  const hasServerSummary = !initialData && data?.summary
  const totalAmount = hasServerSummary ? hasServerSummary.amount : sumMetric(allPoints, 'amount')
  const totalQty = hasServerSummary ? hasServerSummary.qty : sumMetric(allPoints, 'qty')
  const inventoryMetrics = data?.metricCapabilities?.inventory ?? mt.inventoryMetrics
  const selectedMetricTotal = mode === 'sales'
    ? data?.summary?.[metric as 'amount' | 'qty'] ?? sumMetric(allPoints, metric)
    : data?.inventorySummary?.[metric as 'stockOh' | 'stockOnOrder' | 'stockValue'] ?? sumMetric(allPoints, metric)
  const activeBranches = !initialData && data
    ? data.meta.totalBranches
    : new Set(allPoints.map((point) => point.branchId)).size
  const selectedItem = selected ? performanceItems.find((item) => item.sku === selected.sku) : undefined
  const currentDetail = detailResult?.key === detailRequestKey ? detailResult : null
  const detailLoading = Boolean(detailRequestKey && !currentDetail)
  const latestDataDate = availableDates.at(-1) ?? data?.latestImport?.dataDate ?? dates.at(-1)
  return (
    <>
      <div className="page-content" data-performance-source={mtCode}>
        <div className="page-intro">
          <div><span className="eyebrow">ข้อมูล Sales และ Inventory</span><h2>Matrix Performance ของ {mt.name}</h2><p>ติดตามแต่ละ Item ตาม Branch และวัน โดยยังเห็นรหัสจากต้นทางครบถ้วน</p></div>
          <div className="report-context" aria-label="บริบทข้อมูลรายงาน">
            <div className="data-freshness"><CalendarCheck2 size={17} aria-hidden="true" /><span>วันที่ข้อมูลล่าสุด</span><strong>{formatDisplayDate(latestDataDate, '—')}</strong></div>
            <div className="data-grain"><span>ระดับข้อมูล</span><strong>SKU × BRANCH × DAY</strong></div>
          </div>
        </div>

        <PerformanceToolbar
          mode={mode}
          salesBasis={salesBasis}
          metric={metric}
          dimension={dimension}
          dateRanges={dateRanges}
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
          skuFlag={skuFlag}
          branches={branches}
          availableDates={availableDates}
          months={months}
          inventoryMetrics={inventoryMetrics}
          sourceCode={mtCode}
          onModeChange={(value) => { setMode(value); setPage(1); setIsLoading(!initialData); setLoadError(null) }}
          onSalesBasisChange={(value) => { setSalesBasis(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onMetricChange={setMetric}
          onDimensionChange={(value) => { setDimension(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onDateRangeChange={(ranges) => {
            setDateRanges(ranges)
            setDateFrom(ranges[0]?.from ?? '')
            setDateTo(ranges.at(-1)?.to ?? '')
            setPage(1)
            setIsLoading(true)
            setLoadError(null)
          }}
          onBranchMonthChange={(value) => { setBranchMonth(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchPeriodChange={(value) => { setBranchPeriod(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onBranchChange={(value) => { setBranchIds(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onSkuChange={(value) => { setSkuIds(value); setPage(1); setIsLoading(true); setLoadError(null) }}
          onHeatmapChange={setHeatmap}
          onShowDescriptionsChange={setShowDescriptions}
          onSkuFlagChange={(value) => { setSkuFlag(value); setPage(1); setIsLoading(!initialData); setLoadError(null) }}
          onMonthRangeChange={(from, to) => { setMonthFrom(from); setMonthTo(to); setPage(1); setIsLoading(true); setLoadError(null) }}
        />

        {loadError && <div className="empty-state" role="alert"><strong>เชื่อมต่อ Backend ไม่สำเร็จ</strong><span>{loadError}</span></div>}

        <section className="kpi-ledger" aria-label="สรุป Performance">
          <article><span>Amount · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(totalAmount, 'amount')}</strong><small>{salesBasis === 'gross' ? 'เฉพาะยอดมากกว่า 0 ไม่รวม Return' : hasServerSummary ? 'ยอดสุทธิ รวม Return และ Adjustment' : 'ยอดสุทธิของข้อมูลที่แสดง'}</small></article>
          <article><span>Sales Qty · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(totalQty, 'qty')}</strong><small>{salesBasis === 'gross' ? 'เฉพาะจำนวนมากกว่า 0 ไม่รวม Return' : totalQty < 0 ? 'ยอด Return สุทธิ' : 'รวม Return และ Adjustment'}</small></article>
          <article><span>SKU ที่แสดง</span><strong>{visibleItems.length.toLocaleString('en-US')}</strong><small>จาก {(data?.meta.totalSkus ?? 0).toLocaleString('en-US')} SKU</small></article>
          <article><span>Branch ที่มียอด</span><strong>{activeBranches}</strong><small>จาก {data?.meta.totalBranches ?? 0} Branch ของ {mtCode}</small></article>
        </section>

        <div className="matrix-heading">
          <div><h3>{mode === 'sales' ? 'Sales' : 'Inventory'} ตาม {dimension === 'branch' ? 'Branch' : dimension === 'month' ? 'Month' : 'Date'}</h3><span>{metricLabel[metric]}{mode === 'sales' ? ` · ${salesBasis === 'gross' ? 'Gross Sale Out' : 'Net Sales'}` : ''} · {dimension === 'month' ? (monthFrom && monthTo ? `${formatMonth(monthFrom)} – ${formatMonth(monthTo)}` : 'ทุกเดือนที่มีข้อมูล') : mode === 'sales' && dimension === 'branch' && branchPeriod === 'month' && selectedBranchMonth ? formatMonth(selectedBranchMonth) : formatSelectedRanges(dateRanges, selectedDates)}</span></div>
          <div className="matrix-heading-tools">
            <div className="heat-legend" aria-label="คำอธิบาย Heatmap"><span>ต่ำ</span><i className="heat-low" /><i className="heat-medium" /><i className="heat-high" /><span>สูง</span>{mode !== 'sales' || salesBasis === 'net' ? <><i className="heat-negative" /><span>Return</span></> : null}</div>
            <div className="matrix-actions">
              <button type="button" disabled={isDownloading} onClick={() => void handleDownload()}><Download size={15} />{isDownloading ? 'กำลัง Download…' : 'Download Excel'}</button>
            </div>
          </div>
        </div>

        {downloadMessage && <div className={`exchange-message exchange-${downloadMessage.kind}`} role="status">{downloadMessage.text}</div>}
        {flagMessage && <div className="exchange-message exchange-error" role="alert"><strong>บันทึกสถานะ SKU ไม่สำเร็จ</strong> · {flagMessage}</div>}

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
          grandTotal={selectedMetricTotal}
          turnoverSummary={data?.inventorySummary}
          sourceCode={mtCode}
          selected={selected}
          onSelect={setSelected}
          pendingFlagKeys={pendingSkuFlags}
          onFlagChange={(item, flag, enabled) => { void handleSkuFlagChange(item, flag, enabled) }}
          onPageChange={(value) => { setPage(value); setIsLoading(true); setLoadError(null) }}
        />
      </div>

      {selected && selectedItem && (
        <ItemDetailDrawer item={currentDetail?.item ?? selectedItem} selected={selected} dates={selectedDates} branchIds={branchIds} metric={metric} salesBasis={salesBasis} branches={branches} isLoading={detailLoading} loadError={currentDetail?.error} sourceCode={mtCode} inventoryMetrics={inventoryMetrics} onClose={() => setSelected(null)} />
      )}
    </>
  )
}
