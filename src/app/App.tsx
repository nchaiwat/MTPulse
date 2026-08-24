import { useState } from 'react'
import {
  Activity,
  BarChart3,
  ChevronDown,
  Database,
  GitCompareArrows,
  Settings,
} from 'lucide-react'
import { ImportPage } from '../features/imports/ImportPage'
import { PerformancePage } from '../features/performance/PerformancePage'
import { SettingsPage } from '../features/settings/SettingsPage'

type AppPage = 'performance' | 'imports' | 'settings'

const pageMeta: Record<AppPage, { eyebrow: string; title: string }> = {
  performance: { eyebrow: 'รายงาน / ไทวัสดุ', title: 'รายงานไทวัสดุ' },
  imports: { eyebrow: 'สถานะข้อมูล / นำเข้าข้อมูล', title: 'นำเข้าข้อมูล' },
  settings: { eyebrow: 'การตั้งค่า', title: 'การตั้งค่า' },
}

export function App() {
  const [page, setPage] = useState<AppPage>('performance')
  const [openMenu, setOpenMenu] = useState({ reports: true, data: true })
  const meta = pageMeta[page]

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">ข้ามไปยังเนื้อหาหลัก</a>
      <aside className="navigation-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"><Activity size={19} /></span>
          <span><strong>MT Pulse</strong><small>วิเคราะห์ Modern Trade</small></span>
        </div>

        <nav aria-label="Primary navigation">
          <section className="nav-group">
            <button className="nav-group-label" type="button" aria-expanded={openMenu.reports} aria-controls="reports-submenu" onClick={() => setOpenMenu((current) => ({ ...current, reports: !current.reports }))}>
              <BarChart3 size={17} aria-hidden="true" /><span>รายงาน</span><ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.reports && <div className="nav-submenu" id="reports-submenu"><button className="nav-item nav-subitem" aria-label="รายงาน ไทวัสดุ" data-active={page === 'performance' || undefined} aria-current={page === 'performance' ? 'page' : undefined} type="button" onClick={() => setPage('performance')}><span>ไทวัสดุ</span></button></div>}
          </section>

          <section className="nav-group">
            <button className="nav-group-label" type="button" aria-expanded={openMenu.data} aria-controls="data-status-submenu" onClick={() => setOpenMenu((current) => ({ ...current, data: !current.data }))}>
              <Database size={17} aria-hidden="true" /><span>สถานะข้อมูล</span><ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.data && <div className="nav-submenu" id="data-status-submenu"><button className="nav-item nav-subitem" aria-label="สถานะข้อมูล นำเข้าข้อมูล" data-active={page === 'imports' || undefined} aria-current={page === 'imports' ? 'page' : undefined} type="button" onClick={() => setPage('imports')}><span>นำเข้าข้อมูล</span></button></div>}
          </section>

          <button className="nav-item" disabled type="button">
            <GitCompareArrows size={17} aria-hidden="true" /><span>Mapping</span><small>ภายหลัง</small>
          </button>

          <button className="nav-item nav-main-item" aria-label="การตั้งค่า" data-active={page === 'settings' || undefined} aria-current={page === 'settings' ? 'page' : undefined} type="button" onClick={() => setPage('settings')}>
            <Settings size={17} aria-hidden="true" /><span>การตั้งค่า</span>
          </button>
        </nav>

        <div className="rail-footer">
          <span className="environment-dot" aria-hidden="true" />
          <span><strong>ข้อมูลตัวอย่าง</strong><small>ไทวัสดุ · ส.ค. 2026</small></span>
        </div>
      </aside>

      <main className="app-main" id="main-content">
        <header className="top-bar">
          <div><span className="eyebrow">{meta.eyebrow}</span><h1>{meta.title}</h1></div>
          <div className="user-chip" aria-label="Current user"><span>CN</span><div><strong>Chaiwat N.</strong><small>เจ้าของ Workspace</small></div></div>
        </header>
        {page === 'performance' && <PerformancePage />}
        {page === 'imports' && <ImportPage />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}