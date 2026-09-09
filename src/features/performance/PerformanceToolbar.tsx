import { CalendarDays, Eye, EyeOff, SlidersHorizontal, Tags } from 'lucide-react'
import { BranchMultiSelect } from './BranchMultiSelect'
import { DateRangePicker } from './DateRangePicker'
import { MonthRangePicker } from './MonthRangePicker'
import { SkuMultiSelect } from './SkuMultiSelect'
import type { Branch, BranchPeriod, DateRange, Dimension, Metric, Mode, SalesBasis, SkuFlagFilter, SkuOption } from './types'

interface PerformanceToolbarProps {
  mode: Mode
  salesBasis: SalesBasis
  metric: Metric
  dimension: Dimension
  dateRanges: DateRange[]
  monthFrom: string
  monthTo: string
  branchMonth: string
  selectedBranchMonth?: string
  branchPeriod: BranchPeriod
  branchIds: string[]
  skuIds: string[]
  skuOptions: SkuOption[]
  skuOptionsLoading: boolean
  heatmap: boolean
  showDescriptions: boolean
  skuFlag: SkuFlagFilter
  branches: Branch[]
  availableDates: string[]
  months: string[]
  inventoryMetrics: Metric[]
  sourceCode: string
  onModeChange: (mode: Mode) => void
  onSalesBasisChange: (salesBasis: SalesBasis) => void
  onMetricChange: (metric: Metric) => void
  onDimensionChange: (dimension: Dimension) => void
  onDateRangeChange: (dateRanges: DateRange[]) => void
  onMonthRangeChange: (monthFrom: string, monthTo: string) => void
  onBranchMonthChange: (month: string) => void
  onBranchPeriodChange: (period: BranchPeriod) => void
  onBranchChange: (branchIds: string[]) => void
  onSkuChange: (skuIds: string[]) => void
  onHeatmapChange: (enabled: boolean) => void
  onShowDescriptionsChange: (enabled: boolean) => void
  onSkuFlagChange: (filter: SkuFlagFilter) => void
}

const salesMetrics: { value: Metric; label: string }[] = [
  { value: 'amount', label: 'Amount' },
  { value: 'qty', label: 'Qty' },
]

const inventoryMetrics: { value: Metric; label: string }[] = [
  { value: 'stockOh', label: 'Stock on hand' },
  { value: 'stockOnOrder', label: 'Stock on order' },
  { value: 'stockValue', label: 'Stock value' },
]

export function PerformanceToolbar(props: PerformanceToolbarProps) {
  const metrics = props.mode === 'sales'
    ? salesMetrics
    : inventoryMetrics.filter(({ value }) => props.inventoryMetrics.includes(value))

  function changeMode(mode: Mode) {
    props.onModeChange(mode)
    props.onMetricChange(mode === 'sales' ? 'amount' : 'stockOh')
    if (mode === 'inventory' && props.dimension === 'month' && props.sourceCode !== 'TWD') {
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

        {props.mode === 'sales' && (
          <div className="control-group">
            <span className="control-label">Sales Basis</span>
            <div className="segmented-control">
              <button
                type="button"
                aria-pressed={props.salesBasis === 'net'}
                title="ยอดขายสุทธิ รวม Return และ Adjustment"
                onClick={() => props.onSalesBasisChange('net')}
              >
                Net Sales
              </button>
              <button
                type="button"
                aria-pressed={props.salesBasis === 'gross'}
                title="รวมเฉพาะ Amount และ Qty ที่มากกว่า 0 ไม่รวม Return และ Adjustment"
                onClick={() => props.onSalesBasisChange('gross')}
              >
                Gross Sale Out
              </button>
            </div>
          </div>
        )}

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
              {(props.mode === 'sales' || props.sourceCode === 'TWD') && <button type="button" aria-pressed={props.dimension === 'month'} onClick={() => props.onDimensionChange('month')}>Month</button>}
            </div>
            <button className="description-toggle" type="button" aria-pressed={props.showDescriptions} onClick={() => props.onShowDescriptionsChange(!props.showDescriptions)}>
              {props.showDescriptions ? <Eye size={15} aria-hidden="true" /> : <EyeOff size={15} aria-hidden="true" />}
              Description
            </button>
          </div>
        </div>
      </section>

      <section className={`filter-bar ${props.sourceCode === 'TWD' ? 'has-sku-flags' : ''}`} aria-label="ตัวกรอง Performance">
        <SkuMultiSelect
          options={props.skuOptions}
          selectedSkuIds={props.skuIds}
          loading={props.skuOptionsLoading}
          sourceCode={props.sourceCode}
          onApply={props.onSkuChange}
        />

        {props.sourceCode === 'TWD' && (
          <label className="sku-flag-filter">
            <span>สถานะ SKU</span>
            <div className="select-wrap">
              <Tags size={16} aria-hidden="true" />
              <select aria-label="สถานะ Sho/Pro" value={props.skuFlag} onChange={(event) => props.onSkuFlagChange(event.target.value as SkuFlagFilter)}>
                <option value="all">ทั้งหมด</option>
                <option value="flagged">มีสถานะ Sho หรือ Pro</option>
                <option value="sho">Sho · สินค้าตัวโชว์</option>
                <option value="pro">Pro · Promotion</option>
                <option value="both">Sho + Pro</option>
                <option value="none">ยังไม่กำหนดสถานะ</option>
              </select>
            </div>
          </label>
        )}

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
          <DateRangePicker dateRanges={props.dateRanges} availableDates={props.availableDates} onApply={props.onDateRangeChange} />
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
