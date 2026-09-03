import { describe, expect, it } from 'vitest'

import type { ImportRun } from './fileShareSettingsApi'
import { formatCompactDuration, runProgressView } from './runProgress'

const run: ImportRun = {
  runId: 1,
  mtCode: 'TWD',
  mtName: 'Thai Watsadu',
  trigger: 'manual',
  mode: 'scan',
  status: 'running',
  requestedBy: 'admin',
  scheduledLocalDate: null,
  requestedAt: '2026-09-03T01:21:00Z',
  startedAt: '2026-09-03T01:21:00Z',
  finishedAt: null,
  counts: {
    found: 565,
    imported: 0,
    skipped: 17,
    ready: 400,
    pending: 0,
    failed: 7,
  },
  progress: {
    phase: 'processing',
    processed: 424,
    total: 565,
    percent: 75,
    lastProcessedFile: 'file.xls',
    lastProcessedPath: '\\\\server\\share\\TWD\\2026-03-10\\file.xls',
    lastActivityAt: '2026-09-03T03:20:00Z',
    counts: {
      found: 565,
      imported: 0,
      skipped: 17,
      ready: 400,
      pending: 0,
      failed: 7,
    },
    recentIssues: [],
  },
  message: 'กำลังตรวจไฟล์ 425/565 · file.xls',
  error: null,
  results: [],
}

describe('run progress presentation', () => {
  it('formats elapsed time and estimates the remaining duration', () => {
    const view = runProgressView(run, new Date('2026-09-03T03:21:00Z').getTime())

    expect(view.phaseLabel).toBe('กำลังตรวจสอบไฟล์')
    expect(view.elapsedLabel).toBe('2 ชม.')
    expect(view.etaLabel).toBe('40 นาที')
    expect(view.isStale).toBe(false)
  })

  it('flags a run with no recent file activity', () => {
    const view = runProgressView(run, new Date('2026-09-03T03:26:01Z').getTime())

    expect(view.phaseLabel).toBe('ไม่มีความคืบหน้าเกิน 5 นาที')
    expect(view.isStale).toBe(true)
  })

  it('formats short and hour-long durations compactly', () => {
    expect(formatCompactDuration(42)).toBe('42 วินาที')
    expect(formatCompactDuration(5_460)).toBe('1 ชม. 31 นาที')
  })
})
