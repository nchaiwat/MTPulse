import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { SkuOption } from './types'

interface SkuMultiSelectProps {
  options: SkuOption[]
  selectedSkuIds: string[]
  loading?: boolean
  onApply: (skuIds: string[]) => void
}

const rowHeight = 48
const viewportHeight = 288
const overscan = 5

export function SkuMultiSelect({ options, selectedSkuIds, loading = false, onApply }: SkuMultiSelectProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [draftIds, setDraftIds] = useState<string[]>([])
  const [scrollTop, setScrollTop] = useState(0)
  const allSkuIds = useMemo(() => options.map((option) => option.sku), [options])
  const draftSet = useMemo(() => new Set(draftIds), [draftIds])
  const filteredOptions = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return options
    return options.filter((option) => [option.sku, option.twdDescription, option.waItem, option.waDescription]
      .filter(Boolean)
      .some((value) => value!.toLowerCase().includes(term)))
  }, [options, search])
  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan)
  const endIndex = Math.min(filteredOptions.length, Math.ceil((scrollTop + viewportHeight) / rowHeight) + overscan)
  const visibleOptions = filteredOptions.slice(startIndex, endIndex)

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
    setDraftIds(selectedSkuIds.length > 0 ? selectedSkuIds : allSkuIds)
    setSearch('')
    setScrollTop(0)
    setOpen(true)
  }

  const toggleSku = (sku: string) => {
    setDraftIds((current) => current.includes(sku)
      ? current.filter((value) => value !== sku)
      : [...current, sku])
  }

  const selectedLabel = (() => {
    if (selectedSkuIds.length === 0 || selectedSkuIds.length === options.length) return 'ทุก SKU'
    if (selectedSkuIds.length === 1) return selectedSkuIds[0]
    return `เลือก ${selectedSkuIds.length.toLocaleString('en-US')} SKU`
  })()

  const apply = () => {
    const selected = allSkuIds.filter((sku) => draftSet.has(sku))
    onApply(selected.length === allSkuIds.length ? [] : selected)
    setOpen(false)
  }

  const changeSearch = (value: string) => {
    setSearch(value)
    setScrollTop(0)
    if (listRef.current) listRef.current.scrollTop = 0
  }

  return (
    <div className="filter-popover-field sku-filter-field" ref={containerRef}>
      <span className="filter-label">Item</span>
      <button className="filter-trigger" type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => open ? setOpen(false) : openPopover()}>
        <span>{loading ? 'กำลังโหลด SKU…' : selectedLabel}</span><ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="filter-popover sku-popover" role="dialog" aria-label="เลือก SKU">
          <label className="popover-search">
            <span className="sr-only">ค้นหา SKU</span>
            <Search size={15} aria-hidden="true" />
            <input autoFocus type="search" value={search} onChange={(event) => changeSearch(event.target.value)} placeholder="ค้นหา SKU หรือรายละเอียด TWD / WA" />
          </label>
          <div className="branch-selection-tools">
            <button type="button" onClick={() => setDraftIds(allSkuIds)}>เลือกทั้งหมด</button>
            <button type="button" onClick={() => setDraftIds([])}>ล้างการเลือก</button>
          </div>
          <div
            className="sku-option-list"
            role="group"
            aria-label="รายการ SKU"
            ref={listRef}
            onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
          >
            <div className="sku-option-spacer" style={{ height: filteredOptions.length * rowHeight }}>
              {visibleOptions.map((option, visibleIndex) => {
                const optionIndex = startIndex + visibleIndex
                return (
                  <label className="sku-option" style={{ transform: `translateY(${optionIndex * rowHeight}px)` }} key={option.sku}>
                    <input type="checkbox" checked={draftSet.has(option.sku)} onChange={() => toggleSku(option.sku)} />
                    <span className="sku-option-label">
                      <span className="sku-option-codes">
                        <strong>{option.sku}</strong>
                        <span aria-hidden="true">-</span>
                        <code>{option.waItem || '—'}</code>
                        {option.itemType === 'trial' && <em className="trial-badge">สินค้าทดลอง</em>}
                      </span>
                      <small>{option.twdDescription || option.waDescription || 'ไม่มีรายละเอียด'}</small>
                    </span>
                  </label>
                )
              })}
            </div>
            {filteredOptions.length === 0 && <p className="sku-empty">ไม่พบ SKU ที่ค้นหา</p>}
          </div>
          <footer className="filter-popover-footer">
            <span>เลือกแล้ว {draftIds.length.toLocaleString('en-US')} SKU</span>
            <div><button type="button" onClick={() => setOpen(false)}>ยกเลิก</button><button className="apply-filter" type="button" disabled={draftIds.length === 0} onClick={apply}>แสดงผล</button></div>
          </footer>
        </div>
      )}
    </div>
  )
}