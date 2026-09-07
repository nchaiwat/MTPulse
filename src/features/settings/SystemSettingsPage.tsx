import { useEffect, useRef, useState } from 'react'
import { Bell, CheckCircle2, Clock3, Eye, EyeOff, RefreshCw, Send, ServerCog, ShieldAlert } from 'lucide-react'
import { FileShareSettingsCard, type FileShareSettingsHandle } from './FileShareSettingsCard'
import {
  defaultTechnicalNotificationSettings,
  checkTechnicalHealth,
  fetchTechnicalNotificationSettings,
  fetchTelegramSettings,
  fetchTelegramToken,
  saveTechnicalNotificationSettings,
  saveTelegramSettings,
  testTelegram,
  type TechnicalMetricCode,
  type TechnicalNotificationSettings,
} from './systemSettingsApi'

type SettingsMessage = { text: string; tone: 'success' | 'error' }

const technicalMetrics: Array<{ code: TechnicalMetricCode; label: string; detail: string }> = [
  { code: 'cpu', label: 'CPU load', detail: 'ภาระการประมวลผลเทียบจำนวน CPU' },
  { code: 'memory', label: 'RAM', detail: 'หน่วยความจำที่ระบบใช้งาน' },
  { code: 'disk', label: 'Disk', detail: 'พื้นที่จัดเก็บของ Server' },
  { code: 'connections', label: 'DB connections', detail: 'Connection เทียบค่าสูงสุดของ PostgreSQL' },
  { code: 'deadTuples', label: 'Dead tuples', detail: 'ข้อมูลเก่าที่รอ PostgreSQL จัดเก็บพื้นที่' },
]

