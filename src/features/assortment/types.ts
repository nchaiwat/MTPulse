export type BaseItem = {
  id: string
  description: string
  attributes: string[]
  members: string[]
  version: number
}
export type Plan = {
  id: string
  name: string
  year: number
  version: number
  primary: boolean
}
export type Catalog = {
  bases: BaseItem[]
  plans: Plan[]
  mts: string[]
  pageSize: number
}
export type Cell = {
  years: Record<
    string,
    { months: (number | null)[]; total: number | null; snapshot: string | null }
  >
  forecast: (number | null)[]
  forecastTotal: number | null
  filled: number
  growth: number | null
}
export type Report = {
  items: (BaseItem & { cells: Record<string, Cell> })[]
  total: number
  page: number
  pageSize: number
  mts: string[]
  year: number
  coverage: Record<
    string,
    Record<
      string,
      {
        days: number
        expected: number
        months?: { days: number; expected: number }[]
      }
    >
  >
  planVersion: number | null
}
export const attrs = ['กลุ่ม', 'รุ่น', 'สินค้า', 'ประเภท', 'มุ้ง', 'สี', 'ขนาด']
export const months = [
  'ม.ค.',
  'ก.พ.',
  'มี.ค.',
  'เม.ย.',
  'พ.ค.',
  'มิ.ย.',
  'ก.ค.',
  'ส.ค.',
  'ก.ย.',
  'ต.ค.',
  'พ.ย.',
  'ธ.ค.',
]
export const num = (v: number | null | undefined) =>
  v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: 4 })
