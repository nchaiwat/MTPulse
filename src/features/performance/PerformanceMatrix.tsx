import { memo, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, LoaderCircle } from 'lucide-react'
import { aggregateByDimension, formatMetric, heatLevel, monthKeys, pointsForView, sumMetric } from './performanceMath'
import type { Branch, Dimension, Metric, Mode, PerformanceItem, PerformanceResponse, SelectedCell, SkuAnalysisFlagName } from './types'
import { formatDisplayDate } from '../../shared/dateFormat'
import { matrixScrollContentWidth } from './matrixScroll'

interface PerformanceMatrixProps {
  items: PerformanceItem[] | null
  branches: Branch[]
  totalSkus: number
  page: number
  totalPages: number
  isLoading: boolean
  dates: string[]
  branchIds: string[]
  mode: Mode
  metric: Metric
  dimension: Dimension
  heatmap: boolean
  showDescriptions: boolean
  columnTotals?: Record<string, { amount: number, qty: number }>
  grandTotal?: number
  turnoverSummary?: PerformanceResponse['inventorySummary']
  selected: SelectedCell | null
  onSelect: (selected: SelectedCell) => void
  onPageChange: (page: number) => void
  pendingFlagKeys: Set<string>
  onFlagChange: (item: PerformanceItem, flag: SkuAnalysisFlagName, enabled: boolean) => void
  sourceCode?: string
}

const shortMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}

type MatrixTableProps = Omit<PerformanceMatrixProps, 'items' | 'totalSkus' | 'page' | 'totalPages' | 'isLoading' | 'onPageChange'> & {
  items: PerformanceItem[]
}

const turnoverFormatter = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const formatTurnover = (value: number | null | undefined) => value == null ? '—' : turnoverFormatter.format(value)

const skuFlagState = (item: PerformanceItem) => item.isSho && item.isPro
  ? 'both'
  : item.isSho
    ? 'sho'
    : item.isPro
      ? 'pro'
      : undefined

