import type { LoginSession } from '../features/auth/authApi'
import { RoleContext } from '../features/auth/permissions'
import { useState } from 'react'
import { Activity, BarChart3, ChevronDown, Database, HeartPulse, LayoutDashboard, PanelLeftClose, PanelLeftOpen, Settings, TrendingUp } from 'lucide-react'
import { ImportPage } from '../features/imports/ImportPage'
import { TwdDashboardPage } from '../features/dashboard/TwdDashboardPage'
import { MonitoringPage } from '../features/monitoring/MonitoringPage'
import { PerformancePage } from '../features/performance/PerformancePage'
import { SystemAdministrationPage } from '../features/settings/SystemAdministrationPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { SaleOutPage } from '../features/saleOut/SaleOutPage'
import { MODERN_TRADES } from '../config/modernTrades'

type AppPage = 'dashboard' | 'dashboard-hp' | 'dashboard-mh' | 'dashboard-hh' | 'dashboard-gh' | 'dashboard-dh' | 'dashboard-ta' | 'performance' | 'performance-hp' | 'performance-mh' | 'performance-hh' | 'performance-gh' | 'performance-dh' | 'performance-ta' | 'sale-out' | 'imports' | 'monitoring' | 'settings' | 'system-settings'

const pageMeta: Record<AppPage, { eyebrow: string; title: string }> = {
  dashboard: {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.TWD.navigationLabel}`,
    title: `แดชบอร์ด${MODERN_TRADES.TWD.navigationLabel}`,
  },
  'dashboard-hp': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.HP.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.HP.navigationLabel}`,
  },
  'dashboard-mh': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.MH.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.MH.navigationLabel}`,
  },
  'dashboard-hh': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.HH.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.HH.navigationLabel}`,
  },
  'dashboard-gh': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.GH.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.GH.navigationLabel}`,
  },
  'dashboard-dh': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.DH.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.DH.navigationLabel}`,
  },
  'dashboard-ta': {
    eyebrow: `แดชบอร์ด / ${MODERN_TRADES.TA.navigationLabel}`,
    title: `แดชบอร์ด ${MODERN_TRADES.TA.navigationLabel}`,
  },
  performance: {
    eyebrow: `รายงาน / ${MODERN_TRADES.TWD.navigationLabel}`,
    title: `รายงาน${MODERN_TRADES.TWD.navigationLabel}`,
  },
  'performance-hp': {
    eyebrow: `รายงาน / ${MODERN_TRADES.HP.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.HP.navigationLabel}`,
  },
  'performance-mh': {
    eyebrow: `รายงาน / ${MODERN_TRADES.MH.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.MH.navigationLabel}`,
  },
  'performance-hh': {
    eyebrow: `รายงาน / ${MODERN_TRADES.HH.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.HH.navigationLabel}`,
  },
  'performance-gh': {
    eyebrow: `รายงาน / ${MODERN_TRADES.GH.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.GH.navigationLabel}`,
  },
  'performance-dh': {
    eyebrow: `รายงาน / ${MODERN_TRADES.DH.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.DH.navigationLabel}`,
  },
  'performance-ta': {
    eyebrow: `รายงาน / ${MODERN_TRADES.TA.navigationLabel}`,
    title: `รายงาน ${MODERN_TRADES.TA.navigationLabel}`,
  },
  'sale-out': { eyebrow: 'ภาพรวมทุก Modern Trade', title: 'Sale Out' },
  imports: { eyebrow: 'สถานะข้อมูล / นำเข้าข้อมูล', title: 'นำเข้าข้อมูล' },
  monitoring: { eyebrow: 'System health', title: 'Monitoring' },
  settings: { eyebrow: 'Administration', title: 'ModernTrade Setting' },
  'system-settings': { eyebrow: 'Administration', title: 'System Setting' },
}

const developmentSession: LoginSession = { user: { id: 'development', username: 'development-admin', full_name: 'Development Admin', role: 'admin', active: true }, provider: 'development', csrf_token: '', expires_at: null }

