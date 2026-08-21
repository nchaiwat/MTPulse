export type Mode = 'sales' | 'inventory'
export type Metric = 'amount' | 'qty' | 'stockOh' | 'stockOnOrder'
export type Dimension = 'branch' | 'day' | 'month'
export type MappingStatus = 'confirmed' | 'pending' | 'unmatched'

export interface Branch {
  id: string
  name: string
}

export interface DataPoint {
  date: string
  branchId: string
  amount: number
  qty: number
  stockOh: number
  stockOnOrder: number
}

export interface PerformanceItem {
  sku: string
  twdDescription: string
  waItem: string | null
  waDescription: string | null
  mappingStatus: MappingStatus
  points: DataPoint[]
}

export interface SelectedCell {
  sku: string
  dimensionKey?: string
}

export interface PerformanceResponse {
  branches: Branch[]
  dates: string[]
  months?: string[]
  selectedMonth?: string | null
  columnTotals?: Record<string, { amount: number, qty: number }>
  items: PerformanceItem[]
  meta: {
    page: number
    pageSize: number
    totalSkus: number
    totalPages: number
    totalBranches: number
  }
  summary?: {
    amount: number
    qty: number
    mappingAttention: number
  }
  latestImport: {
    dataDate: string
    status: string
    rowCount: number
    warnings: string[]
  } | null
}
