import type { ImportRun } from './fileShareSettingsApi'

export const staleRunThresholdMs = 5 * 60 * 1000

function secondsBetween(start: string | null, endMs: number) {
  if (!start) return 0
  const startMs = new Date(start).getTime()
  if (Number.isNaN(startMs)) return 0
  return Math.max(0, Math.floor((endMs - startMs) / 1000))
}

export function formatCompactDuration(seconds: number) {
  const safeSeconds = Math.max(0, Math.round(seconds))
  if (safeSeconds < 60) return `${safeSeconds} วินาที`
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  if (hours === 0) return `${minutes} นาที`
  return minutes ? `${hours} ชม. ${minutes} นาที` : `${hours} ชม.`
}

export function runProgressView(run: ImportRun, nowMs = Date.now()) {
  const progress = run.progress
  const elapsedSeconds = secondsBetween(run.startedAt ?? run.requestedAt, nowMs)
  const activityAt = progress?.lastActivityAt ?? run.startedAt ?? run.requestedAt
  const lastActivityMs = activityAt ? new Date(activityAt).getTime() : Number.NaN
  const isStale = run.status === 'running'
    && !Number.isNaN(lastActivityMs)
    && nowMs - lastActivityMs > staleRunThresholdMs
  const remaining = progress ? Math.max(0, progress.total - progress.processed) : 0
  const etaSeconds = progress && progress.processed > 0 && remaining > 0
    ? Math.ceil((elapsedSeconds / progress.processed * remaining) / 60) * 60
    : null
  const phaseLabel = isStale
    ? 'ไม่มีความคืบหน้าเกิน 5 นาที'
    : progress?.phase === 'queued'
      ? 'กำลังรอ Worker'
      : progress?.phase === 'discovering'
        ? 'กำลังสำรวจรายการไฟล์'
        : progress && progress.total > 0 && progress.processed >= progress.total
          ? 'กำลังสรุปผล'
          : 'กำลังตรวจสอบไฟล์'

  return {
    elapsedLabel: formatCompactDuration(elapsedSeconds),
    etaLabel: etaSeconds === null ? null : formatCompactDuration(etaSeconds),
    isStale,
    phaseLabel,
  }
}