export function SystemSettingsPage({ embedded = false }: { embedded?: boolean }) {
  const [token, setToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [groupId, setGroupId] = useState('')
  const [configured, setConfigured] = useState(false)
  const [notifyManualImport, setNotifyManualImport] = useState(true)
  const [busy, setBusy] = useState<'save' | 'test' | 'reveal' | 'health' | null>(null)
  const [message, setMessage] = useState<SettingsMessage | null>(null)
  const [savedTelegram, setSavedTelegram] = useState({ groupId: '', notifyManualImport: true })
  const [revealedToken, setRevealedToken] = useState('')
  const [fileShareBusy, setFileShareBusy] = useState(false)
  const [technical, setTechnical] = useState<TechnicalNotificationSettings>(defaultTechnicalNotificationSettings)
  const [savedTechnical, setSavedTechnical] = useState<TechnicalNotificationSettings>(defaultTechnicalNotificationSettings)
  const [healthCheck, setHealthCheck] = useState<{ checkedAt: string, overallStatus: string } | null>(null)
  const fileShareRef = useRef<FileShareSettingsHandle>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      fetchTelegramSettings(controller.signal),
      fetchTechnicalNotificationSettings(controller.signal),
    ])
      .then(([settings, technicalSettings]) => {
        setGroupId(settings.groupId)
        setConfigured(settings.telegramConfigured)
        setNotifyManualImport(settings.notifyManualImport)
        setSavedTelegram({
          groupId: settings.groupId,
          notifyManualImport: settings.notifyManualImport,
        })
        setTechnical(technicalSettings)
        setSavedTechnical(technicalSettings)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setMessage({ text: error instanceof Error ? error.message : 'โหลดการตั้งค่าไม่สำเร็จ', tone: 'error' })
      })
    return () => controller.abort()
  }, [])

  const save = async () => {
    const invalidThreshold = technicalMetrics.find(({ code }) => {
      const threshold = technical.thresholds[code]
      return threshold.warning < 0
        || threshold.critical > 100
        || threshold.warning >= threshold.critical
    })
    if (invalidThreshold) {
      setMessage({
        text: `${invalidThreshold.label}: ค่า Warning ต้องน้อยกว่า Critical และอยู่ระหว่าง 0–100%`,
        tone: 'error',
      })
      return
    }
    setBusy('save')
    setMessage(null)
    try {
      let changed = await fileShareRef.current?.saveIfChanged() ?? false
      const telegramChanged = groupId !== savedTelegram.groupId
        || notifyManualImport !== savedTelegram.notifyManualImport
        || Boolean(token.trim() && token !== revealedToken)
      if (telegramChanged) {
        const settings = await saveTelegramSettings({
          botToken: token !== revealedToken ? token : '',
          groupId,
          notifyManualImport,
        })
        setConfigured(settings.telegramConfigured)
        setGroupId(settings.groupId)
        setNotifyManualImport(settings.notifyManualImport)
        setSavedTelegram({
          groupId: settings.groupId,
          notifyManualImport: settings.notifyManualImport,
        })
        setToken('')
        setRevealedToken('')
        setShowToken(false)
        changed = true
      }
      if (JSON.stringify(technical) !== JSON.stringify(savedTechnical)) {
        const settings = await saveTechnicalNotificationSettings(technical)
        setTechnical(settings)
        setSavedTechnical(settings)
        changed = true
      }
      setMessage({
        text: changed ? 'บันทึกการตั้งค่าระบบแล้ว' : 'ไม่มีการตั้งค่าที่เปลี่ยนแปลง',
        tone: 'success',
      })
    } catch (error) {
      setMessage({ text: error instanceof Error ? error.message : 'บันทึกการตั้งค่าไม่สำเร็จ', tone: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const updateThreshold = (
    code: TechnicalMetricCode,
    field: 'warning' | 'critical',
    value: number,
  ) => {
    setTechnical((current) => ({
      ...current,
      thresholds: {
        ...current.thresholds,
        [code]: { ...current.thresholds[code], [field]: value },
      },
    }))
  }

  const sendTest = async () => {
    setBusy('test')
    setMessage(null)
    try {
      setMessage({ text: await testTelegram(), tone: 'success' })
    } catch (error) {
      setMessage({ text: error instanceof Error ? error.message : 'ส่งข้อความทดสอบไม่สำเร็จ', tone: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const toggleToken = async () => {
    if (showToken) {
      setShowToken(false)
      return
    }
    if (token) {
      setShowToken(true)
      return
    }
    setBusy('reveal')
    setMessage(null)
    try {
      const currentToken = await fetchTelegramToken()
      setToken(currentToken)
      setRevealedToken(currentToken)
      setShowToken(true)
    } catch (error) {
      setMessage({ text: error instanceof Error ? error.message : 'เปิดดู Token ไม่สำเร็จ', tone: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const runHealthCheck = async () => {
    setBusy('health')
    setMessage(null)
    try {
      const result = await checkTechnicalHealth()
      setHealthCheck({
        checkedAt: result.checkedAt,
        overallStatus: result.overallStatus,
      })
      setMessage({ text: 'ตรวจสุขภาพระบบและส่ง Telegram แล้ว', tone: 'success' })
    } catch (error) {
      setMessage({ text: error instanceof Error ? error.message : 'ตรวจสุขภาพระบบไม่สำเร็จ', tone: 'error' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className={`system-settings-page ${embedded ? 'system-settings-page-embedded' : 'page-content'}`}>
      <FileShareSettingsCard ref={fileShareRef} disabled={busy !== null} onBusyChange={setFileShareBusy} />
      <section className="telegram-settings" aria-labelledby="telegram-heading">
        <header>
          <div><span className="setting-icon"><Bell size={19} aria-hidden="true" /></span><div><span className="eyebrow">System notification</span><h3 id="telegram-heading">Telegram</h3><p>ส่งเหตุการณ์สำคัญของ MT Pulse ไปยัง Group กลาง</p></div></div>
          <button className="secondary-action" type="button" disabled={!configured || !groupId.trim() || busy !== null} onClick={() => void sendTest()}><Send size={15} />{busy === 'test' ? 'กำลังส่ง…' : 'ทดสอบส่งข้อความเข้า Telegram'}</button>
        </header>
        <div className="telegram-form">
          <label>API Base URL<input type="text" value="https://api.telegram.org" readOnly /></label>
          <label>
            Bot Token ID
            <span className="secret-input">
              <input aria-label="Bot Token ID" type={showToken ? 'text' : 'password'} autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} placeholder={configured ? '********' : 'กรอก Token จาก BotFather'} />
              <button type="button" aria-label={showToken ? 'ซ่อน Bot Token' : 'แสดง Bot Token'} aria-pressed={showToken} disabled={(!configured && !token) || busy !== null} title={showToken ? 'ซ่อน Bot Token' : 'แสดง Bot Token'} onClick={() => void toggleToken()}>{showToken ? <EyeOff size={16} /> : <Eye size={16} />}</button>
            </span>
          </label>
          <label>Group ID<input type="text" value={groupId} onChange={(event) => setGroupId(event.target.value)} placeholder="เช่น -1001234567890" /></label>
          <label className="notification-option"><input type="checkbox" checked={notifyManualImport} onChange={(event) => setNotifyManualImport(event.target.checked)} /><span><strong>Manual Import</strong><small>แจ้งเมื่อการนำเข้าด้วยผู้ใช้สำเร็จหรือไม่สำเร็จ</small></span></label>
        </div>
        <section className="technical-notification-settings" aria-labelledby="technical-notification-heading">
          <header>
            <span className="setting-icon"><ServerCog size={18} aria-hidden="true" /></span>
            <div><span className="eyebrow">Notification policy</span><h4 id="technical-notification-heading">Technical Health</h4><p>รายงานสุขภาพระบบทุกวันและแจ้ง Critical ระหว่างวัน</p></div>
            <button className="secondary-action technical-health-check" type="button" disabled={busy !== null} onClick={() => void runHealthCheck()}>
              <RefreshCw size={15} aria-hidden="true" className={busy === 'health' ? 'is-spinning' : undefined} />
              {busy === 'health' ? 'กำลังตรวจสอบ…' : 'ตรวจสอบและส่งทันที'}
            </button>
          </header>
          {healthCheck && (
            <div className="technical-health-result" data-status={healthCheck.overallStatus} role="status">
              <CheckCircle2 size={15} aria-hidden="true" />
              ส่งผลตรวจล่าสุดแล้ว · {new Date(healthCheck.checkedAt).toLocaleString('th-TH')}
            </div>
          )}
          <div className="technical-policy-grid">
            <label className="technical-toggle"><input type="checkbox" checked={technical.dailyEnabled} onChange={(event) => setTechnical((current) => ({ ...current, dailyEnabled: event.target.checked }))} /><span><Clock3 size={16} aria-hidden="true" /><strong>Daily report</strong><small>ส่งทุกวันแม้ระบบปกติ</small></span></label>
            <label>เวลารายงาน<input aria-label="เวลารายงาน Technical Health" type="time" value={technical.dailyTime} disabled={!technical.dailyEnabled} onChange={(event) => setTechnical((current) => ({ ...current, dailyTime: event.target.value }))} /></label>
            <label className="technical-toggle"><input type="checkbox" checked={technical.criticalEnabled} onChange={(event) => setTechnical((current) => ({ ...current, criticalEnabled: event.target.checked }))} /><span><ShieldAlert size={16} aria-hidden="true" /><strong>Critical alert</strong><small>แจ้งทันทีเมื่อเกิน Threshold</small></span></label>
            <label>Cooldown (นาที)<input aria-label="Critical alert cooldown" type="number" min="5" max="1440" value={technical.cooldownMinutes} disabled={!technical.criticalEnabled} onChange={(event) => setTechnical((current) => ({ ...current, cooldownMinutes: event.target.valueAsNumber || 5 }))} /></label>
            <label className="technical-toggle"><input type="checkbox" checked={technical.recoveryEnabled} disabled={!technical.criticalEnabled} onChange={(event) => setTechnical((current) => ({ ...current, recoveryEnabled: event.target.checked }))} /><span><strong>Recovery</strong><small>แจ้งเมื่อสถานะกลับสู่ปกติ</small></span></label>
          </div>
          <div className="technical-threshold-table-wrap">
            <table className="technical-threshold-table">
              <thead><tr><th>Metric</th><th>Warning</th><th>Critical</th><th>หน่วย</th></tr></thead>
              <tbody>
                {technicalMetrics.map((metric) => (
                  <tr key={metric.code}>
                    <td><strong>{metric.label}</strong><small>{metric.detail}</small></td>
                    <td><input aria-label={`${metric.label} Warning`} type="number" min="0" max="100" step="0.1" value={technical.thresholds[metric.code].warning} onChange={(event) => updateThreshold(metric.code, 'warning', event.target.valueAsNumber || 0)} /></td>
                    <td><input aria-label={`${metric.label} Critical`} type="number" min="0" max="100" step="0.1" value={technical.thresholds[metric.code].critical} onChange={(event) => updateThreshold(metric.code, 'critical', event.target.valueAsNumber || 0)} /></td>
                    <td>%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
      <div className="system-settings-savebar">
        {message && <div className="settings-message" data-tone={message.tone} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div>}
        <button className="primary-action" type="button" disabled={busy !== null || fileShareBusy} onClick={() => void save()}>{busy === 'save' ? 'กำลังบันทึก…' : 'บันทึกการตั้งค่าระบบ'}</button>
      </div>
    </div>
  )
}
