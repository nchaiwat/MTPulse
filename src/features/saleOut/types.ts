export type SaleOutMetric = 'amount' | 'qty' | 'average_price'
export type SaleOutBasis = 'gross' | 'net'
export type SaleOutState = 'value' | 'zero' | 'missing' | 'future' | 'unavailable' | 'incomplete'

export interface SaleOutValue {
  state: SaleOutState
  value: number | null
}

export interface SaleOutMonth {
  month: number
  base: SaleOutValue
  comparison: SaleOutValue
  growthPercent: number | null
}

export interface SaleOutModernTrade {
  code: string
  name: string
  status: string
  includedInTotal: boolean
  startDate: string | null
  latestSourceDate: string | null
  latestDailyDate: string | null
  baseYtd: SaleOutValue
  comparisonYtd: SaleOutValue
  difference: number | null
  growthPercent: number | null
  latestMonth: SaleOutValue
  momPercent: number | null
  yoyPercent: number | null
  monthly: SaleOutMonth[]
}

export interface SaleOutPeriod {
  code: string
  base: SaleOutValue
  comparison: SaleOutValue
  growthPercent: number | null
}

export interface SaleOutReport {
  meta: {
    baseYear: number
    comparisonYear: number
    cutoff: string
    activeCutoff: string | null
    salesBasis: SaleOutBasis
    metric: SaleOutMetric
    mtCodes: string[]
    availableYears: number[]
  }
  kpis: {
    baseYtd: SaleOutValue
    comparisonYtd: SaleOutValue
    difference: number | null
    growthPercent: number | null
    latestMonth: SaleOutValue
    momPercent: number | null
    yoyPercent: number | null
    dataCompletenessPercent: number | null
  }
  monthly: SaleOutMonth[]
  modernTrades: SaleOutModernTrade[]
  periods: SaleOutPeriod[]
}

export interface SaleOutFilters {
  baseYear: number
  comparisonYear: number
  cutoff?: string
  salesBasis: SaleOutBasis
  metric: SaleOutMetric
  mtCodes?: string[]
}
