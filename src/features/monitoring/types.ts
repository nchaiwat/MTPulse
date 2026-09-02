export type MonitoringStatus = 'healthy' | 'warning' | 'critical'

export interface MonitoringNotice {
  code?: string
  batchId?: number
  level: MonitoringStatus
  title: string
  detail: string
}

export interface MonitoringDatabase {
  status: MonitoringStatus
  factCount: number
  databaseSizeBytes: number
  factTableSizeBytes: number
  factIndexesSizeBytes: number
  deadTupleCount: number
  deadTupleRatio: number
  currentConnections: number
  maxConnections: number
  lastVacuumAt: string | null
  lastAnalyzeAt: string | null
}

export interface MonitoringImport {
  batchId: number
  dataDate: string
  status: string
  finishedAt: string | null
  rowCount: number
  warningCount: number
  warningResolution?: string | null
}

export interface MonitoringModernTrade {
  code: string
  name: string
  latestDataDate: string | null
  lagDays: number | null
}

export interface SlowQuery {
  query: string
  calls: number
  meanTimeMs: number
  totalTimeMs: number
  rows: number
}

export interface MonitoringCurrent {
  capturedAt: string
  overallStatus: MonitoringStatus
  notices: MonitoringNotice[]
  api: { status: MonitoringStatus }
  database: MonitoringDatabase
  latestDataDate: string | null
  latestImport: MonitoringImport | null
  modernTrades: MonitoringModernTrade[]
  pgStatStatementsAvailable: boolean
  slowQueries: SlowQuery[]
}

export interface MonitoringHistory {
  date: string
  capturedAt: string
  trigger: string
  status: MonitoringStatus
  factCount: number
  databaseSizeBytes: number
  deadTupleRatio: number
  connections: number
  latestDataDate: string | null
  warningCount: number
}

export interface MonitoringResponse {
  current: MonitoringCurrent
  history: MonitoringHistory[]
  automaticImports?: {
    runs: ImportRun[]
    pendingFiles: Array<{
      sourceFileId: number
      mtCode: string
      filename: string
      dataDate: string | null
      sourceFolderDate: string | null
      status: 'pending_review' | 'failed' | 'missing'
      message: string | null
      lastSeenAt: string
      batchId: number | null
    }>
    pendingSkus: Array<{
      skuInterestId: number
      mtCode: string
      sku: string
      description: string | null
      status: 'pending' | 'accepted'
      firstSeenDate: string
      lastSeenDate: string
      lastSeenAt: string
    }>
  }
}
import type { ImportRun } from '../settings/fileShareSettingsApi'
