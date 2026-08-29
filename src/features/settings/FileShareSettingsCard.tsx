import { useEffect, useState } from 'react'
import { CheckCircle2, Database, Eye, EyeOff, PlugZap, XCircle } from 'lucide-react'
import {
  fetchFileSharePassword,
  fetchFileShareSettings,
  saveFileShareSettings,
  testFileShare,
  type FileShareProfile,
  type FileShareTestResult,
} from './fileShareSettingsApi'

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

export function FileShareSettingsCard() {
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
  const [busy, setBusy] = useState<'save' | 'test' | 'reveal' | null>(null)
  const [message, setMessage] = useState<SettingsMessage | null>(null)

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

  const payload = () => ({ baseUnc, domain, username, password, profiles })

  const save = async () => {
    setBusy('save')
    setMessage(null)
    try {
      const settings = await saveFileShareSettings(payload())
      setBaseUnc(settings.baseUnc)
      setPasswordConfigured(settings.passwordConfigured)
      setProfiles(settings.profiles)
      setPassword('')
      setShowPassword(false)
      setMessage({ text: 'บันทึกการตั้งค่า FileShare แล้ว', tone: 'success' })
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : 'บันทึกการตั้งค่า FileShare ไม่สำเร็จ',
        tone: 'error',
      })
    } finally {
      setBusy(null)
    }
  }

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
        <button className="secondary-action" type="button" disabled={busy !== null || !baseUnc.trim() || !username.trim()} onClick={() => void test()}>
          <PlugZap size={15} />{busy === 'test' ? 'กำลังทดสอบ…' : 'ทดสอบการเชื่อมต่อ'}
        </button>
      </header>

      <div className="fileshare-form">
        <label className="fileshare-base">
          Base UNC
          <input type="text" value={baseUnc} onChange={(event) => setBaseUnc(event.target.value)} placeholder={defaultBaseUnc} />
          <small>Path กลางร่วมกันของทุก MT เช่น {defaultBaseUnc}</small>
        </label>
        <label>Domain<input type="text" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="เช่น IT-ADMIN (ถ้ามี)" /></label>
        <label>User<input type="text" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Account สำหรับอ่าน FileShare" /></label>
        <label>
          Password
          <span className="secret-input">
            <input aria-label="FileShare Password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={passwordConfigured ? '********' : 'กรอก Password'} />
            <button type="button" aria-label={showPassword ? 'ซ่อน FileShare Password' : 'แสดง FileShare Password'} aria-pressed={showPassword} disabled={(!passwordConfigured && !password) || busy !== null} onClick={() => void togglePassword()}>
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
          return (
            <article key={profile.code}>
              <label className="fileshare-profile-toggle">
                <input type="checkbox" checked={profile.enabled} onChange={(event) => updateProfile(profile.code, { enabled: event.target.checked })} />
                <span><strong>{profile.name}</strong><small>{profile.code}</small></span>
              </label>
              <label>Subfolder<input type="text" value={profile.subfolder} onChange={(event) => updateProfile(profile.code, { subfolder: event.target.value })} placeholder={profile.code} /></label>
              <div className="fileshare-path"><span>Full Path</span><code>{fullPath}</code></div>
              <div className="fileshare-result" data-status={result?.status}>
                {result?.status === 'success' ? <CheckCircle2 size={16} /> : result ? <XCircle size={16} /> : null}
                <span>{result?.message ?? (profile.enabled ? 'ยังไม่ได้ทดสอบ' : 'ปิดใช้งาน')}</span>
              </div>
            </article>
          )
        })}
      </div>

      {message && <div className="settings-message" data-tone={message.tone} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div>}
      <footer><button className="primary-action" type="button" disabled={busy !== null} onClick={() => void save()}>{busy === 'save' ? 'กำลังบันทึก…' : 'บันทึกการตั้งค่า'}</button></footer>
    </section>
  )
}
