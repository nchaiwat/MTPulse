import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  EyeOff,
  LoaderCircle,
  Play,
  PlugZap,
  ScanSearch,
  X,
  XCircle,
} from 'lucide-react'
import {
  fetchFileSharePassword,
  fetchFileShareSettings,
  runModernTradeNow,
  saveFileShareSettings,
  testFileShare,
  type FileShareProfile,
  type FileShareTestResult,
  type ImportRun,
} from './fileShareSettingsApi'
import { runProgressView } from './runProgress'

type SettingsMessage = { text: string; tone: 'success' | 'error' }

const defaultBaseUnc = '\\\\WA-NAS-IT03\\FileShare-2\\SaleOut_RPT'

function formatTestTime(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export interface FileShareSettingsHandle {
  saveIfChanged: () => Promise<boolean>
}

function formatRunTime(value: string | null) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return new Intl.DateTimeFormat('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
}

function formatRunClock(value: string | null) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return new Intl.DateTimeFormat('th-TH', {
    timeZone: 'Asia/Bangkok',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(parsed)
}

const activeRunStatuses = new Set(['queued', 'running'])

function runStatus(run: ImportRun | null) {
  if (!run) return { tone: 'idle', label: 'ยังไม่เคยทำงาน' }
  if (run.status === 'queued') return { tone: 'active', label: 'รอเริ่มงาน' }
  if (run.status === 'running') return { tone: 'active', label: 'กำลังประมวลผล' }
  if (run.status === 'success') return { tone: 'success', label: 'สำเร็จ' }
  if (run.status === 'success_with_warnings') return { tone: 'warning', label: 'สำเร็จ มีรายการรอตรวจสอบ' }
  return { tone: 'error', label: 'ไม่สำเร็จ' }
}

function settingsSnapshot(input: {
  baseUnc: string
  domain: string
  username: string
  profiles: FileShareProfile[]
}) {
  return JSON.stringify({
    baseUnc: input.baseUnc,
    domain: input.domain,
    username: input.username,
    profiles: input.profiles.map(({ code, subfolder, enabled, scheduleEnabled, scheduleTime }) => ({
      code,
      subfolder,
      enabled,
      scheduleEnabled,
      scheduleTime,
    })),
  })
}

export const FileShareSettingsCard = forwardRef<FileShareSettingsHandle, {
  disabled?: boolean
  onBusyChange?: (busy: boolean) => void
}>(function FileShareSettingsCard({ disabled = false, onBusyChange }, ref) {
  const [baseUnc, setBaseUnc] = useState('')
  const [domain, setDomain] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [passwordConfigured, setPasswordConfigured] = useState(false)
  const [profiles, setProfiles] = useState<FileShareProfile[]>([])
  const [lastTestAt, setLastTestAt] = useState<string | null>(null)
  const [lastTestStatus, setLastTestStatus] = useState<string | null>(null)
  const [results, setResults] = useState<FileShareTestResult[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<SettingsMessage | null>(null)
  const [savedSnapshot, setSavedSnapshot] = useState('')
  const [confirmProfile, setConfirmProfile] = useState<FileShareProfile | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchFileShareSettings(controller.signal)
      .then((settings) => {
        setBaseUnc(settings.baseUnc ?? '')
        setDomain(settings.domain ?? '')
        setUsername(settings.username ?? '')
        setPasswordConfigured(settings.passwordConfigured ?? false)
        setProfiles(settings.profiles ?? [])
        setLastTestAt(settings.lastTestAt ?? null)
        setLastTestStatus(settings.lastTestStatus ?? null)
        setResults(settings.lastTestResults ?? [])
        setSavedSnapshot(settingsSnapshot(settings))
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage({
            text: error instanceof Error ? error.message : 'โหลดการตั้งค่า FileShare ไม่สำเร็จ',
            tone: 'error',
          })
        }
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    onBusyChange?.(busy !== null)
  }, [busy, onBusyChange])

  useEffect(() => {
    const hasActiveRun = profiles.some((profile) => (
      profile.lastRun && activeRunStatuses.has(profile.lastRun.status)
    ))
    if (!hasActiveRun) return
    const timer = window.setInterval(() => {
      fetchFileShareSettings()
        .then((settings) => {
          setProfiles((current) => current.map((profile) => {
            const fresh = settings.profiles.find((item) => item.code === profile.code)
            return fresh ? {
              ...profile,
              initialScanCompleted: fresh.initialScanCompleted,
              lastRun: fresh.lastRun,
              nextRunAt: fresh.nextRunAt,
            } : profile
          }))
        })
        .catch(() => undefined)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [profiles])

  useEffect(() => {
    if (!confirmProfile) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setConfirmProfile(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [confirmProfile])

  const payload = () => ({ baseUnc, domain, username, password, profiles })

  const saveIfChanged = async () => {
    const currentSnapshot = settingsSnapshot({ baseUnc, domain, username, profiles })
    if (!password.trim() && currentSnapshot === savedSnapshot) return false
    setBusy('save')
    setMessage(null)
    try {
      const settings = await saveFileShareSettings(payload())
      setBaseUnc(settings.baseUnc)
      setDomain(settings.domain)
      setUsername(settings.username)
      setPasswordConfigured(settings.passwordConfigured)
      setProfiles(settings.profiles)
      setSavedSnapshot(settingsSnapshot(settings))
      setPassword('')
      setShowPassword(false)
      return true
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : 'บันทึกการตั้งค่า FileShare ไม่สำเร็จ',
        tone: 'error',
      })
      throw error
    } finally {
      setBusy(null)
    }
  }

  useImperativeHandle(ref, () => ({ saveIfChanged }))

  const test = async () => {
    setBusy('test')
    setMessage(null)
    try {
      const response = await testFileShare(payload())
      setResults(response.results)
      setLastTestStatus(response.status)
      setLastTestAt(new Date().toISOString())
      setMessage({
        text: response.message,
        tone: response.status === 'success' ? 'success' : 'error',
      })
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : 'ทดสอบ FileShare ไม่สำเร็จ',
        tone: 'error',
      })
    } finally {
      setBusy(null)
    }
  }

  const togglePassword = async () => {
    if (showPassword) {
      setShowPassword(false)
      return
    }
    if (password) {
      setShowPassword(true)
      return
    }
    setBusy('reveal')
    setMessage(null)
    try {
      setPassword(await fetchFileSharePassword())
      setShowPassword(true)
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : 'เปิดดู Password ไม่สำเร็จ',
        tone: 'error',
      })
    } finally {
      setBusy(null)
    }
  }

  const updateProfile = (code: string, update: Partial<FileShareProfile>) => {
    setProfiles((current) => current.map((profile) => (
      profile.code === code ? { ...profile, ...update } : profile
    )))
  }

  const runNow = async (profile: FileShareProfile) => {
    setConfirmProfile(null)
    setBusy(`run-${profile.code}`)
    setMessage(null)
    try {
      const run = await runModernTradeNow(profile.code)
      updateProfile(profile.code, { lastRun: run })
      setMessage({
        text: run.mode === 'scan'
          ? 'เริ่ม Initial Scan แล้ว ระบบจะสำรวจไฟล์โดยยังไม่นำเข้าข้อมูล'
          : `เริ่ม Run ${run.runId} แล้ว ระบบจะข้ามไฟล์ที่เคยนำเข้าโดยอัตโนมัติ`,
        tone: 'success',
      })
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : 'เริ่ม Run ไม่สำเร็จ',
        tone: 'error',
      })
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="fileshare-settings" aria-labelledby="fileshare-heading">
      <header>
        <div>
          <span className="setting-icon"><Database size={19} aria-hidden="true" /></span>
          <div>
            <span className="eyebrow">Data connection</span>
            <h3 id="fileshare-heading">FileShare</h3>
            <p>กำหนด UNC และ Account กลางสำหรับอ่านไฟล์ของทุก Modern Trade</p>
          </div>
        </div>
        <button className="secondary-action" type="button" disabled={disabled || busy !== null || !baseUnc.trim() || !username.trim()} onClick={() => void test()}>
          <PlugZap size={15} />{busy === 'test' ? 'กำลังทดสอบ…' : 'ทดสอบการเชื่อมต่อ'}
        </button>
      </header>

      <div className="fileshare-form">
        <label className="fileshare-base">
          Base UNC
          <input type="text" value={baseUnc} onChange={(event) => setBaseUnc(event.target.value)} placeholder={defaultBaseUnc} />
          <small>Path กลางร่วมกันของทุก MT เช่น {defaultBaseUnc}</small>
        </label>
        <label>Domain (AD)<input type="text" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="เช่น WA" /><small>ระบบจะใช้รูปแบบ WA\username; หาก User เป็น name@domain ให้เว้นช่องนี้</small></label>
        <label>User<input type="text" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Account สำหรับอ่าน FileShare" /></label>
        <label>
          Password
          <span className="secret-input">
            <input aria-label="FileShare Password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={passwordConfigured ? '********' : 'กรอก Password'} />
            <button type="button" aria-label={showPassword ? 'ซ่อน FileShare Password' : 'แสดง FileShare Password'} aria-pressed={showPassword} disabled={disabled || (!passwordConfigured && !password) || busy !== null} onClick={() => void togglePassword()}>
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </span>
        </label>
      </div>

      <div className="fileshare-profiles">
        <div className="fileshare-profile-heading">
          <div><strong>โฟลเดอร์ของ Modern Trade</strong><small>ระบบจะต่อ Subfolder กับ Base UNC อัตโนมัติ</small></div>
          {lastTestAt && <span data-status={lastTestStatus ?? undefined}>ทดสอบล่าสุด {formatTestTime(lastTestAt)}</span>}
        </div>
        {profiles.length === 0 ? <p className="empty-fileshare-profile">ยังไม่มี Modern Trade ในระบบ</p> : profiles.map((profile) => {
          const result = results.find((item) => item.code === profile.code)
          const fullPath = baseUnc && profile.subfolder
            ? baseUnc.replace(/[\\/]+$/, '') + '\\' + profile.subfolder.replace(/^[\\/]+/, '')
            : '—'
          const currentRunStatus = runStatus(profile.lastRun)
          const isRunActive = Boolean(
            profile.lastRun && activeRunStatuses.has(profile.lastRun.status),
          )
          const progress = isRunActive ? profile.lastRun?.progress : null
          const progressView = isRunActive && profile.lastRun
            ? runProgressView(profile.lastRun)
            : null
          const displayedRunTone = progressView?.isStale
            ? 'warning'
            : currentRunStatus.tone
          const hasUnsavedSettings = Boolean(
            password.trim()
            || settingsSnapshot({ baseUnc, domain, username, profiles }) !== savedSnapshot
          )
          return (
            <article key={profile.code}>
              <div className="fileshare-profile-source">
                <label className="fileshare-profile-toggle">
                  <input type="checkbox" checked={profile.enabled} onChange={(event) => updateProfile(profile.code, { enabled: event.target.checked })} />
                  <span><strong>{profile.name}</strong><small>{profile.code}</small></span>
                </label>
                <label>Subfolder<input type="text" value={profile.subfolder} onChange={(event) => updateProfile(profile.code, { subfolder: event.target.value })} placeholder={profile.code} /></label>
                <div className="fileshare-path"><span>Full Path</span><code title={fullPath}>{fullPath}</code></div>
                <div className="fileshare-result" data-status={result?.status}>
                  {result?.status === 'success' ? <CheckCircle2 size={16} /> : result ? <XCircle size={16} /> : null}
                  <span>{result?.message ?? (profile.enabled ? 'ยังไม่ได้ทดสอบ' : 'ปิดใช้งาน')}</span>
                </div>
              </div>
              <div className="fileshare-profile-automation">
                <div className="schedule-control">
                  <label className="schedule-toggle">
                    <input
                      type="checkbox"
                      checked={profile.scheduleEnabled}
                      disabled={!profile.enabled || profile.code !== 'TWD'}
                      onChange={(event) => updateProfile(profile.code, {
                        scheduleEnabled: event.target.checked,
                      })}
                    />
                    <span><strong>Schedule รายวัน</strong><small>เวลา Asia/Bangkok</small></span>
                  </label>
                  <label className="schedule-time">
                    <Clock3 size={15} aria-hidden="true" />
                    <input
                      aria-label={`เวลา Schedule ${profile.code}`}
                      type="time"
                      value={profile.scheduleTime ?? ''}
                      disabled={!profile.enabled || !profile.scheduleEnabled || profile.code !== 'TWD'}
                      onChange={(event) => updateProfile(profile.code, {
                        scheduleTime: event.target.value || null,
                      })}
                    />
                  </label>
                </div>
                <div className="run-status" data-tone={displayedRunTone}>
                  <span className="run-status-icon">
                    {isRunActive
                      ? <LoaderCircle size={16} className="spin" />
                      : profile.lastRun?.status === 'success'
                        ? <CheckCircle2 size={16} />
                        : profile.lastRun?.status === 'success_with_warnings'
                          ? <AlertTriangle size={16} />
                          : profile.lastRun?.status === 'failed'
                            ? <XCircle size={16} />
                            : <ScanSearch size={16} />}
                  </span>
                  <span className="run-status-copy">
                    <strong>{currentRunStatus.label}</strong>
                    <small>
                      {profile.lastRun
                        ? `Run ${profile.lastRun.runId} · ${formatRunTime(profile.lastRun.finishedAt ?? profile.lastRun.requestedAt)}`
                        : 'ครั้งแรกจะเป็น Initial Scan เท่านั้น'}
                    </small>
                    {profile.lastRun?.message && <small>{profile.lastRun.message}</small>}
                    {profile.lastRun?.error && <small>{profile.lastRun.error}</small>}
                  </span>
                  {isRunActive && progressView && (
                    <div
                      className="run-progress"
                      data-stale={progressView.isStale || undefined}
                    >
                      <div className="run-progress-heading">
                        <span>{progressView.phaseLabel}</span>
                        <strong>
                          {progress?.total
                            ? `${progress.processed.toLocaleString()} / ${progress.total.toLocaleString()} ไฟล์`
                            : 'กำลังนับไฟล์…'}
                        </strong>
                      </div>
                      <div
                        className="run-progress-track"
                        data-indeterminate={!progress?.total || undefined}
                        role="progressbar"
                        aria-label="ความคืบหน้า Import Run"
                        aria-valuemin={0}
                        aria-valuemax={progress?.total || undefined}
                        aria-valuenow={progress?.total ? progress.processed : undefined}
                        aria-valuetext={progress?.total
                          ? `${progress.percent}% · ${progress.processed} จาก ${progress.total} ไฟล์`
                          : 'กำลังสำรวจรายการไฟล์'}
                      >
                        <span
                          style={progress?.total
                            ? { transform: `scaleX(${Math.min(100, progress.percent) / 100})` }
                            : undefined}
                        />
                      </div>
                      <div className="run-progress-meta">
                        <span>ทำงานมาแล้ว <strong>{progressView.elapsedLabel}</strong></span>
                        {progressView.etaLabel && (
                          <span>คาดว่าเหลือ <strong>{progressView.etaLabel}</strong></span>
                        )}
                        <span>
                          อัปเดตล่าสุด{' '}
                          <strong>{formatRunClock(progress?.lastActivityAt ?? null)}</strong>
                        </span>
                      </div>
                      {progress && (
                        <>
                          <div className="run-progress-counts">
                            <span data-tone="ready">พร้อม {progress.counts.ready.toLocaleString()}</span>
                            <span>ข้าม {progress.counts.skipped.toLocaleString()}</span>
                            <span data-tone={progress.counts.pending ? 'warning' : undefined}>
                              รอตรวจ {progress.counts.pending.toLocaleString()}
                            </span>
                            <span data-tone={progress.counts.failed ? 'error' : undefined}>
                              ผิดพลาด {progress.counts.failed.toLocaleString()}
                            </span>
                          </div>
                          {progress.lastProcessedFile && (
                            <p className="run-progress-file" title={progress.lastProcessedPath ?? undefined}>
                              <span>ไฟล์ล่าสุด</span>
                              <strong>{progress.lastProcessedFile}</strong>
                            </p>
                          )}
                          {progress.recentIssues[0] && (
                            <p className="run-progress-issue">
                              <AlertTriangle size={13} aria-hidden="true" />
                              <span>
                                <strong>{progress.recentIssues[0].filename}</strong>
                                {' · '}
                                {progress.recentIssues[0].message ?? 'รอตรวจสอบ'}
                              </span>
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
                <div className="run-actions">
                  <span>
                    {profile.scheduleEnabled && profile.nextRunAt
                      ? `ครั้งถัดไป ${formatRunTime(profile.nextRunAt)}`
                      : 'Schedule ปิดอยู่'}
                  </span>
                  <button
                    className="secondary-action run-now-action"
                    type="button"
                    disabled={
                      disabled
                      || busy !== null
                      || !profile.enabled
                      || profile.code !== 'TWD'
                      || isRunActive
                      || hasUnsavedSettings
                    }
                    title={hasUnsavedSettings ? 'กรุณาบันทึกการตั้งค่าก่อน Run' : undefined}
                    onClick={() => setConfirmProfile(profile)}
                  >
                    <Play size={14} fill="currentColor" />
                    {profile.initialScanCompleted ? 'Run ทันที' : 'Initial Scan'}
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {message && <div className="settings-message" data-tone={message.tone} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div>}
      {confirmProfile && (
        <div className="run-confirm-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setConfirmProfile(null)
        }}>
          <div className="run-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="run-confirm-title">
            <button className="run-confirm-close" type="button" aria-label="ปิด" onClick={() => setConfirmProfile(null)}>
              <X size={17} />
            </button>
            <span className="run-confirm-icon">
              {confirmProfile.initialScanCompleted ? <Play size={20} /> : <ScanSearch size={20} />}
            </span>
            <span className="eyebrow">{confirmProfile.code} · Automatic import</span>
            <h4 id="run-confirm-title">
              {confirmProfile.initialScanCompleted ? 'ยืนยัน Run ทันที' : 'ยืนยัน Initial Scan'}
            </h4>
            <p>
              {confirmProfile.initialScanCompleted
                ? 'ระบบจะตรวจทุกไฟล์ใน Path แต่จะอ่านละเอียดเฉพาะไฟล์ใหม่หรือไฟล์ที่เปลี่ยน และข้ามข้อมูลที่เคยนำเข้าแล้ว'
                : 'ระบบจะสำรวจและบันทึกรายการไฟล์ทั้งหมดก่อน โดยยังไม่นำข้อมูลเข้าและไม่แก้ข้อมูลเดิม'}
            </p>
            <div className="run-confirm-note">
              <AlertTriangle size={16} />
              หากพบวันที่ซ้ำแต่ไฟล์ต่างกัน หรือมีคำเตือน ระบบจะพักรายการนั้นไว้ตรวจสอบและทำไฟล์อื่นต่อ
            </div>
            <div className="run-confirm-actions">
              <button type="button" className="secondary-action" onClick={() => setConfirmProfile(null)}>ยกเลิก</button>
              <button type="button" className="primary-action" autoFocus onClick={() => void runNow(confirmProfile)}>
                {confirmProfile.initialScanCompleted ? 'ยืนยัน Run' : 'เริ่ม Initial Scan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
})
