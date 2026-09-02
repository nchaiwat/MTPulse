import { useEffect, useRef, useState } from 'react'
import { Bell, Eye, EyeOff, Send } from 'lucide-react'
import { FileShareSettingsCard, type FileShareSettingsHandle } from './FileShareSettingsCard'
import { fetchTelegramSettings, fetchTelegramToken, saveTelegramSettings, testTelegram } from './systemSettingsApi'

type SettingsMessage = { text: string; tone: 'success' | 'error' }

export function SystemSettingsPage({ embedded = false }: { embedded?: boolean }) {
  const [token, setToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [groupId, setGroupId] = useState('')
  const [configured, setConfigured] = useState(false)
  const [notifyManualImport, setNotifyManualImport] = useState(true)
  const [busy, setBusy] = useState<'save' | 'test' | 'reveal' | null>(null)
  const [message, setMessage] = useState<SettingsMessage | null>(null)
  const [savedTelegram, setSavedTelegram] = useState({ groupId: '', notifyManualImport: true })
  const [revealedToken, setRevealedToken] = useState('')
  const [fileShareBusy, setFileShareBusy] = useState(false)
  const fileShareRef = useRef<FileShareSettingsHandle>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchTelegramSettings(controller.signal)
      .then((settings) => {
        setGroupId(settings.groupId)
        setConfigured(settings.telegramConfigured)
        setNotifyManualImport(settings.notifyManualImport)
        setSavedTelegram({
          groupId: settings.groupId,
          notifyManualImport: settings.notifyManualImport,
        })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setMessage({ text: error instanceof Error ? error.message : 'โหลดการตั้งค่าไม่สำเร็จ', tone: 'error' })
      })
    return () => controller.abort()
  }, [])

  const save = async () => {
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
      </section>
      <div className="system-settings-savebar">
        {message && <div className="settings-message" data-tone={message.tone} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div>}
        <button className="primary-action" type="button" disabled={busy !== null || fileShareBusy} onClick={() => void save()}>{busy === 'save' ? 'กำลังบันทึก…' : 'บันทึกการตั้งค่าระบบ'}</button>
      </div>
    </div>
  )
}
