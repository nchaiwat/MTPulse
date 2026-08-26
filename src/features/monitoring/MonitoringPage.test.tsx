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
    latestImport: {
      batchId: 7,
      dataDate: '2026-08-22',
      status: 'imported',
      finishedAt: '2026-08-25T03:00:00+00:00',
      rowCount: 12590,
      warningCount: 0,
    },
    modernTrades: [{ code: 'TWD', name: 'ไทวัสดุ', latestDataDate: '2026-08-22', lagDays: 3 }],
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
  }],
}

describe('MonitoringPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows current health, database workload, slow queries, and refreshes on demand', async () => {
    const onOpenImports = vi.fn()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }))

    render(<MonitoringPage onOpenImports={onOpenImports} />)

    expect(await screen.findByRole('heading', { name: 'สถานะระบบ' })).toBeInTheDocument()
    expect(screen.getByText('23/08/2026')).toBeInTheDocument()
    expect(screen.getAllByText('22/08/2026')).toHaveLength(2)
    expect(screen.getAllByText('175,717')).toHaveLength(2)
    expect(screen.getByText('Import Batch 18 มีคำเตือน 1 รายการ')).toBeInTheDocument()
    expect(screen.getByText('Stock On Hand: calculated=77904.0, source=77379')).toBeInTheDocument()
    expect(screen.getByText('SELECT * FROM sales_inventory_facts')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'ประวัติสถานะรายวัน' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'ดำเนินการแก้ไข' }))
    expect(onOpenImports).toHaveBeenCalledWith(18)

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/monitoring/refresh'),
      expect.objectContaining({ method: 'POST' }),
    ))
  })
})
