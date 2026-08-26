import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronDown } from 'lucide-react'
import { formatDisplayDate, parseDisplayDate } from '../../shared/dateFormat'

interface DateRangePickerProps {
  dateFrom: string
  dateTo: string
  availableDates: string[]
  onApply: (dateFrom: string, dateTo: string) => void
}

export function DateRangePicker({
  dateFrom,
  dateTo,
  availableDates,
  onApply,
}: DateRangePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const fromPickerRef = useRef<HTMLInputElement>(null)
  const toPickerRef = useRef<HTMLInputElement>(null)
  const [draftFrom, setDraftFrom] = useState('')
  const [draftTo, setDraftTo] = useState('')
  const [error, setError] = useState('')
  const minDate = availableDates[0]
  const maxDate = availableDates.at(-1)

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
    setDraftFrom(formatDisplayDate(dateFrom))
    setDraftTo(formatDisplayDate(dateTo))
    setError('')
    setOpen(true)
  }

  const label = dateFrom && dateTo
    ? dateFrom === dateTo
      ? formatDisplayDate(dateFrom)
      : formatDisplayDate(dateFrom) + ' – ' + formatDisplayDate(dateTo)
    : 'ทุกวันที่มีข้อมูล'

  const apply = () => {
    if (!draftFrom && !draftTo) {
      onApply('', '')
      setOpen(false)
      return
    }
    const parsedFrom = draftFrom ? parseDisplayDate(draftFrom) : ''
    const parsedTo = draftTo ? parseDisplayDate(draftTo) : ''

    if ((draftFrom && !draftTo) || (!draftFrom && draftTo)) {
      setError('กรุณาระบุทั้งวันที่เริ่มต้นและวันที่สิ้นสุด')
      return
    }
    if (!parsedFrom || !parsedTo) {
      setError('กรุณาระบุวันที่เป็น dd/mm/yyyy')
      return
    }
    if (parsedFrom > parsedTo) {
      setError('วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด')
      return
    }
    onApply(parsedFrom, parsedTo)
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
        <div className="filter-popover date-range-popover" role="dialog" aria-label="เลือกช่วงวันที่">
          <div className="date-range-inputs">
            <div className="date-range-field">
              <span>วันที่เริ่มต้น</span>
              <div className="date-entry">
                <input aria-label="วันที่เริ่มต้น" type="text" inputMode="numeric" maxLength={10} placeholder="dd/mm/yyyy" value={draftFrom} onChange={(event) => { setDraftFrom(event.target.value); setError('') }} />
                <button type="button" aria-label="เปิดปฏิทินวันที่เริ่มต้น" onClick={() => fromPickerRef.current?.showPicker()}><CalendarDays size={15} aria-hidden="true" /></button>
                <input ref={fromPickerRef} className="native-date-picker" tabIndex={-1} aria-hidden="true" type="date" value={parseDisplayDate(draftFrom) ?? ''} min={minDate} max={parseDisplayDate(draftTo) || maxDate} onChange={(event) => { setDraftFrom(formatDisplayDate(event.target.value)); setError('') }} />
              </div>
            </div>
            <div className="date-range-field">
              <span>วันที่สิ้นสุด</span>
              <div className="date-entry">
                <input aria-label="วันที่สิ้นสุด" type="text" inputMode="numeric" maxLength={10} placeholder="dd/mm/yyyy" value={draftTo} onChange={(event) => { setDraftTo(event.target.value); setError('') }} />
                <button type="button" aria-label="เปิดปฏิทินวันที่สิ้นสุด" onClick={() => toPickerRef.current?.showPicker()}><CalendarDays size={15} aria-hidden="true" /></button>
                <input ref={toPickerRef} className="native-date-picker" tabIndex={-1} aria-hidden="true" type="date" value={parseDisplayDate(draftTo) ?? ''} min={parseDisplayDate(draftFrom) || minDate} max={maxDate} onChange={(event) => { setDraftTo(formatDisplayDate(event.target.value)); setError('') }} />
              </div>
            </div>
          </div>
          {error && <p className="filter-validation" role="alert">{error}</p>}
          <button className="clear-date-range" type="button" onClick={() => { setDraftFrom(''); setDraftTo(''); setError('') }}>ทุกวันที่มีข้อมูล</button>
          <footer className="filter-popover-footer">
            <span>{minDate && maxDate ? 'ข้อมูล ' + formatDisplayDate(minDate) + ' – ' + formatDisplayDate(maxDate) : 'ยังไม่มีข้อมูลวันที่'}</span>
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
