import { useEffect } from 'react'
import { Bell, Building2 } from 'lucide-react'
import { SystemSettingsPage } from './SystemSettingsPage'
import { TwdSettingsPage } from './TwdSettingsPage'

export function SettingsPage({ focusCoverageKey = 0 }: { focusCoverageKey?: number }) {
  useEffect(() => {
    if (!focusCoverageKey) return
    document.getElementById('data-coverage-heading')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focusCoverageKey])

  return (    <div className="settings-workspace page-content">
      <div className="settings-workspace-intro">
        <p>รวมการตั้งค่าของ Modern Trade และระบบไว้ในที่เดียว</p>
      </div>

      <section className="settings-zone" aria-labelledby="twd-zone-heading">
        <header className="settings-zone-heading">
          <span className="settings-zone-icon"><Building2 size={19} aria-hidden="true" /></span>
          <div><span className="eyebrow">Modern Trade</span><h2 id="twd-zone-heading">ไทวัสดุ</h2><p>กำหนดขอบเขตข้อมูลที่ใช้ในรายงาน</p></div>
        </header>
        <TwdSettingsPage embedded />
      </section>

      <section className="settings-zone" aria-labelledby="system-zone-heading">
        <header className="settings-zone-heading">
          <span className="settings-zone-icon"><Bell size={19} aria-hidden="true" /></span>
          <div><span className="eyebrow">System</span><h2 id="system-zone-heading">การแจ้งเตือน</h2><p>กำหนดช่องทางแจ้งเหตุการณ์สำคัญของระบบ</p></div>
        </header>
        <SystemSettingsPage embedded />
      </section>
    </div>
  )
}