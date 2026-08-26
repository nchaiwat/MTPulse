import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { Branch } from './types'

interface BranchMultiSelectProps {
  branches: Branch[]
  selectedBranchIds: string[]
  onApply: (branchIds: string[]) => void
}

export function BranchMultiSelect({
  branches,
  selectedBranchIds,
  onApply,
}: BranchMultiSelectProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [draftIds, setDraftIds] = useState<string[]>([])
  const allBranchIds = useMemo(() => branches.map((branch) => branch.id), [branches])
  const filteredBranches = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return branches
    return branches.filter((branch) =>
      (branch.id + ' ' + branch.name).toLowerCase().includes(term),
    )
  }, [branches, search])

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
    setDraftIds(selectedBranchIds.length > 0 ? selectedBranchIds : allBranchIds)
    setSearch('')
    setOpen(true)
  }

  const toggleBranch = (branchId: string) => {
    setDraftIds((current) => current.includes(branchId)
      ? current.filter((value) => value !== branchId)
      : [...current, branchId])
  }

  const selectedLabel = (() => {
    if (selectedBranchIds.length === 0 || selectedBranchIds.length === branches.length) {
      return 'ทุก Branch'
    }
    if (selectedBranchIds.length === 1) {
      const branch = branches.find((entry) => entry.id === selectedBranchIds[0])
      return branch ? branch.id + ' - ' + branch.name : selectedBranchIds[0]
    }
    return 'เลือก ' + selectedBranchIds.length + ' Branch'
  })()

  const apply = () => {
    const selected = allBranchIds.filter((branchId) => draftIds.includes(branchId))
    onApply(selected.length === allBranchIds.length ? [] : selected)
    setOpen(false)
  }

  return (
    <div className="filter-popover-field" ref={containerRef}>
      <span className="filter-label">Branch</span>
      <button className="filter-trigger" type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => open ? setOpen(false) : openPopover()}>
        <span>{selectedLabel}</span><ChevronDown size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="filter-popover branch-popover" role="dialog" aria-label="เลือก Branch">
          <label className="popover-search">
            <span className="sr-only">ค้นหา Branch</span>
            <Search size={15} aria-hidden="true" />
            <input autoFocus type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ค้นหารหัสหรือชื่อ Branch" />
          </label>
          <div className="branch-selection-tools">
            <button type="button" onClick={() => setDraftIds(allBranchIds)}>เลือกทั้งหมด</button>
            <button type="button" onClick={() => setDraftIds([])}>ล้างการเลือก</button>
          </div>
          <div className="branch-option-list" role="group" aria-label="รายการ Branch">
            {filteredBranches.map((branch) => (
              <label key={branch.id}>
                <input type="checkbox" checked={draftIds.includes(branch.id)} onChange={() => toggleBranch(branch.id)} />
                <span className="branch-option-label"><strong>{branch.id}</strong><span aria-hidden="true"> - </span><small>{branch.name}</small></span>
              </label>
            ))}
            {filteredBranches.length === 0 && <p>ไม่พบ Branch ที่ค้นหา</p>}
          </div>
          <footer className="filter-popover-footer">
            <span>เลือกแล้ว {draftIds.length.toLocaleString('en-US')} Branch</span>
            <div><button type="button" onClick={() => setOpen(false)}>ยกเลิก</button><button className="apply-filter" type="button" disabled={draftIds.length === 0} onClick={apply}>แสดงผล</button></div>
          </footer>
        </div>
      )}
    </div>
  )
}
