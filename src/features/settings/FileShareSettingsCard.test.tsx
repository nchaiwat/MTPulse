import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FileShareSettingsCard } from './FileShareSettingsCard'

describe('FileShareSettingsCard progress', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders the independent HH source profile in the HH settings scope', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      baseUnc: '\\\\server\\share',
      domain: 'WA',
      username: 'user',
      passwordConfigured: true,
      passwordMasked: '********',
      lastTestAt: null,
      lastTestStatus: null,
      lastTestResults: [],
      profiles: [{
        code: 'HH', name: 'HomeHub', subfolder: 'HomeHub', enabled: true,
        fullPath: '\\\\server\\share\\HomeHub', scheduleEnabled: false,
        scheduleTime: null, initialScanCompleted: false, nextRunAt: null,
        sourceGroup: 'HH', sharedProfileOwner: true, sharedWith: [], lastRun: null,
      }],
    }), { status: 200 }))

    const { container } = render(
      <FileShareSettingsCard view="profile" profileCode="HH" />,
    )

    expect(await screen.findByRole('heading', { name: 'FileShare · HH' })).toBeInTheDocument()
    expect(screen.getByText('HomeHub')).toBeInTheDocument()
    expect(screen.getByDisplayValue('HomeHub')).toBeInTheDocument()
    expect(container.querySelectorAll('article[data-source-group="HH"]')).toHaveLength(1)
  })

  it('shows live progress, activity and the latest issue for an active run', async () => {
    const now = Date.now()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(
      JSON.stringify({
        baseUnc: '\\\\server\\share',
        domain: 'WA',
        username: 'user',
        passwordConfigured: true,
        passwordMasked: '********',
        lastTestAt: null,
        lastTestStatus: null,
        lastTestResults: [],
        profiles: [{
          code: 'TWD',
          name: 'Thai Watsadu',
          subfolder: 'TWD',
          enabled: true,
          fullPath: '\\\\server\\share\\TWD',
          scheduleEnabled: false,
          scheduleTime: null,
          initialScanCompleted: false,
          nextRunAt: null,
          lastRun: {
            runId: 1,
            mtCode: 'TWD',
            mtName: 'Thai Watsadu',
            trigger: 'manual',
            mode: 'scan',
            status: 'running',
            requestedBy: 'admin',
            scheduledLocalDate: null,
            requestedAt: new Date(now - 60 * 60 * 1000).toISOString(),
            startedAt: new Date(now - 60 * 60 * 1000).toISOString(),
            finishedAt: null,
            counts: {
              found: 565,
              imported: 0,
              skipped: 12,
              ready: 400,
              pending: 0,
              failed: 7,
            },
            progress: {
              phase: 'processing',
              processed: 419,
              total: 565,
              percent: 74.2,
              lastProcessedFile: 'latest.xls',
              lastProcessedPath: '\\\\server\\share\\TWD\\2026-03-09\\latest.xls',
              lastActivityAt: new Date(now - 10_000).toISOString(),
              counts: {
                found: 565,
                imported: 0,
                skipped: 12,
                ready: 400,
                pending: 0,
                failed: 7,
              },
              recentIssues: [{
                filename: 'empty.xls',
                status: 'failed',
                message: 'File size is 0 bytes',
              }],
            },
            message: 'กำลังตรวจไฟล์ 420/565 · current.xls',
            error: null,
            results: [],
          },
        }],
      }),
      { status: 200 },
    ))

    render(<FileShareSettingsCard />)

    expect(await screen.findByText('กำลังตรวจสอบไฟล์')).toBeInTheDocument()
    expect(screen.getByText('419 / 565 ไฟล์')).toBeInTheDocument()
    expect(screen.getByText('พร้อม 400')).toBeInTheDocument()
    expect(screen.getByText('ผิดพลาด 7')).toBeInTheDocument()
    expect(screen.getByText('latest.xls')).toBeInTheDocument()
    expect(screen.getByText(/empty\.xls/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '419')
  })

  it('groups HP and MH under one shared source while keeping per-MT counts', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(
      JSON.stringify({
        baseUnc: '\\\\server\\share',
        domain: 'WA',
        username: 'user',
        passwordConfigured: true,
        passwordMasked: '********',
        lastTestAt: null,
        lastTestStatus: null,
        lastTestResults: [],
        profiles: [
          {
            code: 'HP', name: 'HomePro', subfolder: 'HP_MH', enabled: true,
            fullPath: '\\\\server\\share\\HP_MH', scheduleEnabled: true,
            scheduleTime: '07:15', initialScanCompleted: true, nextRunAt: null,
            sourceGroup: 'HP_MH', sharedProfileOwner: true, sharedWith: ['MH'],
            lastRun: {
              runId: 7, mtCode: 'HP', mtName: 'HomePro', trigger: 'scheduled',
              mode: 'import', status: 'success', requestedBy: 'worker',
              scheduledLocalDate: '2026-09-07', requestedAt: '2026-09-07T00:15:00Z',
              startedAt: '2026-09-07T00:15:01Z', finishedAt: '2026-09-07T00:16:00Z',
              counts: { found: 1, imported: 1, skipped: 0, ready: 0, pending: 0, failed: 0 },
              progress: null, message: 'นำเข้า 1 คู่', error: null,
              results: [{
                status: 'imported', message: 'สำเร็จ',
                mt: {
                  HP: { rows: 39, newPendingSkus: 2 },
                  MH: { rows: 26, newPendingSkus: 1 },
                },
              }],
            },
          },
          {
            code: 'MH', name: 'MegaHome', subfolder: 'HP_MH', enabled: true,
            fullPath: '\\\\server\\share\\HP_MH', scheduleEnabled: true,
            scheduleTime: '07:15', initialScanCompleted: true, nextRunAt: null,
            sourceGroup: 'HP_MH', sharedProfileOwner: false, sharedWith: ['HP'],
            lastRun: null,
          },
        ],
      }),
      { status: 200 },
    ))

    const { container } = render(<FileShareSettingsCard />)

    expect(await screen.findByText('HomePro Group — Shared Source')).toBeInTheDocument()
    expect(screen.getByText('MegaHome')).toBeInTheDocument()
    expect(screen.getByText('39')).toBeInTheDocument()
    expect(screen.getByText('26')).toBeInTheDocument()
    expect(container.querySelectorAll('article[data-source-group="HP_MH"]')).toHaveLength(1)
  })
})
