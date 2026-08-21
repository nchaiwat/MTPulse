import { CalendarDays, Eye, EyeOff, Search, SlidersHorizontal } from 'lucide-react'
import type { Branch, Dimension, MappingStatus, Metric, Mode } from './types'

interface PerformanceToolbarProps {
  mode: Mode
  metric: Metric
  dimension: Dimension
  dateRange: string
  branchMonth: string
  selectedBranchMonth?: string
  branchId: string
  mappingStatus: MappingStatus | 'all'
  search: string
  heatmap: boolean
  showDescriptions: boolean
  hideUnmapped: boolean
  branches: Branch[]
  dates: string[]
  months: string[]
  onModeChange: (mode: Mode) => void
  onMetricChange: (metric: Metric) => void
  onDimensionChange: (dimension: Dimension) => void
  onDateRangeChange: (dateRange: string) => void
  onBranchMonthChange: (month: string) => void
  onBranchChange: (branchId: string) => void
  onMappingStatusChange: (status: MappingStatus | 'all') => void
  onSearchChange: (search: string) => void
  onHeatmapChange: (enabled: boolean) => void
  onShowDescriptionsChange: (enabled: boolean) => void
  onHideUnmappedChange: (enabled: boolean) => void
}

const salesMetrics: { value: Metric; label: string }[] = [
  { value: 'amount', label: 'Amount' },
  { value: 'qty', label: 'Qty' },
]

const inventoryMetrics: { value: Metric; label: string }[] = [
  { value: 'stockOh', label: 'Stock on hand' },
  { value: 'stockOnOrder', label: 'Stock on order' },
]

export function PerformanceToolbar(props: PerformanceToolbarProps) {
  const metrics = props.mode === 'sales' ? salesMetrics : inventoryMetrics

  function changeMode(mode: Mode) {
    props.onModeChange(mode)
    props.onMetricChange(mode === 'sales' ? 'amount' : 'stockOh')
    if (mode === 'inventory' && props.dimension === 'month') {
      props.onDimensionChange('branch')
    }
  }

  return (
    <>
      <section className="mode-toolbar" aria-label="Report controls">
        <div className="control-group">
          <span className="control-label">Mode</span>
          <div className="segmented-control">
            {(['sales', 'inventory'] as const).map((value) => (
              <button type="button" aria-pressed={props.mode === value} onClick={() => changeMode(value)} key={value}>
                {value === 'sales' ? 'Sales' : 'Inventory'}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group">
          <span className="control-label">Metric</span>
          <div className="segmented-control metric-control">
            {metrics.map(({ value, label }) => (
              <button type="button" aria-pressed={props.metric === value} onClick={() => props.onMetricChange(value)} key={value}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group view-control">
          <span className="control-label">View</span>
          <div className="view-actions">
            <div className="segmented-control">
              <button type="button" aria-pressed={props.dimension === 'branch'} onClick={() => props.onDimensionChange('branch')}>Branch</button>
              <button type="button" aria-pressed={props.dimension === 'day'} onClick={() => props.onDimensionChange('day')}>Date</button>
              {props.mode === 'sales' && <button type="button" aria-pressed={props.dimension === 'month'} onClick={() => props.onDimensionChange('month')}>Month</button>}
            </div>
            <button className="description-toggle" type="button" aria-pressed={props.showDescriptions} onClick={() => props.onShowDescriptionsChange(!props.showDescriptions)}>
              {props.showDescriptions ? <Eye size={15} aria-hidden="true" /> : <EyeOff size={15} aria-hidden="true" />}
              Description
            </button>
            <button className="description-toggle unmapped-toggle" type="button" aria-pressed={!props.hideUnmapped} onClick={() => props.onHideUnmappedChange(!props.hideUnmapped)}>
              {props.hideUnmapped ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
              Unmap
            </button>
          </div>
        </div>
      </section>

      <section className="filter-bar" aria-label="ตัวกรอง Performance">
        <label className="search-field">
          <span>ค้นหา Item</span>
          <div><Search size={16} aria-hidden="true" /><input type="search" value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} placeholder="SKU หรือรายละเอียด TWD / WA" /></div>
        </label>

        <label>
          <span>{props.mode === 'sales' && props.dimension !== 'day' ? 'เดือน' : 'ช่วงวันที่'}</span>
          <div className="select-wrap">
            <CalendarDays size={16} aria-hidden="true" />
            {props.mode === 'sales' && props.dimension === 'month' ? (
              <select aria-label="เดือน" value="all" disabled><option value="all">ทุกเดือนที่มีข้อมูล</option></select>
            ) : props.mode === 'sales' && props.dimension === 'branch' ? (
              <select aria-label="เดือน" value={props.branchMonth} onChange={(event) => props.onBranchMonthChange(event.target.value)}>
                <option value="latest">เดือนล่าสุด{props.selectedBranchMonth ? ` · ${formatMonth(props.selectedBranchMonth)}` : ''}</option>
                {props.months.map((month) => <option value={month} key={month}>{formatMonth(month)}</option>)}
              </select>
            ) : (
              <select value={props.dateRange} onChange={(event) => props.onDateRangeChange(event.target.value)}><option value="all">ทุกวันที่นำเข้า</option>{props.dates.map((date) => <option value={date} key={date}>{formatDate(date)}</option>)}</select>
            )}
          </div>
        </label>

        <label>
          <span>Branch</span>
          <select value={props.branchId} onChange={(event) => props.onBranchChange(event.target.value)}>
            <option value="all">ทุก Branch</option>
            {props.branches.map((branch) => <option value={branch.id} key={branch.id}>{branch.id} · {branch.name}</option>)}
          </select>
        </label>

        <label>
          <span>Mapping</span>
          <select value={props.mappingStatus} onChange={(event) => props.onMappingStatusChange(event.target.value as MappingStatus | 'all')}>
            <option value="all">ทุกสถานะ</option>
            <option value="confirmed">ยืนยันแล้ว</option>
            <option value="pending">รอตรวจสอบ</option>
            <option value="unmatched">ยังไม่ Mapping</option>
          </select>
        </label>

        <label className="heatmap-toggle">
          <input type="checkbox" checked={props.heatmap} onChange={(event) => props.onHeatmapChange(event.target.checked)} />
          <span className="toggle-track" aria-hidden="true"><span /></span>
          <span><SlidersHorizontal size={15} aria-hidden="true" />Heatmap</span>
        </label>
      </section>
    </>
  )
}
  const formatDate = (date: string) => new Intl.DateTimeFormat('th-TH-u-ca-gregory', {
    day: 'numeric', month: 'short', year: 'numeric',
  }).format(new Date(`${date}T00:00:00`))

const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}
