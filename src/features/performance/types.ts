import type { ActiveModernTradeCode } from '../../config/modernTrades'

export type Mode = 'sales' | 'inventory'
export type SalesBasis = 'net' | 'gross'
export type Metric = 'amount' | 'qty' | 'stockOh' | 'stockOnOrder' | 'stockValue'
export type ModernTradeCode = ActiveModernTradeCode
export type Dimension = 'branch' | 'day' | 'month'
export type BranchPeriod = 'month' | 'day'
export type MappingStatus = 'confirmed' | 'pending' | 'unmatched'
export type ItemType = 'normal' | 'trial'
export type SkuFlagFilter = 'all' | 'flagged' | 'sho' | 'pro' | 'both' | 'none'
export type SkuAnalysisFlagName = 'sho' | 'pro'

export interface DateRange {
  from: string
  to: string
}

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
  stockValue?: number
}

export interface PerformanceItem {
  sku: string
  twdDescription: string
  waItem: string | null
  waDescription: string | null
  mappingStatus: MappingStatus
  itemType?: ItemType
  isSho?: boolean
  isPro?: boolean
  tom?: number | null
  tod?: number | null
  points: DataPoint[]
}

export interface SkuAnalysisFlagResponse {
  mtCode: ModernTradeCode
  sku: string
  isSho: boolean
  isPro: boolean
  updatedAt: string
}

export interface SkuOption {
  sku: string
  twdDescription: string
  waItem: string | null
  waDescription: string | null
  itemType: ItemType
}
export interface SelectedCell {
  sku: string
  dimensionKey?: string
}

export interface PerformanceResponse {
  mtCode?: ModernTradeCode
  mtName?: string
  metricCapabilities?: {
    sales: Metric[]
    inventory: Metric[]
  }
  branches: Branch[]
  dates: string[]
  availableDates?: string[]
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
  inventorySummary?: {
    stockOh: number
    stockOnOrder: number
    stockValue: number
    averageTom?: number | null
    averageTod?: number | null
    turnoverSkuCount?: number
    turnoverReferenceDate?: string | null
  }
  latestImport: {
    dataDate: string
    status: string
    rowCount: number
    warnings: string[]
  } | null
}
