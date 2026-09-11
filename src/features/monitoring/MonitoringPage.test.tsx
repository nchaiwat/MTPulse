import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MonitoringPage } from './MonitoringPage'

const response = {
  current: {
    capturedAt: '2026-08-25T10:00:00+07:00',
    overallStatus: 'warning',
    notices: [{
      code: 'import_warning',
      batchId: 18,
      level: 'warning',
      title: 'Import Batch 18 มีคำเตือน 1 รายการ',
      detail: 'Stock On Hand: calculated=77904.0, source=77379',
    }],
    api: { status: 'healthy' },
    host: {
      status: 'healthy',
      cpuPercent: 14.2,
      memoryUsedPercent: 62.5,
      memoryTotalBytes: 17179869184,
      diskUsedPercent: 71.4,
      diskTotalBytes: 536870912000,
      uptimeSeconds: 183600,
    },
    database: {
      status: 'healthy',
      factCount: 175717,
      databaseSizeBytes: 71303168,
      factTableSizeBytes: 53477376,
      factIndexesSizeBytes: 17825792,
      deadTupleCount: 10,
      deadTupleRatio: 0.01,
      currentConnections: 4,
      maxConnections: 100,
      lastVacuumAt: '2026-08-25T02:00:00+00:00',
      lastAnalyzeAt: '2026-08-25T02:05:00+00:00',
    },
    latestDataDate: '2026-08-23',
    workerHeartbeatAt: '2026-08-25T09:59:30+07:00',
    technicalMetrics: [
      { code: 'cpu', label: 'CPU load', value: 14.2, unit: '%', warningThreshold: 80, criticalThreshold: 95, status: 'healthy', recommendation: 'ตรวจ Process' },
      { code: 'memory', label: 'RAM', value: 62.5, unit: '%', warningThreshold: 80, criticalThreshold: 90, status: 'healthy', recommendation: 'ตรวจ RAM' },
      { code: 'disk', label: 'Disk', value: 71.4, unit: '%', warningThreshold: 80, criticalThreshold: 90, status: 'healthy', recommendation: 'ตรวจ Disk' },
    ],
    latestImport: {
      batchId: 7,
      dataDate: '2026-08-22',
      status: 'imported',
      finishedAt: '2026-08-25T03:00:00+00:00',
      rowCount: 12590,
      warningCount: 0,
    },
    modernTrades: [{
      code: 'TWD',
      name: 'ไทวัสดุ',
      enabled: true,
      status: 'warning',
      latestDataDate: '2026-08-22',
      lagDays: 3,
      recordCount: 175717,
      latestImport: {
        batchId: 7,
        dataDate: '2026-08-22',
        status: 'imported',
        finishedAt: '2026-08-25T03:00:00+00:00',
        rowCount: 12590,
        warningCount: 0,
      },
    }],
    pgStatStatementsAvailable: true,
    slowQueries: [{ query: 'SELECT * FROM sales_inventory_facts', calls: 3, meanTimeMs: 12.5, totalTimeMs: 37.5, rows: 30 }],
  },
  history: [{
    date: '2026-08-25',
    capturedAt: '2026-08-25T10:00:00+07:00',
    trigger: 'page_open',
    status: 'warning',
    factCount: 175717,
    databaseSizeBytes: 71303168,
    deadTupleRatio: 0.01,
    connections: 4,
    latestDataDate: '2026-08-22',
    warningCount: 1,
    hostCpuPercent: 14.2,
    hostMemoryUsedPercent: 62.5,
    hostDiskUsedPercent: 71.4,
  }],
}

describe('MonitoringPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders HH in data readiness even before its first import', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      ...response,
      current: {
        ...response.current,
        modernTrades: [
          ...response.current.modernTrades,
          {
            code: 'HH',
            name: 'HomeHub',
            enabled: false,
            status: 'inactive',
            latestDataDate: null,
            lagDays: null,
            recordCount: 0,
            latestImport: null,
          },
        ],
      },
    }), { status: 200 }))

    render(<MonitoringPage />)

    expect(await screen.findByText('HomeHub')).toBeInTheDocument()
    expect(screen.getByText('HH')).toBeInTheDocument()
  })

  it('shows current health, database workload, slow queries, and refreshes on demand', async () => {
    const onOpenImports = vi.fn()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }))

    render(<MonitoringPage onOpenImports={onOpenImports} />)

    expect(await screen.findByRole('heading', { name: 'Monitoring' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'สถานะข้อมูลแยกตาม Modern Trade' })).toBeInTheDocument()
    expect(screen.getByText('12,590 records · 25/08/2026 10:00')).toBeInTheDocument()
    expect(screen.getAllByText('22/08/2026')).toHaveLength(2)
    expect(screen.getAllByText('175,717')).toHaveLength(3)
    expect(screen.getByText('Import Batch 18 มีคำเตือน 1 รายการ')).toBeInTheDocument()
    expect(screen.getByText('Stock On Hand: calculated=77904.0, source=77379')).toBeInTheDocument()
    expect(screen.getByText('SELECT * FROM sales_inventory_facts')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'ทรัพยากร Server และฐานข้อมูล' })).toBeInTheDocument()
    expect(screen.getByText('62.5%')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'ประวัติสถานะรายวัน' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'ดำเนินการแก้ไข' }))
    expect(onOpenImports).toHaveBeenCalledWith(18)

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/monitoring/refresh'),
      expect.objectContaining({ method: 'POST' }),
    ))
  })

  it('lets the user accept or ignore a newly detected SKU', async () => {
    const pendingResponse = {
      ...response,
      automaticImports: {
        runs: [],
        pendingFiles: [],
        pendingSkus: [{
          skuInterestId: 1,
          mtCode: 'HP',
          sku: 'NEW-001',
          description: 'สินค้าใหม่',
          status: 'pending',
          firstSeenDate: '2026-09-01',
          lastSeenDate: '2026-09-02',
          lastSeenAt: '2026-09-02T10:00:00+07:00',
        }],
      },
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(pendingResponse), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'active' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...pendingResponse,
        automaticImports: {
          ...pendingResponse.automaticImports,
          pendingSkus: [],
        },
      }), { status: 200 }))

    render(<MonitoringPage />)

    expect(await screen.findByText('NEW-001')).toBeInTheDocument()
    expect(screen.getByText('Modern Trade · HP')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))

    await waitFor(() => expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/api/admin/modern-trades/HP/sku-interests/NEW-001'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ decision: 'accept' }),
      }),
    ))
  })
})