export function App({ auth = developmentSession, onLogout }: { auth?: LoginSession; onLogout?: () => void }) {
  const isAdmin = auth.user.role === 'admin'
  const canEdit = auth.user.role !== 'viewer'
  const [page, updatePage] = useState<AppPage>('dashboard')
  const [systemDirty, setSystemDirty] = useState(false)
  const setPage = (next: AppPage) => {
    if (next !== page && page === 'system-settings' && systemDirty && !window.confirm('มีข้อมูลที่ยังไม่ได้บันทึก ต้องการออกจากหน้านี้หรือไม่?')) return
    setSystemDirty(false)
    updatePage(next)
  }
  const [openMenu, setOpenMenu] = useState({
    dashboard: false,
    reports: false,
    data: false,
  })
  const [navigationCollapsed, setNavigationCollapsed] = useState(false)
  const [correctiveBatchId, setCorrectiveBatchId] = useState<number | null>(null)
  const [settingsFocusKey, setSettingsFocusKey] = useState(0)
  const meta = pageMeta[page]

  return (
    <RoleContext.Provider value={auth.user.role}><div className="app-shell" data-navigation={navigationCollapsed ? 'collapsed' : 'expanded'}>
      <a className="skip-link" href="#main-content">
        ข้ามไปยังเนื้อหาหลัก
      </a>
      <aside className="navigation-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            <Activity size={19} />
          </span>
          <span className="brand-copy">
            <strong>MT Pulse</strong>
            <small>วิเคราะห์ Modern Trade</small>
          </span>
          <button className="sidebar-toggle" type="button" aria-label={navigationCollapsed ? 'ขยายเมนู' : 'ย่อเมนู'} aria-expanded={!navigationCollapsed} title={navigationCollapsed ? 'ขยายเมนู' : 'ย่อเมนู'} onClick={() => setNavigationCollapsed((current) => !current)}>
            {navigationCollapsed ? <PanelLeftOpen size={17} aria-hidden="true" /> : <PanelLeftClose size={17} aria-hidden="true" />}
          </button>
        </div>

        <nav aria-label="Primary navigation">
          <section className="nav-group">
            <button
              className="nav-group-label"
              type="button"
              title={navigationCollapsed ? 'แดชบอร์ด' : undefined}
              disabled={!canEdit}
              data-active={(navigationCollapsed && page === 'dashboard') || undefined}
              aria-current={navigationCollapsed && page === 'dashboard' ? 'page' : undefined}
              aria-expanded={navigationCollapsed ? false : openMenu.dashboard}
              aria-controls="dashboard-submenu"
              onClick={() => {
                if (navigationCollapsed) {
                  setPage('dashboard')
                  return
                }
                setOpenMenu((current) => ({
                  ...current,
                  dashboard: !current.dashboard,
                }))
              }}
            >
              <LayoutDashboard size={17} aria-hidden="true" />
              <span>แดชบอร์ด</span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.dashboard && (
              <div className="nav-submenu" id="dashboard-submenu">
                <button className="nav-item nav-subitem" aria-label={`แดชบอร์ด ${MODERN_TRADES.TWD.navigationLabel}`} data-active={page === 'dashboard' || undefined} aria-current={page === 'dashboard' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard')}>
                  <span>{MODERN_TRADES.TWD.navigationLabel}</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด HomePro" data-active={page === 'dashboard-hp' || undefined} aria-current={page === 'dashboard-hp' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-hp')}>
                  <span>HomePro</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด MegaHome" data-active={page === 'dashboard-mh' || undefined} aria-current={page === 'dashboard-mh' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-mh')}>
                  <span>MegaHome</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด HomeHub" data-active={page === 'dashboard-hh' || undefined} aria-current={page === 'dashboard-hh' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-hh')}>
                  <span>HomeHub</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด Global House" data-active={page === 'dashboard-gh' || undefined} aria-current={page === 'dashboard-gh' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-gh')}>
                  <span>Global House</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด DoHome" data-active={page === 'dashboard-dh' || undefined} aria-current={page === 'dashboard-dh' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-dh')}>
                  <span>DoHome</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="แดชบอร์ด Thai-Aust" data-active={page === 'dashboard-ta' || undefined} aria-current={page === 'dashboard-ta' ? 'page' : undefined} type="button" onClick={() => setPage('dashboard-ta')}>
                  <span>Thai-Aust</span>
                </button>
              </div>
            )}
          </section>

          <button className="nav-item nav-main-item" aria-label="Sale Out" title={navigationCollapsed ? 'Sale Out' : undefined} data-active={page === 'sale-out' || undefined} aria-current={page === 'sale-out' ? 'page' : undefined} type="button" onClick={() => setPage('sale-out')}>
            <TrendingUp size={17} aria-hidden="true" />
            <span>Sale Out</span>
          </button>

          <section className="nav-group">
            <button
              className="nav-group-label"
              type="button"
              title={navigationCollapsed ? 'รายงาน' : undefined}
              disabled={!canEdit}
              data-active={(navigationCollapsed && page.startsWith('performance')) || undefined}
              aria-current={navigationCollapsed && page.startsWith('performance') ? 'page' : undefined}
              aria-expanded={navigationCollapsed ? false : openMenu.reports}
              aria-controls="reports-submenu"
              onClick={() => {
                if (navigationCollapsed) {
                  setPage('performance')
                  return
                }
                setOpenMenu((current) => ({
                  ...current,
                  reports: !current.reports,
                }))
              }}
            >
              <BarChart3 size={17} aria-hidden="true" />
              <span>รายงาน</span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.reports && (
              <div className="nav-submenu" id="reports-submenu">
                <button className="nav-item nav-subitem" aria-label={`รายงาน ${MODERN_TRADES.TWD.navigationLabel}`} data-active={page === 'performance' || undefined} aria-current={page === 'performance' ? 'page' : undefined} type="button" onClick={() => setPage('performance')}>
                  <span>{MODERN_TRADES.TWD.navigationLabel}</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน HomePro" data-active={page === 'performance-hp' || undefined} aria-current={page === 'performance-hp' ? 'page' : undefined} type="button" onClick={() => setPage('performance-hp')}>
                  <span>HomePro</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน MegaHome" data-active={page === 'performance-mh' || undefined} aria-current={page === 'performance-mh' ? 'page' : undefined} type="button" onClick={() => setPage('performance-mh')}>
                  <span>MegaHome</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน HomeHub" data-active={page === 'performance-hh' || undefined} aria-current={page === 'performance-hh' ? 'page' : undefined} type="button" onClick={() => setPage('performance-hh')}>
                  <span>HomeHub</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน Global House" data-active={page === 'performance-gh' || undefined} aria-current={page === 'performance-gh' ? 'page' : undefined} type="button" onClick={() => setPage('performance-gh')}>
                  <span>Global House</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน DoHome" data-active={page === 'performance-dh' || undefined} aria-current={page === 'performance-dh' ? 'page' : undefined} type="button" onClick={() => setPage('performance-dh')}>
                  <span>DoHome</span>
                </button>
                <button className="nav-item nav-subitem" aria-label="รายงาน Thai-Aust" data-active={page === 'performance-ta' || undefined} aria-current={page === 'performance-ta' ? 'page' : undefined} type="button" onClick={() => setPage('performance-ta')}>
                  <span>Thai-Aust</span>
                </button>
              </div>
            )}
          </section>

          <section className="nav-group">
            <button
              className="nav-group-label"
              type="button"
              title={navigationCollapsed ? 'สถานะข้อมูล' : undefined}
              disabled={!canEdit}
              data-active={(navigationCollapsed && page === 'imports') || undefined}
              aria-current={navigationCollapsed && page === 'imports' ? 'page' : undefined}
              aria-expanded={navigationCollapsed ? false : openMenu.data}
              aria-controls="data-status-submenu"
              onClick={() => {
                if (navigationCollapsed) {
                  setCorrectiveBatchId(null)
                  setPage('imports')
                  return
                }
                setOpenMenu((current) => ({ ...current, data: !current.data }))
              }}
            >
              <Database size={17} aria-hidden="true" />
              <span>สถานะข้อมูล</span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {openMenu.data && (
              <div className="nav-submenu" id="data-status-submenu">
                <button
                  className="nav-item nav-subitem"
                  aria-label="สถานะข้อมูล นำเข้าข้อมูล"
                  data-active={page === 'imports' || undefined}
                  aria-current={page === 'imports' ? 'page' : undefined}
                  type="button"
                  onClick={() => {
                    setCorrectiveBatchId(null)
                    setPage('imports')
                  }}
                >
                  <span>นำเข้าข้อมูล</span>
                </button>
              </div>
            )}
          </section>

          <button disabled={!isAdmin} className="nav-item nav-main-item" aria-label="Monitoring" title={navigationCollapsed ? 'Monitoring' : undefined} data-active={page === 'monitoring' || undefined} aria-current={page === 'monitoring' ? 'page' : undefined} type="button" onClick={() => setPage('monitoring')}>
            <HeartPulse size={17} aria-hidden="true" />
            <span>Monitoring</span>
          </button>

          <button disabled={!canEdit} className="nav-item nav-main-item" aria-label="ModernTrade Setting" title={navigationCollapsed ? 'ModernTrade Setting' : undefined} data-active={page === 'settings' || undefined} aria-current={page === 'settings' ? 'page' : undefined} type="button" onClick={() => setPage('settings')}>
            <Settings size={17} aria-hidden="true" />
            <span>ModernTrade Setting</span>
          </button>
          {isAdmin && <button className="nav-item nav-main-item" aria-label="System Setting" title={navigationCollapsed ? 'System Setting' : undefined} data-active={page === 'system-settings' || undefined} aria-current={page === 'system-settings' ? 'page' : undefined} type="button" onClick={() => setPage('system-settings')}>
            <Settings size={18} aria-hidden="true" /><span>System Setting</span>
          </button>}
        </nav>

        <div className="rail-footer rail-user" aria-label="ผู้ใช้งานปัจจุบัน">
          <span className="rail-user-avatar" aria-hidden="true">
            {auth.user.full_name.slice(0, 2)}
          </span>
          <span>
            <strong>{auth.user.full_name}</strong>
            <small>{auth.user.role}</small>
            {onLogout && <button type="button" onClick={onLogout}>ออกจากระบบ</button>}
          </span>
        </div>
      </aside>

      <main className="app-main" id="main-content">
        {!page.startsWith('performance') && !page.startsWith('dashboard') && page !== 'sale-out' && page !== 'imports' && page !== 'monitoring' && page !== 'settings' && page !== 'system-settings' && (
          <header className="top-bar">
            <div>
              <span className="eyebrow">{meta.eyebrow}</span>
              <h1>{meta.title}</h1>
            </div>
          </header>
        )}
        {page === 'dashboard' && <TwdDashboardPage onOpenReport={() => setPage('performance')} />}
        {page === 'dashboard-hp' && <TwdDashboardPage mtCode="HP" onOpenReport={() => setPage('performance-hp')} />}
        {page === 'dashboard-mh' && <TwdDashboardPage mtCode="MH" onOpenReport={() => setPage('performance-mh')} />}
        {page === 'dashboard-hh' && <TwdDashboardPage mtCode="HH" onOpenReport={() => setPage('performance-hh')} />}
        {page === 'dashboard-gh' && <TwdDashboardPage mtCode="GH" onOpenReport={() => setPage('performance-gh')} />}
        {page === 'dashboard-dh' && <TwdDashboardPage mtCode="DH" onOpenReport={() => setPage('performance-dh')} />}
        {page === 'dashboard-ta' && <TwdDashboardPage mtCode="TA" onOpenReport={() => setPage('performance-ta')} />}
        {page === 'performance' && <PerformancePage />}
        {page === 'performance-hp' && <PerformancePage mtCode="HP" />}
        {page === 'performance-mh' && <PerformancePage mtCode="MH" />}
        {page === 'performance-hh' && <PerformancePage mtCode="HH" />}
        {page === 'performance-gh' && <PerformancePage mtCode="GH" />}
        {page === 'performance-dh' && <PerformancePage mtCode="DH" />}
        {page === 'performance-ta' && <PerformancePage mtCode="TA" />}
        {page === 'sale-out' && <SaleOutPage />}
        {canEdit && page === 'imports' && <ImportPage correctiveBatchId={correctiveBatchId} />}
        {isAdmin && page === 'monitoring' && (
          <MonitoringPage
            onOpenImports={(batchId) => {
              setCorrectiveBatchId(batchId)
              setPage('imports')
            }}
            onOpenCoverage={() => {
              setSettingsFocusKey(Date.now())
              setPage('settings')
            }}
          />
        )}
        {canEdit && page === 'settings' && <SettingsPage focusCoverageKey={settingsFocusKey} />}
        {isAdmin && page === 'system-settings' && <SystemAdministrationPage onDirtyChange={setSystemDirty} />}
      </main>
    </div></RoleContext.Provider>
  )
}
