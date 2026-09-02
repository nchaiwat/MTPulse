export type DashboardPeriod = 'ytd' | 'h1' | 'h2' | 'full'
export type DashboardMetric = 'amount' | 'qty'

export interface DashboardMeta {
  mtCode: string
  mtName: string
  year: number | null
  previousYear: number | null
  period: DashboardPeriod
  rangeFrom?: string
  rangeTo?: string
  latestDataDate: string | null
  availableYears: number[]
  loadedDays: number
  expectedDays: number
  completenessPercent: number
}

export interface DashboardSummary {
  currentAmount: number
  previousAmount: number
  amountYoY: number | null
  currentQty: number
  previousQty: number
  qtyYoY: number | null
}

export interface DashboardMonth {
  month: number
  monthKey: string
  currentAmount: number
  previousAmount: number
  amountYoY: number | null
  amountMoM: number | null
  currentQty: number
  previousQty: number
  qtyYoY: number | null
}

export interface DashboardBranch {
  branchCode: string
  branchName: string
  mappedBranchCode: string | null
  displayName: string
  currentAmount: number
  previousAmount: number
  currentQty: number
  previousQty: number
  amountYoY: number | null
  qtyYoY: number | null
}

export interface DashboardSku {
  sku: string
  description: string
  currentAmount: number
  previousAmount: number
  currentQty: number
  previousQty: number
  amountYoY: number | null
  qtyYoY: number | null
}

export interface TwdDashboardResponse {
  meta: DashboardMeta
  summary: DashboardSummary | null
  monthly: DashboardMonth[]
  topBranches: DashboardBranch[]
  topSkus: DashboardSku[]
}
