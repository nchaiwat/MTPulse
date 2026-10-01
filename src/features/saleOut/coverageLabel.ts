import type { SaleOutValue } from './types'

export function coverageLabel(entry: SaleOutValue) {
  if (entry.state !== 'incomplete') return ''
  if (entry.coveredDays === undefined || entry.expectedDays === undefined) return 'ข้อมูลไม่ครบ'
  return `ข้อมูล ${entry.coveredDays}/${entry.expectedDays} ${entry.coverageUnit === 'mt_days' ? 'วันรวมทุก MT' : 'วัน'}`
}
