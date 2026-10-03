import { useEffect, useRef, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { authRequest } from '../auth/authApi'

type Props = { label: string; kind: 'client' | 'ad'; configured: boolean; value: string; onChange: (value: string) => void }

export function CiamSecretField({ label, kind, configured, value, onChange }: Props) {
  const [editing, setEditing] = useState(!configured)
  const [shown, setShown] = useState(false)
  const [revealed, setRevealed] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const requestId = useRef(0)
  useEffect(() => () => { requestId.current += 1 }, [])
  useEffect(() => {
    if (!shown) return
    const timer = window.setTimeout(() => { setShown(false); setRevealed('') }, 30000)
    return () => window.clearTimeout(timer)
  }, [shown])
  function hide() { requestId.current += 1; setShown(false); setRevealed(''); setLoading(false); setError('') }
  async function toggle() {
    if (shown) { hide(); return }
    if (editing) { setShown(true); return }
    const id = ++requestId.current
    setLoading(true); setError('')
    try {
      const result = await authRequest<{ value: string }>(`/api/settings/ciam-sso/secrets/${kind}/reveal`, 'POST')
      if (id === requestId.current) { setRevealed(result.value); setShown(true) }
    } catch (e) {
      if (id === requestId.current) setError(e instanceof Error ? e.message : 'แสดง Secret ไม่สำเร็จ')
    } finally { if (id === requestId.current) setLoading(false) }
  }
  return <div className="ciam-secret">
    <label htmlFor={`ciam-secret-${kind}`}>{label}</label>
    <div className="ciam-secret-input">
      <input id={`ciam-secret-${kind}`} type={editing && !shown ? 'password' : 'text'} autoComplete="new-password" readOnly={!editing}
        value={editing ? value : shown ? revealed : '********'} maxLength={2000}
        onChange={e => onChange(e.target.value)} />
      <button type="button" disabled={loading || (editing && !value)} aria-label={`${shown ? 'ซ่อน' : 'แสดง'} ${label}`} aria-pressed={shown} onClick={() => void toggle()}>
        {shown ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
      </button>
    </div>
    <small>{editing ? 'กรอกค่าใหม่ แล้วกดบันทึก' : 'บันทึกแล้ว — กดรูปตาเพื่อดูค่า'}</small>
    {configured && <button type="button" className="auth-link" onClick={() => { hide(); onChange(''); setEditing(!editing) }}>{editing ? `ยกเลิกเปลี่ยน ${label}` : `เปลี่ยน ${label}`}</button>}
    {error && <small role="alert" className="auth-error">{error}</small>}
  </div>
}