const MatrixTable = memo(function MatrixTable({ items, branches, dates, branchIds, mode, metric, dimension, heatmap, showDescriptions, columnTotals, grandTotal, turnoverSummary, selected, onSelect, pendingFlagKeys, onFlagChange, sourceCode = 'TWD' }: MatrixTableProps) {
  const topScrollRef = useRef<HTMLDivElement>(null)
  const matrixScrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const topSpacerRef = useRef<HTMLDivElement>(null)
  const dimensionKeys = useMemo(() => dimension === 'branch'
    ? branches.filter((branch) => branchIds.length === 0 || branchIds.includes(branch.id)).map((branch) => branch.id)
    : dimension === 'month'
      ? monthKeys(dates)
      : dates, [branchIds, branches, dates, dimension])

  const rows = useMemo(() => items.map((item) => {
    const points = pointsForView(item, dates, branchIds, mode, dimension)
    return { item, values: aggregateByDimension(points, dimension, metric), total: sumMetric(points, metric) }
  }), [branchIds, dates, dimension, items, metric, mode])
  const maxValue = useMemo(
    () => Math.max(0, ...rows.flatMap((row) => dimensionKeys.map((key) => row.values[key] ?? 0))),
    [dimensionKeys, rows],
  )
  const salesMetric = metric === 'amount' || metric === 'qty' ? metric : null
  const summaryValue = (key: string) => salesMetric && columnTotals?.[key]
    ? columnTotals[key][salesMetric]
    : rows.reduce((total, row) => total + (row.values[key] ?? 0), 0)
  const summaryTotal = grandTotal ?? rows.reduce((total, row) => total + row.total, 0)
  const showTurnover = mode === 'inventory' && sourceCode === 'TWD'
  const showFlags = sourceCode === 'TWD'
  const showSummary = mode === 'sales' || showTurnover

  useLayoutEffect(() => {
    const table = tableRef.current
    const spacer = topSpacerRef.current
    if (!table || !spacer) return

    const syncWidth = () => {
      const matrixScroll = matrixScrollRef.current
      spacer.style.width = `${matrixScrollContentWidth(table.scrollWidth, matrixScroll?.offsetWidth ?? 0, matrixScroll?.clientWidth ?? 0)}px`
    }
    syncWidth()

    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(syncWidth)
    observer.observe(table)
    if (matrixScrollRef.current) observer.observe(matrixScrollRef.current)
    return () => observer.disconnect()
  }, [dimensionKeys.length, showFlags, showTurnover])

  const matrixBody = useMemo(() => (
    <tbody>
      {rows.map(({ item, values, total }) => (
        <tr data-selected={selected?.sku === item.sku || undefined} data-sku-flag={skuFlagState(item)} data-mapping-status={item.mappingStatus} data-item-type={item.itemType ?? 'normal'} key={item.sku}>
          {showFlags && (
            <td className="sticky-column sku-flag-cell col-sho">
              <label className="sku-flag-check sku-flag-sho" data-pending={pendingFlagKeys.has(`${item.sku}:sho`) || undefined} title="สินค้าตัวโชว์">
                <input type="checkbox" aria-label={`Sho ${sourceCode} SKU ${item.sku}`} checked={Boolean(item.isSho)} disabled={pendingFlagKeys.has(`${item.sku}:sho`)} onChange={(event) => onFlagChange(item, 'sho', event.target.checked)} />
              </label>
            </td>
          )}
          {showFlags && (
            <td className="sticky-column sku-flag-cell col-pro">
              <label className="sku-flag-check sku-flag-pro" data-pending={pendingFlagKeys.has(`${item.sku}:pro`) || undefined} title="สินค้าทำ Promotion">
                <input type="checkbox" aria-label={`Pro ${sourceCode} SKU ${item.sku}`} checked={Boolean(item.isPro)} disabled={pendingFlagKeys.has(`${item.sku}:pro`)} onChange={(event) => onFlagChange(item, 'pro', event.target.checked)} />
              </label>
            </td>
          )}
          <td className="sticky-column col-sku"><span className="item-link-wrap"><button className={`item-link ${item.mappingStatus === 'unmatched' ? 'item-link-unmatched' : ''}`} type="button" onClick={() => onSelect({ sku: item.sku })}>{item.sku}</button>{item.itemType === 'trial' && <span className="trial-row-badge">สินค้าทดลอง</span>}</span></td>
          <td className="sticky-column col-twd-desc"><span className="truncate" title={item.twdDescription}>{item.twdDescription}</span></td>
          <td className="sticky-column col-wa-item mono">{item.waItem ?? '—'}</td>
          <td className={`sticky-column col-wa-desc ${showTurnover ? '' : 'sticky-divider'}`}><span className="truncate" title={item.waDescription ?? 'ยังไม่ Mapping'}>{item.waDescription ?? 'ยังไม่ได้เลือก Mapping'}</span></td>
          {showTurnover && <td className="sticky-column col-tom numeric-column turnover-column">{formatTurnover(item.tom)}</td>}
          {showTurnover && <td className="sticky-column col-tod numeric-column turnover-column sticky-divider">{formatTurnover(item.tod)}</td>}
          <td className={`numeric-column total-column ${total < 0 ? 'is-negative' : ''}`}><strong>{formatMetric(total, metric)}</strong></td>
          {dimensionKeys.map((key) => {
            const value = values[key] ?? 0
            const level = heatmap ? heatLevel(value, maxValue) : 'off'
            return (
              <td className={`numeric-column heat-${level}`} key={key}>
                {value === 0
                  ? <span aria-hidden="true">—</span>
                  : <button type="button" className={value < 0 ? 'is-negative' : ''} aria-label={`เปิด ${item.sku}, ${key}, ${formatMetric(value, metric)}`} onClick={() => onSelect({ sku: item.sku, dimensionKey: key })}>{formatMetric(value, metric)}</button>}
              </td>
            )
          })}
        </tr>
      ))}
    </tbody>
  ), [dimensionKeys, heatmap, maxValue, metric, onFlagChange, onSelect, pendingFlagKeys, rows, selected, showFlags, showTurnover, sourceCode])

  return (
    <>
      <div
        className="matrix-top-scroll"
        ref={topScrollRef}
        role="region"
        aria-label="เลื่อนตารางแนวนอนด้านบน"
        tabIndex={0}
        onScroll={(event) => { if (matrixScrollRef.current) matrixScrollRef.current.scrollLeft = event.currentTarget.scrollLeft }}
      >
        <div className="matrix-top-scroll-spacer" ref={topSpacerRef} />
      </div>
      <div
        className="matrix-scroll"
        ref={matrixScrollRef}
        onScroll={(event) => { if (topScrollRef.current) topScrollRef.current.scrollLeft = event.currentTarget.scrollLeft }}
      >
      <table ref={tableRef} className={`performance-matrix ${showDescriptions ? '' : 'descriptions-hidden'} ${showSummary ? 'has-summary' : ''} ${showTurnover ? 'has-turnover' : ''} ${showFlags ? 'has-sku-flags' : ''}`}>
        <caption className="sr-only">Performance ของ {sourceCode} ตาม {dimension === 'branch' ? 'Branch' : dimension === 'month' ? 'Month' : 'Date'}</caption>
        <thead>
          {showSummary && (
            <tr className="matrix-summary-row">
              {showFlags && <th className="sticky-column col-sho" />}
              {showFlags && <th className="sticky-column col-pro" />}
              <th className="sticky-column col-sku">{mode === 'sales' ? 'SUM' : 'AVG'}</th>
              {showDescriptions && <th className="sticky-column col-twd-desc" />}
              <th className="sticky-column col-wa-item" />
              {showDescriptions && <th className={`sticky-column col-wa-desc ${showTurnover ? '' : 'sticky-divider'}`} />}
              {showTurnover && <th className="sticky-column col-tom numeric-column">AVG {formatTurnover(turnoverSummary?.averageTom)}</th>}
              {showTurnover && <th className="sticky-column col-tod numeric-column sticky-divider">AVG {formatTurnover(turnoverSummary?.averageTod)}</th>}
              <th className={`numeric-column total-column ${mode === 'sales' && summaryTotal < 0 ? 'is-negative' : ''}`}>{mode === 'sales' ? formatMetric(summaryTotal, metric) : ''}</th>
              {dimensionKeys.map((key) => {
                const value = summaryValue(key)
                return <th className={`numeric-column dimension-header ${mode === 'sales' && value < 0 ? 'is-negative' : ''}`} key={key}>{mode === 'sales' ? formatMetric(value, metric) : ''}</th>
              })}
            </tr>
          )}
          <tr className="matrix-label-row">
            {showFlags && <th className="sticky-column sku-flag-heading col-sho"><abbr title="สินค้าตัวโชว์">Sho</abbr></th>}
            {showFlags && <th className="sticky-column sku-flag-heading col-pro"><abbr title="สินค้าทำ Promotion">Pro</abbr></th>}
            <th className="sticky-column col-sku">{sourceCode} SKU</th>
            {showDescriptions && <th className="sticky-column col-twd-desc">{sourceCode} description</th>}
            <th className="sticky-column col-wa-item">WA item</th>
            {showDescriptions && <th className={`sticky-column col-wa-desc ${showTurnover ? '' : 'sticky-divider'}`}>WA description</th>}
            {showTurnover && <th className="sticky-column col-tom numeric-column"><abbr title="Turn Over Month">TOM</abbr></th>}
            {showTurnover && <th className="sticky-column col-tod numeric-column sticky-divider"><abbr title="Turn Over Day">TOD</abbr></th>}
            <th className="numeric-column total-column">Total</th>
            {dimensionKeys.map((key) => {
              const branch = branches.find((entry) => entry.id === key)
              return (
                <th className="numeric-column dimension-header" key={key}>
                  {branch
                    ? <><span className="branch-header-code">{branch.id}</span><small className="branch-header-name">{branch.name}</small></>
                    : <span>{dimension === 'month' ? shortMonth(key) : formatDisplayDate(key)}</span>}
                </th>
              )
            })}
          </tr>
        </thead>
        {matrixBody}
      </table>
      </div>
    </>
  )
})

