import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronDown } from 'lucide-react'

interface MonthRangePickerProps {
  monthFrom: string
  monthTo: string
  months: string[]
  onApply: (monthFrom: string, monthTo: string) => void
}

const formatMonth = (month: string) => {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' })
    .format(new Date(year, monthNumber - 1, 1))
}

export function MonthRangePicker({ monthFrom, monthTo, months, onApply }: MonthRangePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [draftFrom, setDraftFrom] = useState('')
  const [draftTo, setDraftTo] = useState('')
  const [error, setError] = useState('')

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
    setDraftFrom(monthFrom)
    setDraftTo(monthTo)
    setError('')
    setOpen(true)
  }

  const label = monthFrom && monthTo
    ? monthFrom === monthTo
      ? formatMonth(monthFrom)
      : `${formatMonth(monthFrom)} – ${formatMonth(monthTo)}`
    : 'ทุกเดือนที่มีข้อมูล'

  const apply = () => {
    if (!draftFrom && !draftTo) {
      onApply('', '')
      setOpen(false)
      return
    }
    if (!draftFrom || !draftTo) {
      setError('กรุณาระบุทั้งเดือนเริ่มต้นและเดือนสิ้นสุด')
      return
    }
    if (draftFrom > draftTo) {
      setError('เดือนเริ่มต้นต้องไม่เกินเดือนสิ้นสุด')
      return
    }
    onApply(draftFrom, draftTo)
    setOpen(false)
  }

  return (
    <div className="filter-popover-field" ref={containerRef}>
      <span className="filter-label">ช่วงเดือน</span>
      <button className="filter-trigger" type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => open ? setOpen(false) : openPopover()}>
        <span><CalendarDays size={15} aria-hidden="true" />{label}</span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="filter-popover date-range-popover" role="dialog" aria-label="เลือกช่วงเดือน">
          <div className="date-range-inputs">
            <label className="date-range-field">
              <span>เดือนเริ่มต้น</span>
              <input aria-label="เดือนเริ่มต้น" type="month" min={months[0]} max={draftTo || months.at(-1)} value={draftFrom} onChange={(event) => { setDraftFrom(event.target.value); setError('') }} />
            </label>
            <label className="date-range-field">
              <span>เดือนสิ้นสุด</span>
              <input aria-label="เดือนสิ้นสุด" type="month" min={draftFrom || months[0]} max={months.at(-1)} value={draftTo} onChange={(event) => { setDraftTo(event.target.value); setError('') }} />
            </label>
          </div>
          {error && <p className="filter-validation" role="alert">{error}</p>}
          <button className="clear-date-range" type="button" onClick={() => { setDraftFrom(''); setDraftTo(''); setError('') }}>ทุกเดือนที่มีข้อมูล</button>
          <footer className="filter-popover-footer">
            <span>{months.length > 0 ? `ข้อมูล ${formatMonth(months[0])} – ${formatMonth(months.at(-1)!)}` : 'ยังไม่มีข้อมูลเดือน'}</span>
            <div>
              <button type="button" onClick={() => setOpen(false)}>ยกเลิก</button>
              <button className="apply-filter" type="button" onClick={apply}>แสดงผล</button>
            </div>
          </footer>
        </div>
      )}
    </div>
  )
}
