import { memo, useLayoutEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { aggregateByDimension, formatMetric, heatLevel, monthKeys, pointsForView, sumMetric } from './performanceMath'
import type { Branch, Dimension, Metric, Mode, PerformanceItem, SelectedCell } from './types'

interface PerformanceMatrixProps {
  items: PerformanceItem[] | null
  branches: Branch[]
  totalSkus: number
  page: number
  totalPages: number
  isLoading: boolean
  dates: string[]
  branchId: string
  mode: Mode
  metric: Metric
  dimension: Dimension
  heatmap: boolean
  showDescriptions: boolean
  columnTotals?: Record<string, { amount: number, qty: number }>
  grandTotal?: number
  selected: SelectedCell | null
  onSelect: (selected: SelectedCell) => void
  onPageChange: (page: number) => void
}

const shortDate = (date: string) => new Intl.DateTimeFormat('th-TH-u-ca-gregory', { day: '2-digit', month: 'short' }).format(new Date(`${date}T00:00:00`))
const shortMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}

type MatrixTableProps = Omit<PerformanceMatrixProps, 'items' | 'totalSkus' | 'page' | 'totalPages' | 'isLoading' | 'onPageChange'> & {
  items: PerformanceItem[]
}

const MatrixTable = memo(function MatrixTable({ items, branches, dates, branchId, mode, metric, dimension, heatmap, showDescriptions, columnTotals, grandTotal, selected, onSelect }: MatrixTableProps) {
  const topScrollRef = useRef<HTMLDivElement>(null)
  const matrixScrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const topSpacerRef = useRef<HTMLDivElement>(null)
  const dimensionKeys = dimension === 'branch'
    ? branches.filter((branch) => branchId === 'all' || branch.id === branchId).map((branch) => branch.id)
    : dimension === 'month'
      ? monthKeys(dates)
      : dates

  const rows = items.map((item) => {
    const points = pointsForView(item, dates, branchId, mode, dimension)
    return { item, values: aggregateByDimension(points, dimension, metric), total: sumMetric(points, metric) }
  })
  const maxValue = Math.max(0, ...rows.flatMap((row) => dimensionKeys.map((key) => row.values[key] ?? 0)))
  const salesMetric = metric === 'amount' || metric === 'qty' ? metric : null
  const summaryValue = (key: string) => salesMetric && columnTotals?.[key]
    ? columnTotals[key][salesMetric]
    : rows.reduce((total, row) => total + (row.values[key] ?? 0), 0)
  const summaryTotal = grandTotal ?? rows.reduce((total, row) => total + row.total, 0)
  const showSummary = mode === 'sales' && (dimension === 'branch' || dimension === 'month')

  useLayoutEffect(() => {
    const table = tableRef.current
    const spacer = topSpacerRef.current
    if (!table || !spacer) return

    const syncWidth = () => { spacer.style.width = `${table.scrollWidth}px` }
    syncWidth()

    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(syncWidth)
    observer.observe(table)
    return () => observer.disconnect()
  }, [dimensionKeys.length, showDescriptions])

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
      <table ref={tableRef} className={`performance-matrix ${showDescriptions ? '' : 'descriptions-hidden'} ${showSummary ? 'has-summary' : ''}`}>
        <caption className="sr-only">Performance ของ TWD ตาม {dimension === 'branch' ? 'Branch' : dimension === 'month' ? 'Month' : 'Date'}</caption>
        <thead>
          {showSummary && (
            <tr className="matrix-summary-row">
              <th className="sticky-column col-sku">SUM</th>
              {showDescriptions && <th className="sticky-column col-twd-desc" />}
              <th className="sticky-column col-wa-item" />
              {showDescriptions && <th className="sticky-column col-wa-desc sticky-divider" />}
              <th className={`numeric-column total-column ${summaryTotal < 0 ? 'is-negative' : ''}`}>{formatMetric(summaryTotal, metric)}</th>
              {dimensionKeys.map((key) => {
                const value = summaryValue(key)
                return <th className={`numeric-column dimension-header ${value < 0 ? 'is-negative' : ''}`} key={key}>{formatMetric(value, metric)}</th>
              })}
            </tr>
          )}
          <tr className="matrix-label-row">
            <th className="sticky-column col-sku">TWD SKU</th>
            {showDescriptions && <th className="sticky-column col-twd-desc">TWD description</th>}
            <th className="sticky-column col-wa-item">WA item</th>
            {showDescriptions && <th className="sticky-column col-wa-desc sticky-divider">WA description</th>}
            <th className="numeric-column total-column">Total</th>
            {dimensionKeys.map((key) => {
              const branch = branches.find((entry) => entry.id === key)
              return <th className="numeric-column dimension-header" key={key}><span>{branch ? branch.id : dimension === 'month' ? shortMonth(key) : shortDate(key)}</span>{branch && <small>{branch.name}</small>}</th>
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ item, values, total }) => (
            <tr data-selected={selected?.sku === item.sku || undefined} data-mapping-status={item.mappingStatus} key={item.sku}>
              <td className="sticky-column col-sku"><button className={`item-link ${item.mappingStatus === 'unmatched' ? 'item-link-unmatched' : ''}`} type="button" onClick={() => onSelect({ sku: item.sku })}>{item.sku}</button></td>
              {showDescriptions && <td className="sticky-column col-twd-desc"><span className="truncate" title={item.twdDescription}>{item.twdDescription}</span></td>}
              <td className={`sticky-column col-wa-item mono ${showDescriptions ? '' : 'sticky-divider'}`}>{item.waItem ?? '—'}</td>
              {showDescriptions && <td className="sticky-column col-wa-desc sticky-divider"><span className="truncate" title={item.waDescription ?? 'ยังไม่ Mapping'}>{item.waDescription ?? 'ยังไม่ได้เลือก Mapping'}</span></td>}
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

export function PerformanceMatrix({ items, branches, totalSkus, page, totalPages, isLoading, dates, branchId, mode, metric, dimension, heatmap, showDescriptions, columnTotals, grandTotal, selected, onSelect, onPageChange }: PerformanceMatrixProps) {
  if (items === null) {
    return <div className="matrix-skeleton" aria-label="กำลังโหลดข้อมูล Performance" aria-busy="true">{Array.from({ length: 7 }, (_, index) => <span key={index} />)}</div>
  }

  if (items.length === 0) {
    return <div className="empty-state"><strong>ไม่พบ Item ตามตัวกรอง</strong><span>เปลี่ยนหรือล้างตัวกรองด้านบนแล้วลองอีกครั้ง</span></div>
  }

  return (
    <div className="matrix-frame" data-loading={isLoading || undefined} aria-busy={isLoading}>
      <MatrixTable items={items} branches={branches} dates={dates} branchId={branchId} mode={mode} metric={metric} dimension={dimension} heatmap={heatmap} showDescriptions={showDescriptions} columnTotals={columnTotals} grandTotal={grandTotal} selected={selected} onSelect={onSelect} />
      <footer className="matrix-footer">
        <span>แสดง {items.length.toLocaleString('en-US')} จาก {totalSkus.toLocaleString('en-US')} SKU</span>
        <span className="loading-copy" role="status" aria-live="polite">{isLoading ? 'กำลังโหลดข้อมูล…' : 'พร้อมใช้งาน'}</span>
        <PaginationControls key={page} page={page} totalPages={totalPages} isLoading={isLoading} onPageChange={onPageChange} />
      </footer>
    </div>
  )
}
