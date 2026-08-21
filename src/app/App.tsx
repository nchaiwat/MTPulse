import {
  Activity,
  BarChart3,
  Database,
  GitCompareArrows,
  Settings,
} from 'lucide-react'
import { PerformancePage } from '../features/performance/PerformancePage'

const navigation = [
  { label: 'รายงาน Performance', icon: BarChart3, active: true },
  { label: 'สถานะข้อมูล', icon: Database },
  { label: 'Mapping', icon: GitCompareArrows },
  { label: 'ตั้งค่าระบบ', icon: Settings },
]

export function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">ข้ามไปยังข้อมูล Performance</a>
      <aside className="navigation-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"><Activity size={19} /></span>
          <span><strong>MT Pulse</strong><small>วิเคราะห์ Modern Trade</small></span>
        </div>

        <nav aria-label="Primary navigation">
          {navigation.map(({ label, icon: Icon, active }) => (
            <button
              className="nav-item"
              data-active={active || undefined}
              aria-current={active ? 'page' : undefined}
              disabled={!active}
              type="button"
              key={label}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{label}</span>
              {!active && <small>ภายหลัง</small>}
            </button>
          ))}
        </nav>

        <div className="rail-footer">
          <span className="environment-dot" aria-hidden="true" />
          <span><strong>ข้อมูลตัวอย่าง</strong><small>TWD · ส.ค. 2026</small></span>
        </div>
      </aside>

      <main className="app-main" id="main-content">
        <header className="top-bar">
          <div>
            <span className="eyebrow">Modern Trade / TWD</span>
            <h1>รายงาน Performance</h1>
          </div>
          <div className="user-chip" aria-label="Current user">
            <span>CN</span>
            <div><strong>Chaiwat N.</strong><small>เจ้าของ Workspace</small></div>
          </div>
        </header>
        <PerformancePage />
      </main>
    </div>
  )
}
