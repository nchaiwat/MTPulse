import { parseDisplayDate } from '../../shared/dateFormat'

export interface DateRangeDraft {
  from: string
  to: string
}

export function validateDateRangeDrafts(drafts: DateRangeDraft[]) {
  const errors = drafts.map(() => '')
  const parsed = drafts.map((range, index) => {
    if (!range.from && !range.to && drafts.length === 1) return null
    if (!range.from || !range.to) {
      errors[index] = 'กรุณาระบุทั้งวันที่เริ่มต้นและวันที่สิ้นสุด'
      return null
    }
    const from = parseDisplayDate(range.from)
    const to = parseDisplayDate(range.to)
    if (!from || !to) {
      errors[index] = 'กรุณาระบุวันที่เป็น dd/mm/yyyy'
      return null
    }
    if (from > to) {
      errors[index] = 'วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด'
      return null
    }
    return { from, to }
  })

  parsed.forEach((range, index) => {
    if (!range) return
    parsed.forEach((other, otherIndex) => {
      if (!other || index >= otherIndex) return
      if (range.from <= other.to && other.from <= range.to) {
        errors[index] = `ทับกับช่วงที่ ${otherIndex + 1}`
        errors[otherIndex] = `ทับกับช่วงที่ ${index + 1}`
      }
    })
  })
  return errors
}
