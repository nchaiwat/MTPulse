export type MonitoringStatus = 'healthy' | 'warning' | 'critical'
export type TechnicalMetricStatus = MonitoringStatus | 'unknown'

export interface MonitoringHost {
  status: MonitoringStatus
  cpuPercent: number | null
  memoryUsedPercent: number | null
  memoryTotalBytes: number | null
  diskUsedPercent: number | null
  diskTotalBytes: number | null
  uptimeSeconds: number | null
}

export interface MonitoringTechnicalMetric {
  code: string
  label: string
  value: number | null
  unit: string
  warningThreshold: number
  criticalThreshold: number
  status: TechnicalMetricStatus
  recommendation: string
}

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
  enabled: boolean
  status: MonitoringStatus | 'inactive'
  latestDataDate: string | null
  lagDays: number | null
  recordCount: number
  latestImport: MonitoringImport | null
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
  host: MonitoringHost
  database: MonitoringDatabase
  workerHeartbeatAt: string | null
  technicalMetrics: MonitoringTechnicalMetric[]
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
  hostCpuPercent: number | null
  hostMemoryUsedPercent: number | null
  hostDiskUsedPercent: number | null
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
