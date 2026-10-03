import { useEffect, useState } from 'react'
import { ShieldCheck, Users, ScrollText } from 'lucide-react'
import { useIsAdmin } from '../auth/permissions'
import { CiamSettingsPanel } from './CiamSettingsPanel'
import { TransactionLogsPanel } from './TransactionLogsPanel'
import './settingsControlPlane.css'

const tabs = [
  { id: 'ciam', label: 'Central IAM / AD', icon: ShieldCheck },
  { id: 'users', label: 'User Management', icon: Users },
  { id: 'logs', label: 'Transaction Logs', icon: ScrollText },
] as const
type Tab = typeof tabs[number]['id']

export function SystemAdministrationPage({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const isAdmin = useIsAdmin()
  const [tab, setTab] = useState<Tab>('ciam')
  const [dirty, setDirty] = useState(false)
  useEffect(() => { onDirtyChange(dirty) }, [dirty, onDirtyChange])
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])
  if (!isAdmin) return <p role="alert">เฉพาะ System Admin</p>
  function select(next: Tab) {
    if (next === tab) return
    if (dirty && !window.confirm('มีข้อมูลที่ยังไม่ได้บันทึก ต้องการเปลี่ยนแท็บหรือไม่?')) return
    setDirty(false); setTab(next)
    window.requestAnimationFrame(() => document.getElementById('system-tab-' + next)?.focus())
  }
  return <div className="settings-control-plane page-content">
    <div className="settings-control-intro"><div><span className="eyebrow">Administration</span><h1>System Setting</h1><p>การเข้าสู่ระบบ บัญชีผู้ใช้ และประวัติการทำรายการ</p></div></div>
    <nav className="settings-scope-tabs" role="tablist" aria-label="System Setting">
      {tabs.map(({ id, label, icon: Icon }, index) => <button key={id} id={'system-tab-' + id} type="button" role="tab" aria-selected={tab === id} aria-controls={'system-panel-' + id} tabIndex={tab === id ? 0 : -1} data-active={tab === id || undefined} onClick={() => select(id)} onKeyDown={event => {
        const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
        if (direction) { event.preventDefault(); select(tabs[(index + direction + tabs.length) % tabs.length].id) }
        if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); select(event.key === 'Home' ? tabs[0].id : tabs[tabs.length - 1].id) }
      }}><Icon size={16} aria-hidden="true" /><span><strong>{label}</strong></span></button>)}
    </nav>
    <div id={'system-panel-' + tab} role="tabpanel" aria-labelledby={'system-tab-' + tab} className="settings-scope-panel">
      {tab === 'logs' ? <TransactionLogsPanel /> : <CiamSettingsPanel key={tab} mode={tab} onDirtyChange={setDirty} />}
    </div>
  </div>
}
