import { useEffect } from 'react'
import { CircleAlert, CircleCheck, LoaderCircle, X } from 'lucide-react'
import { formatMetric, metricLabel, sumMetric } from './performanceMath'
import type { Branch, Metric, PerformanceItem, SalesBasis, SelectedCell } from './types'
import { formatDisplayDate } from '../../shared/dateFormat'

interface ItemDetailDrawerProps {
  item: PerformanceItem
  selected: SelectedCell
  dates: string[]
  branchIds: string[]
  metric: Metric
  salesBasis: SalesBasis
  branches: Branch[]
  isLoading?: boolean
  loadError?: string | null
  onClose: () => void
  sourceCode?: string
  inventoryMetrics?: Metric[]
}

const formatDimension = (date: string) => {
  if (/^\d{4}-\d{2}$/.test(date)) {
    const [year, month] = date.split('-').map(Number)
    return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1))
  }
  return formatDisplayDate(date)
}

export function ItemDetailDrawer({ item, selected, dates, branchIds, metric, salesBasis, branches, isLoading = false, loadError = null, onClose, sourceCode = 'TWD', inventoryMetrics = ['stockOh', 'stockOnOrder'] }: ItemDetailDrawerProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  const points = item.points
    .filter((point) => dates.includes(point.date) && (branchIds.length === 0 || point.branchId === 'all' || branchIds.includes(point.branchId)))
    .sort((a, b) => b.date.localeCompare(a.date) || a.branchId.localeCompare(b.branchId))
  const focusBranch = branches.find((branch) => branch.id === selected.dimensionKey)
  const focusLabel = selected.dimensionKey
    ? focusBranch
      ? `${focusBranch.id} - ${focusBranch.name}`
      : formatDimension(selected.dimensionKey)
    : 'ข้อมูลที่เลือกทั้งหมด'
  const secondaryInventoryMetric: Metric = inventoryMetrics.includes('stockValue') ? 'stockValue' : 'stockOnOrder'

  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header className="drawer-header">
          <div><span className="eyebrow">รายละเอียด Item {sourceCode} / {focusLabel} / {salesBasis === 'gross' ? 'Gross Sale Out' : 'Net Sales'}</span><h2 id="drawer-title">{item.sku}</h2><p>{item.twdDescription}</p></div>
          <button className="icon-button" type="button" aria-label="ปิดรายละเอียด Item" onClick={onClose}><X size={19} /></button>
        </header>

        <div className="drawer-identities">
          <div><span>WA Item</span><strong className="mono">{item.waItem ?? 'ยังไม่ Mapping'}</strong><small>{item.waDescription ?? 'เลือก Item ของ Window Asia ก่อนยืนยัน Mapping'}</small><div className="sku-flag-badges" aria-label="สถานะความสนใจ SKU"><span className="sku-flag-badge flag-sho" data-active={item.isSho || undefined}>Sho</span><span className="sku-flag-badge flag-pro" data-active={item.isPro || undefined}>Pro</span></div></div>
          <span className={`status status-${item.mappingStatus}`}><span aria-hidden="true" />{item.mappingStatus === 'confirmed' ? 'ยืนยันแล้ว' : item.mappingStatus === 'pending' ? 'รอตรวจสอบ' : 'ยังไม่ Mapping'}</span>
        </div>

        <section className="drawer-kpis" aria-label="ยอดรวม Item">
          <div><span>Amount · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(sumMetric(points, 'amount'), 'amount')}</strong></div>
          <div><span>Sales Qty · {salesBasis === 'gross' ? 'Gross' : 'Net'}</span><strong>{formatMetric(sumMetric(points, 'qty'), 'qty')}</strong></div>
          <div><span>Stock OH ล่าสุด</span><strong>{formatMetric(sumMetric(points.filter((point) => point.date === dates.at(-1)), 'stockOh'), 'stockOh')}</strong></div>
          <div><span>{metricLabel[secondaryInventoryMetric]}</span><strong>{formatMetric(sumMetric(points.filter((point) => point.date === dates.at(-1)), secondaryInventoryMetric), secondaryInventoryMetric)}</strong></div>
        </section>

        {item.mappingStatus === 'confirmed' ? (
          <section className="mapping-note mapping-confirmed"><CircleCheck size={18} aria-hidden="true" /><div><strong>Mapping มีผลใช้งานแล้ว</strong><span>มีผลตั้งแต่ 20/08/2026 · ดูประวัติได้ในหน้า Mapping</span></div></section>
        ) : (
          <section className="mapping-note mapping-attention"><CircleAlert size={18} aria-hidden="true" /><div><strong>{item.mappingStatus === 'pending' ? 'Candidate รอการยืนยัน' : 'ไม่พบ Mapping Candidate'}</strong><span>การแก้ Mapping จะเปิดใช้งานหลังเชื่อม Backend Workflow</span></div></section>
        )}

        <section className="daily-breakdown">
          <div className="section-heading"><div><span className="eyebrow">SKU × Branch × Day</span><h3>รายละเอียดรายวัน</h3></div><span>Metric ที่เลือก: {metricLabel[metric]}</span></div>
          {isLoading ? <div className="drawer-detail-loading" role="status"><LoaderCircle className="matrix-loading-spinner" size={22} aria-hidden="true" />กำลังโหลดรายละเอียดรายวัน…</div> : loadError ? <div className="drawer-detail-error" role="alert">{loadError}</div> : <div className="drawer-table-wrap">
            <table>
              <thead><tr><th>วันที่</th><th>Branch</th><th className="numeric-column">Qty</th><th className="numeric-column">Amount</th><th className="numeric-column">Stock OH</th><th className="numeric-column">{metricLabel[secondaryInventoryMetric]}</th></tr></thead>
              <tbody>
                {points.map((point) => {
                  const branch = branches.find((entry) => entry.id === point.branchId)
                  return <tr key={`${point.date}-${point.branchId}`}><td>{formatDisplayDate(point.date)}</td><td className="branch-inline"><strong className="mono">{point.branchId}</strong>{branch && <span> - {branch.name}</span>}</td><td className={`numeric-column ${point.qty < 0 ? 'is-negative' : ''}`}>{formatMetric(point.qty, 'qty')}</td><td className={`numeric-column ${point.amount < 0 ? 'is-negative' : ''}`}>{formatMetric(point.amount, 'amount')}</td><td className="numeric-column">{formatMetric(point.stockOh, 'stockOh')}</td><td className="numeric-column">{formatMetric(point[secondaryInventoryMetric] ?? 0, secondaryInventoryMetric)}</td></tr>
                })}
              </tbody>
            </table>
          </div>}
        </section>
      </aside>
    </div>
  )
}
