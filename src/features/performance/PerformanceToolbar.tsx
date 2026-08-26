import { CalendarDays, Eye, EyeOff, SlidersHorizontal } from 'lucide-react'
import { BranchMultiSelect } from './BranchMultiSelect'
import { DateRangePicker } from './DateRangePicker'
import { MonthRangePicker } from './MonthRangePicker'
import { SkuMultiSelect } from './SkuMultiSelect'
import type { Branch, BranchPeriod, Dimension, Metric, Mode, SkuOption } from './types'

interface PerformanceToolbarProps {
  mode: Mode
  metric: Metric
  dimension: Dimension
  dateFrom: string
  monthFrom: string
  monthTo: string
  dateTo: string
  branchMonth: string
  selectedBranchMonth?: string
  branchPeriod: BranchPeriod
  branchIds: string[]
  skuIds: string[]
  skuOptions: SkuOption[]
  skuOptionsLoading: boolean
  heatmap: boolean
  showDescriptions: boolean
  branches: Branch[]
  availableDates: string[]
  months: string[]
  onModeChange: (mode: Mode) => void
  onMetricChange: (metric: Metric) => void
  onDimensionChange: (dimension: Dimension) => void
  onDateRangeChange: (dateFrom: string, dateTo: string) => void
  onMonthRangeChange: (monthFrom: string, monthTo: string) => void
  onBranchMonthChange: (month: string) => void
  onBranchPeriodChange: (period: BranchPeriod) => void
  onBranchChange: (branchIds: string[]) => void
  onSkuChange: (skuIds: string[]) => void
  onHeatmapChange: (enabled: boolean) => void
  onShowDescriptionsChange: (enabled: boolean) => void
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

        {props.mode === 'sales' && props.dimension === 'branch' && (
          <div className="control-group">
            <span className="control-label">ช่วงข้อมูล</span>
            <div className="segmented-control">
              <button type="button" aria-pressed={props.branchPeriod === 'month'} onClick={() => props.onBranchPeriodChange('month')}>รายเดือน</button>
              <button type="button" aria-pressed={props.branchPeriod === 'day'} onClick={() => props.onBranchPeriodChange('day')}>รายวัน</button>
            </div>
          </div>
        )}
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
          </div>
        </div>
      </section>

      <section className="filter-bar" aria-label="ตัวกรอง Performance">
        <SkuMultiSelect
          options={props.skuOptions}
          selectedSkuIds={props.skuIds}
          loading={props.skuOptionsLoading}
          onApply={props.onSkuChange}
        />

        {props.dimension === 'month' ? (
          <MonthRangePicker monthFrom={props.monthFrom} monthTo={props.monthTo} months={props.months} onApply={props.onMonthRangeChange} />
        ) : props.mode === 'sales' && props.dimension === 'branch' && props.branchPeriod === 'month' ? (
          <label>
            <span>เดือน</span>
            <div className="select-wrap">
              <CalendarDays size={16} aria-hidden="true" />
              <select aria-label="เดือน" value={props.branchMonth} onChange={(event) => props.onBranchMonthChange(event.target.value)}>
                <option value="latest">เดือนล่าสุด{props.selectedBranchMonth ? ` · ${formatMonth(props.selectedBranchMonth)}` : ''}</option>
                {props.months.map((month) => <option value={month} key={month}>{formatMonth(month)}</option>)}
              </select>
            </div>
          </label>
        ) : (
          <DateRangePicker dateFrom={props.dateFrom} dateTo={props.dateTo} availableDates={props.availableDates} onApply={props.onDateRangeChange} />
        )}

        <BranchMultiSelect branches={props.branches} selectedBranchIds={props.branchIds} onApply={props.onBranchChange} />


        <label className="heatmap-toggle">
          <input type="checkbox" checked={props.heatmap} onChange={(event) => props.onHeatmapChange(event.target.checked)} />
          <span className="toggle-track" aria-hidden="true"><span /></span>
          <span><SlidersHorizontal size={15} aria-hidden="true" />Heatmap</span>
        </label>
      </section>
    </>
  )
}

const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(year, monthNumber - 1, 1))
}
