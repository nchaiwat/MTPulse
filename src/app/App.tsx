import { useState } from 'react'
import {
  Activity,
  BarChart3,
  ChevronDown,
  Database,
  HeartPulse,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
} from 'lucide-react'
import { ImportPage } from '../features/imports/ImportPage'
import { TwdDashboardPage } from '../features/dashboard/TwdDashboardPage'
import { MonitoringPage } from '../features/monitoring/MonitoringPage'
import { PerformancePage } from '../features/performance/PerformancePage'
import { SettingsPage } from '../features/settings/SettingsPage'

type AppPage = 'dashboard' | 'performance' | 'imports' | 'monitoring' | 'settings'

const pageMeta: Record<AppPage, { eyebrow: string; title: string }> = {
  dashboard: { eyebrow: 'แดชบอร์ด / ไทวัสดุ', title: 'แดชบอร์ดไทวัสดุ' },
  performance: { eyebrow: 'รายงาน / ไทวัสดุ', title: 'รายงานไทวัสดุ' },
  imports: { eyebrow: 'สถานะข้อมูล / นำเข้าข้อมูล', title: 'นำเข้าข้อมูล' },
  monitoring: { eyebrow: 'System health', title: 'Monitoring' },
  settings: { eyebrow: 'การตั้งค่า', title: 'การตั้งค่า' },
}

export function App() {
  const [page, setPage] = useState<AppPage>('performance')
  const [openMenu, setOpenMenu] = useState({ dashboard: true, reports: true, data: true })
  const [navigationCollapsed, setNavigationCollapsed] = useState(false)
  const [correctiveBatchId, setCorrectiveBatchId] = useState<number | null>(null)
  const [settingsFocusKey, setSettingsFocusKey] = useState(0)
  const meta = pageMeta[page]

  return (
    <div className="app-shell" data-navigation={navigationCollapsed ? 'collapsed' : 'expanded'}>
      <a className="skip-link" href="#main-content">ข้ามไปยังเนื้อหาหลัก</a>
      <aside className="navigation-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"><Activity size={19} /></span>
          <span className="brand-copy"><strong>MT Pulse</strong><small>วิเคราะห์ Modern Trade</small></span>
          <button
            className="sidebar-toggle"
            type="button"
            aria-label={navigationCollapsed ? 'ขยายเมนู' : 'ย่อเมนู'}
            aria-expanded={!navigationCollapsed}
            title={navigationCollapsed ? 'ขยายเมนู' : 'ย่อเมนู'}
            onClick={() => setNavigationCollapsed((current) => !current)}
          >
            {navigationCollapsed
              ? <PanelLeftOpen size={17} aria-hidden="true" />
              : <PanelLeftClose size={17} aria-hidden="true" />}
          </button>
        </div>

        <nav aria-label="Primary navigation">
          <section className="nav-group">
            <button className="nav-group-label" type="button" title={navigationCollapsed ? 'แดชบอร์ด' : undefined} data-active={navigationCollapsed && page === 'dashboard' || undefined} aria-current={navigationCollapsed && page === 'dashboard' ? 'page' : undefined} aria-expanded={navigationCollapsed ? false : openMenu.dashboard} aria-controls="dashboard-submenu" onClick={() => { if (navigationCollapsed) { setPage('dashboard'); return } setOpenMenu((current) => ({ ...current, dashboard: !current.dashboard })) }}>
              <LayoutDashboard size={17} aria-hidden="true" /><span>แดชบอร์ด</span><ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.dashboard && <div className="nav-submenu" id="dashboard-submenu"><button className="nav-item nav-subitem" aria-label="แดชบอร์ด ไทวัสดุ" data-active={page === 'dashboard' || undefined} aria-current={page === 'dashboard' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard')}><span>ไทวัสดุ</span></button></div>}
          </section>

          <section className="nav-group">
            <button className="nav-group-label" type="button" title={navigationCollapsed ? 'รายงาน' : undefined} data-active={navigationCollapsed && page === 'performance' || undefined} aria-current={navigationCollapsed && page === 'performance' ? 'page' : undefined} aria-expanded={navigationCollapsed ? false : openMenu.reports} aria-controls="reports-submenu" onClick={() => { if (navigationCollapsed) { setPage('performance'); return } setOpenMenu((current) => ({ ...current, reports: !current.reports })) }}>
              <BarChart3 size={17} aria-hidden="true" /><span>รายงาน</span><ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.reports && <div className="nav-submenu" id="reports-submenu"><button className="nav-item nav-subitem" aria-label="รายงาน ไทวัสดุ" data-active={page === 'performance' || undefined} aria-current={page === 'performance' ? 'page' : undefined} type="button" onClick={() => setPage('performance')}><span>ไทวัสดุ</span></button></div>}
          </section>

          <section className="nav-group">
            <button className="nav-group-label" type="button" title={navigationCollapsed ? 'สถานะข้อมูล' : undefined} data-active={navigationCollapsed && page === 'imports' || undefined} aria-current={navigationCollapsed && page === 'imports' ? 'page' : undefined} aria-expanded={navigationCollapsed ? false : openMenu.data} aria-controls="data-status-submenu" onClick={() => { if (navigationCollapsed) { setCorrectiveBatchId(null); setPage('imports'); return } setOpenMenu((current) => ({ ...current, data: !current.data })) }}>
              <Database size={17} aria-hidden="true" /><span>สถานะข้อมูล</span><ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.data && <div className="nav-submenu" id="data-status-submenu"><button className="nav-item nav-subitem" aria-label="สถานะข้อมูล นำเข้าข้อมูล" data-active={page === 'imports' || undefined} aria-current={page === 'imports' ? 'page' : undefined} type="button" onClick={() => { setCorrectiveBatchId(null); setPage('imports') }}><span>นำเข้าข้อมูล</span></button></div>}
          </section>

          <button className="nav-item nav-main-item" aria-label="Monitoring" title={navigationCollapsed ? 'Monitoring' : undefined} data-active={page === 'monitoring' || undefined} aria-current={page === 'monitoring' ? 'page' : undefined} type="button" onClick={() => setPage('monitoring')}>
            <HeartPulse size={17} aria-hidden="true" /><span>Monitoring</span>
          </button>

          <button className="nav-item nav-main-item" aria-label="การตั้งค่า" title={navigationCollapsed ? 'การตั้งค่า' : undefined} data-active={page === 'settings' || undefined} aria-current={page === 'settings' ? 'page' : undefined} type="button" onClick={() => setPage('settings')}>
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
        {page === 'dashboard' && <TwdDashboardPage onOpenReport={() => setPage('performance')} />}
        {page === 'performance' && <PerformancePage />}
        {page === 'imports' && <ImportPage correctiveBatchId={correctiveBatchId} />}
        {page === 'monitoring' && <MonitoringPage onOpenImports={(batchId) => { setCorrectiveBatchId(batchId); setPage('imports') }} onOpenCoverage={() => { setSettingsFocusKey(Date.now()); setPage('settings') }} />}
        {page === 'settings' && <SettingsPage focusCoverageKey={settingsFocusKey} />}
      </main>
    </div>
  )
}
