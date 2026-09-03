import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FileShareSettingsCard } from './FileShareSettingsCard'

describe('FileShareSettingsCard progress', () => {
  afterEach(() => vi.restoreAllMocks())

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
})
