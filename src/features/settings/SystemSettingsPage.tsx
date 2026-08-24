import { useEffect, useState } from 'react'
import { Bell, Eye, EyeOff, Send, ShieldCheck } from 'lucide-react'
import { fetchTelegramSettings, saveTelegramSettings, testTelegram } from './systemSettingsApi'

export function SystemSettingsPage({ embedded = false }: { embedded?: boolean }) {
  const [token, setToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [groupId, setGroupId] = useState('')
  const [configured, setConfigured] = useState(false)
  const [notifyManualImport, setNotifyManualImport] = useState(true)
  const [busy, setBusy] = useState<'save' | 'test' | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchTelegramSettings(controller.signal)
      .then((settings) => {
        setGroupId(settings.groupId)
        setConfigured(settings.telegramConfigured)
        setNotifyManualImport(settings.notifyManualImport)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : 'โหลดการตั้งค่าไม่สำเร็จ')
      })
    return () => controller.abort()
  }, [])

  const save = async () => {
    setBusy('save')
    setMessage(null)
    try {
      const settings = await saveTelegramSettings({ botToken: token, groupId, notifyManualImport })
      setConfigured(settings.telegramConfigured)
      setToken('')
      setShowToken(false)
      setMessage('บันทึกแล้ว ระบบจะใช้ Token ที่บันทึกไว้กับ Group / Chat ID ' + settings.groupId)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'บันทึกการตั้งค่าไม่สำเร็จ')
    } finally {
      setBusy(null)
    }
  }

  const sendTest = async () => {
    setBusy('test')
    setMessage(null)
    try {
      setMessage(await testTelegram())
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ส่งข้อความทดสอบไม่สำเร็จ')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className={`system-settings-page ${embedded ? 'system-settings-page-embedded' : 'page-content'}`}>
      <section className="telegram-settings" aria-labelledby="telegram-heading">
        <header>
          <div><span className="setting-icon"><Bell size={19} aria-hidden="true" /></span><div><span className="eyebrow">System notification</span><h3 id="telegram-heading">Telegram</h3><p>ส่งเหตุการณ์สำคัญของ MT Pulse ไปยัง Group กลาง</p></div></div>
          <span className={`connection-state ${configured ? 'configured' : ''}`}>{configured ? 'มี Token บันทึกอยู่' : 'ยังไม่มี Token'}</span>
        </header>
        <div className="telegram-form">
          <label>
            {configured ? 'Bot Token ใหม่ (กรอกเมื่อต้องการเปลี่ยน)' : 'Bot Token'}
            <span className="secret-input">
              <input aria-label="Bot Token" type={showToken ? 'text' : 'password'} autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} placeholder={configured ? 'กรอก Token ใหม่เฉพาะเมื่อต้องการเปลี่ยน' : 'กรอก Token จาก BotFather'} />
              <button type="button" aria-label={showToken ? 'ซ่อน Bot Token' : 'แสดง Bot Token'} aria-pressed={showToken} disabled={!token} title={token ? 'แสดงหรือซ่อน Token ที่กำลังกรอก' : 'กรอก Token ใหม่ก่อนจึงจะเปิดดูได้'} onClick={() => setShowToken((visible) => !visible)}>{showToken ? <EyeOff size={16} /> : <Eye size={16} />}</button>
            </span>
            <small><ShieldCheck size={13} />{configured ? 'ช่องนี้ว่างได้ ระบบจะใช้ Token ที่บันทึกไว้' : 'Token จะถูกเข้ารหัสก่อนบันทึก'}</small>
          </label>
          <label>Group / Chat ID<input type="text" value={groupId} onChange={(event) => setGroupId(event.target.value)} placeholder="เช่น -1001234567890" /><small>Group กลางสำหรับรับการแจ้งเตือนของทุก MT</small></label>
          <label className="notification-option"><input type="checkbox" checked={notifyManualImport} onChange={(event) => setNotifyManualImport(event.target.checked)} /><span><strong>Manual Import</strong><small>แจ้งเมื่อการนำเข้าด้วยผู้ใช้สำเร็จหรือไม่สำเร็จ</small></span></label>
        </div>
        {message && <div className="settings-message" role="status">{message}</div>}
        <footer><button className="secondary-action" type="button" disabled={!configured || !groupId.trim() || busy !== null} onClick={() => void sendTest()}><Send size={15} />{busy === 'test' ? 'กำลังตรวจสอบ…' : 'ทดสอบ Token และ Group'}</button><button className="primary-action" type="button" disabled={busy !== null} onClick={() => void save()}>{busy === 'save' ? 'กำลังบันทึก…' : 'บันทึกการตั้งค่า'}</button></footer>
      </section>
    </div>
  )
}