function PaginationControls({ page, totalPages, isLoading, onPageChange }: Pick<PerformanceMatrixProps, 'page' | 'totalPages' | 'isLoading' | 'onPageChange'>) {
  const [pageInput, setPageInput] = useState(String(page))

  const goToInputPage = () => {
    const requestedPage = Number.parseInt(pageInput, 10)
    if (!Number.isFinite(requestedPage)) {
      setPageInput(String(page))
      return
    }
    const nextPage = Math.min(totalPages, Math.max(1, requestedPage))
    setPageInput(String(nextPage))
    if (nextPage !== page) onPageChange(nextPage)
  }

  return (
    <form className="pagination-controls" onSubmit={(event) => { event.preventDefault(); goToInputPage() }}>
      <button type="button" aria-label="ไปหน้าแรก" title="หน้าแรก" disabled={isLoading || page <= 1} onClick={() => onPageChange(1)}><ChevronsLeft size={16} /></button>
      <button type="button" aria-label="หน้าก่อนหน้า" title="หน้าก่อนหน้า" disabled={isLoading || page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft size={16} /></button>
      <label className="page-jump">
        <span>หน้า</span>
        <input aria-label="เลขหน้าที่ต้องการ" type="number" inputMode="numeric" min="1" max={totalPages} value={pageInput} disabled={isLoading} onChange={(event) => setPageInput(event.target.value)} />
        <span>จาก {totalPages.toLocaleString('en-US')}</span>
      </label>
      <button className="page-go" type="submit" disabled={isLoading}>ไป</button>
      <button type="button" aria-label="หน้าถัดไป" title="หน้าถัดไป" disabled={isLoading || page >= totalPages} onClick={() => onPageChange(page + 1)}><ChevronRight size={16} /></button>
      <button type="button" aria-label="ไปหน้าสุดท้าย" title="หน้าสุดท้าย" disabled={isLoading || page >= totalPages} onClick={() => onPageChange(totalPages)}><ChevronsRight size={16} /></button>
    </form>
  )
}

export function PerformanceMatrix({ items, branches, totalSkus, page, totalPages, isLoading, dates, branchIds, mode, metric, dimension, heatmap, showDescriptions, columnTotals, grandTotal, turnoverSummary, selected, onSelect, onPageChange, pendingFlagKeys, onFlagChange, sourceCode = 'TWD' }: PerformanceMatrixProps) {
  if (items === null) {
    return <div className="matrix-skeleton" aria-busy="true">{Array.from({ length: 7 }, (_, index) => <span key={index} />)}<div className="matrix-loading-state" role="status" aria-label="กำลังโหลดข้อมูล Performance"><LoaderCircle className="matrix-loading-spinner" size={28} aria-hidden="true" /><strong>กำลังโหลดข้อมูล…</strong></div></div>
  }

  if (items.length === 0) {
    return <div className="empty-state"><strong>ไม่พบ Item ตามตัวกรอง</strong><span>เปลี่ยนหรือล้างตัวกรองด้านบนแล้วลองอีกครั้ง</span></div>
  }

  return (
    <div className="matrix-frame" data-loading={isLoading || undefined} aria-busy={isLoading}>
      {isLoading && <div className="matrix-loading-overlay" role="status" aria-label="กำลังโหลดข้อมูล Performance"><div className="matrix-loading-state"><LoaderCircle className="matrix-loading-spinner" size={28} aria-hidden="true" /><strong>กำลังโหลดข้อมูล…</strong><span>กำลังเตรียมข้อมูลตามตัวกรอง</span></div></div>}
      <MatrixTable items={items} branches={branches} dates={dates} branchIds={branchIds} mode={mode} metric={metric} dimension={dimension} heatmap={heatmap} showDescriptions={showDescriptions} columnTotals={columnTotals} grandTotal={grandTotal} turnoverSummary={turnoverSummary} selected={selected} onSelect={onSelect} pendingFlagKeys={pendingFlagKeys} onFlagChange={onFlagChange} sourceCode={sourceCode} />
      <footer className="matrix-footer">
        <span>แสดง {items.length.toLocaleString('en-US')} จาก {totalSkus.toLocaleString('en-US')} SKU</span>
        <span className="loading-copy" role="status" aria-live="polite">{isLoading ? 'กำลังโหลดข้อมูล…' : 'พร้อมใช้งาน'}</span>
        <PaginationControls key={page} page={page} totalPages={totalPages} isLoading={isLoading} onPageChange={onPageChange} />
      </footer>
    </div>
  )
}
