import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, ChevronDown, Plus, Trash2 } from 'lucide-react'
import { formatDisplayDate, parseDisplayDate } from '../../shared/dateFormat'
import type { DateRange } from './types'
import { validateDateRangeDrafts } from './dateRangeValidation'

const maxDateRanges = 12

interface DraftRange {
  id: number
  from: string
  to: string
}

interface DateRangePickerProps {
  dateRanges: DateRange[]
  availableDates: string[]
  onApply: (dateRanges: DateRange[]) => void
}

function DateEntry({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: string
  min?: string
  max?: string
  onChange: (value: string) => void
}) {
  const pickerRef = useRef<HTMLInputElement>(null)
  return (
    <div className="date-entry">
      <input aria-label={label} type="text" inputMode="numeric" maxLength={10} placeholder="dd/mm/yyyy" value={value} onChange={(event) => onChange(event.target.value)} />
      <button type="button" aria-label={`เปิดปฏิทิน${label}`} onClick={() => pickerRef.current?.showPicker()}><CalendarDays size={15} aria-hidden="true" /></button>
      <input ref={pickerRef} className="native-date-picker" tabIndex={-1} aria-hidden="true" type="date" value={parseDisplayDate(value) ?? ''} min={min} max={max} onChange={(event) => onChange(formatDisplayDate(event.target.value))} />
    </div>
  )
}

export function DateRangePicker({
  dateRanges,
  availableDates,
  onApply,
}: DateRangePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const nextId = useRef(1)
  const [open, setOpen] = useState(false)
  const [drafts, setDrafts] = useState<DraftRange[]>([{ id: 0, from: '', to: '' }])
  const minDate = availableDates[0]
  const maxDate = availableDates.at(-1)
  const errors = useMemo(() => validateDateRangeDrafts(drafts), [drafts])
  const hasErrors = errors.some(Boolean)

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const openPopover = () => {
    setDrafts(dateRanges.length
      ? dateRanges.map((range) => ({ id: nextId.current++, from: formatDisplayDate(range.from), to: formatDisplayDate(range.to) }))
      : [{ id: nextId.current++, from: '', to: '' }])
    setOpen(true)
  }

  const label = dateRanges.length === 0
    ? 'ทุกวันที่มีข้อมูล'
    : dateRanges.length === 1
      ? dateRanges[0].from === dateRanges[0].to
        ? formatDisplayDate(dateRanges[0].from)
        : `${formatDisplayDate(dateRanges[0].from)} – ${formatDisplayDate(dateRanges[0].to)}`
      : `${dateRanges.length} ช่วง · ${formatDisplayDate(dateRanges[0].from)} – ${formatDisplayDate(dateRanges.at(-1)!.to)}`

  const updateDraft = (index: number, field: 'from' | 'to', value: string) => {
    setDrafts((current) => current.map((range, rangeIndex) => rangeIndex === index ? { ...range, [field]: value } : range))
  }

  const apply = () => {
    if (hasErrors) return
    if (drafts.length === 1 && !drafts[0].from && !drafts[0].to) {
      onApply([])
      setOpen(false)
      return
    }
    const ranges = drafts
      .map(({ from, to }) => ({ from: parseDisplayDate(from)!, to: parseDisplayDate(to)! }))
      .sort((left, right) => left.from.localeCompare(right.from))
    onApply(ranges)
    setOpen(false)
  }

  return (
    <div className="filter-popover-field" ref={containerRef}>
      <span className="filter-label">ช่วงวันที่</span>
      <button className="filter-trigger" type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => open ? setOpen(false) : openPopover()}>
        <span><CalendarDays size={15} aria-hidden="true" />{label}</span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="filter-popover date-range-popover date-multi-range-popover" role="dialog" aria-label="เลือกช่วงวันที่">
          <div className="date-range-list">
            {drafts.map((range, index) => {
              const parsedFrom = parseDisplayDate(range.from) ?? ''
              const parsedTo = parseDisplayDate(range.to) ?? ''
              const fromLabel = index === 0 ? 'วันที่เริ่มต้น' : `ช่วงที่ ${index + 1} วันที่เริ่มต้น`
              const toLabel = index === 0 ? 'วันที่สิ้นสุด' : `ช่วงที่ ${index + 1} วันที่สิ้นสุด`
              return (
                <div className={`date-range-row ${errors[index] ? 'has-error' : ''}`} key={range.id}>
                  <strong>ช่วงที่ {index + 1}</strong>
                  <div className="date-range-inputs">
                    <div className="date-range-field">
                      <span>วันที่เริ่มต้น</span>
                      <DateEntry label={fromLabel} value={range.from} min={minDate} max={parsedTo || maxDate} onChange={(value) => updateDraft(index, 'from', value)} />
                    </div>
                    <div className="date-range-field">
                      <span>วันที่สิ้นสุด</span>
                      <DateEntry label={toLabel} value={range.to} min={parsedFrom || minDate} max={maxDate} onChange={(value) => updateDraft(index, 'to', value)} />
                    </div>
                  </div>
                  <button
                    className="remove-date-range"
                    type="button"
                    aria-label={`ลบช่วงที่ ${index + 1}`}
                    onClick={() => setDrafts((current) => current.length === 1 ? [{ ...current[0], from: '', to: '' }] : current.filter((_, rangeIndex) => rangeIndex !== index))}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                  {errors[index] && <p className="filter-validation" role="alert">{errors[index]}</p>}
                </div>
              )
            })}
          </div>
          <div className="date-range-tools">
            <button type="button" disabled={drafts.length >= maxDateRanges} onClick={() => setDrafts((current) => [...current, { id: nextId.current++, from: '', to: '' }])}>
              <Plus size={14} aria-hidden="true" />เพิ่มช่วงวันที่
            </button>
            <span>{drafts.length} / {maxDateRanges} ช่วง</span>
          </div>
          <button className="clear-date-range" type="button" onClick={() => setDrafts([{ id: nextId.current++, from: '', to: '' }])}>ทุกวันที่มีข้อมูล</button>
          <footer className="filter-popover-footer">
            <span aria-live="polite">{hasErrors ? 'แก้ไขช่วงวันที่ที่มีกรอบสีแดงก่อนแสดงผล' : 'ระบบจะแสดงเฉพาะวันที่ในช่วงที่เลือก'}</span>
            <div>
              <button type="button" onClick={() => setOpen(false)}>ยกเลิก</button>
              <button className="apply-filter" type="button" disabled={hasErrors} onClick={apply}>แสดงผล</button>
            </div>
          </footer>
        </div>
      )}
    </div>
  )
}
