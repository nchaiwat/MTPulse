import { useEffect } from 'react'
import { CircleAlert, CircleCheck, X } from 'lucide-react'
import { formatMetric, sumMetric } from './performanceMath'
import type { Branch, Metric, PerformanceItem, SelectedCell } from './types'

interface ItemDetailDrawerProps {
  item: PerformanceItem
  selected: SelectedCell
  dates: string[]
  branchId: string
  metric: Metric
  branches: Branch[]
  onClose: () => void
}

const formatDate = (date: string) => {
  if (/^\d{4}-\d{2}$/.test(date)) {
    const [year, month] = date.split('-').map(Number)
    return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1))
  }
  return new Intl.DateTimeFormat('th-TH-u-ca-gregory', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${date}T00:00:00`))
}

export function ItemDetailDrawer({ item, selected, dates, branchId, metric, branches, onClose }: ItemDetailDrawerProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  const points = item.points
    .filter((point) => dates.includes(point.date) && (branchId === 'all' || point.branchId === branchId))
    .sort((a, b) => b.date.localeCompare(a.date) || a.branchId.localeCompare(b.branchId))
  const focusLabel = selected.dimensionKey
    ? branches.find((branch) => branch.id === selected.dimensionKey)?.name ?? formatDate(selected.dimensionKey)
    : 'ข้อมูลที่เลือกทั้งหมด'

  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header className="drawer-header">
          <div><span className="eyebrow">รายละเอียด Item / {focusLabel}</span><h2 id="drawer-title">{item.sku}</h2><p>{item.twdDescription}</p></div>
          <button className="icon-button" type="button" aria-label="ปิดรายละเอียด Item" onClick={onClose}><X size={19} /></button>
        </header>

        <div className="drawer-identities">
          <div><span>WA Item</span><strong className="mono">{item.waItem ?? 'ยังไม่ Mapping'}</strong><small>{item.waDescription ?? 'เลือก Item ของ Window Asia ก่อนยืนยัน Mapping'}</small></div>
          <span className={`status status-${item.mappingStatus}`}><span aria-hidden="true" />{item.mappingStatus === 'confirmed' ? 'ยืนยันแล้ว' : item.mappingStatus === 'pending' ? 'รอตรวจสอบ' : 'ยังไม่ Mapping'}</span>
        </div>

        <section className="drawer-kpis" aria-label="ยอดรวม Item">
          <div><span>Amount</span><strong>{formatMetric(sumMetric(points, 'amount'), 'amount')}</strong></div>
          <div><span>Sales Qty</span><strong>{formatMetric(sumMetric(points, 'qty'), 'qty')}</strong></div>
          <div><span>Stock OH ล่าสุด</span><strong>{formatMetric(sumMetric(points.filter((point) => point.date === dates.at(-1)), 'stockOh'), 'stockOh')}</strong></div>
          <div><span>Stock On Order</span><strong>{formatMetric(sumMetric(points.filter((point) => point.date === dates.at(-1)), 'stockOnOrder'), 'stockOnOrder')}</strong></div>
        </section>

        {item.mappingStatus === 'confirmed' ? (
          <section className="mapping-note mapping-confirmed"><CircleCheck size={18} aria-hidden="true" /><div><strong>Mapping มีผลใช้งานแล้ว</strong><span>มีผลตั้งแต่ 20 ส.ค. 2026 · ดูประวัติได้ในหน้า Mapping</span></div></section>
        ) : (
          <section className="mapping-note mapping-attention"><CircleAlert size={18} aria-hidden="true" /><div><strong>{item.mappingStatus === 'pending' ? 'Candidate รอการยืนยัน' : 'ไม่พบ Mapping Candidate'}</strong><span>การแก้ Mapping จะเปิดใช้งานหลังเชื่อม Backend Workflow</span></div></section>
        )}

        <section className="daily-breakdown">
          <div className="section-heading"><div><span className="eyebrow">SKU × Branch × Day</span><h3>รายละเอียดรายวัน</h3></div><span>Metric ที่เลือก: {metric === 'amount' ? 'Amount' : metric}</span></div>
          <div className="drawer-table-wrap">
            <table>
              <thead><tr><th>วันที่</th><th>Branch</th><th className="numeric-column">Qty</th><th className="numeric-column">Amount</th><th className="numeric-column">Stock OH</th><th className="numeric-column">On Order</th></tr></thead>
              <tbody>
                {points.map((point) => {
                  const branch = branches.find((entry) => entry.id === point.branchId)
                  return <tr key={`${point.date}-${point.branchId}`}><td>{formatDate(point.date)}</td><td><strong className="mono">{point.branchId}</strong><small>{branch?.name}</small></td><td className={`numeric-column ${point.qty < 0 ? 'is-negative' : ''}`}>{formatMetric(point.qty, 'qty')}</td><td className={`numeric-column ${point.amount < 0 ? 'is-negative' : ''}`}>{formatMetric(point.amount, 'amount')}</td><td className="numeric-column">{formatMetric(point.stockOh, 'stockOh')}</td><td className="numeric-column">{formatMetric(point.stockOnOrder, 'stockOnOrder')}</td></tr>
                })}
              </tbody>
            </table>
          </div>
        </section>
      </aside>
    </div>
  )
}
