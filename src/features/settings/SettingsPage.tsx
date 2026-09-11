import { useEffect, useState } from 'react'
import {
  Bell,
  Building2,
  CalendarClock,
  FileCog,
  FileSearch,
  Globe2,
  LockKeyhole,
  SlidersHorizontal,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { FileShareSettingsCard } from './FileShareSettingsCard'
import { SystemSettingsPage } from './SystemSettingsPage'
import { TwdSettingsPage } from './TwdSettingsPage'
import { MODERN_TRADES, type ModernTradeCode } from '../../config/modernTrades'
import './settingsControlPlane.css'

type SettingsScope = 'global' | ModernTradeCode

type ScopeDefinition = {
  code: SettingsScope
  label: string
  name: string
  status: 'ready' | 'partial' | 'planned'
  sharedWith?: string
}

const scopes: ScopeDefinition[] = [
  { code: 'global', label: 'Global', name: 'Global Settings', status: 'ready' },
  ...Object.values(MODERN_TRADES).map((definition): ScopeDefinition => ({
    code: definition.code,
    label: definition.code,
    name: definition.name,
    status: definition.activeCapabilities.includes('settings')
      ? definition.plannedCapabilities.length > 0 ? 'partial' : 'ready'
      : 'planned',
    sharedWith: definition.code === 'HP' ? 'MH' : definition.code === 'MH' ? 'HP' : undefined,
  })),
]

const statusLabel = {
  ready: 'พร้อมใช้งาน',
  partial: 'พร้อมใช้งานบางส่วน',
  planned: 'ยังไม่ตั้งค่า',
}

function UnavailableSection({
  icon: Icon,
  eyebrow,
  title,
  description,
}: {
  icon: LucideIcon
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <section className="settings-standard-section" data-availability="unavailable" aria-disabled="true">
      <header>
        <span className="setting-icon"><Icon size={18} aria-hidden="true" /></span>
        <div><span className="eyebrow">{eyebrow}</span><h3>{title}</h3><p>{description}</p></div>
        <span className="settings-availability"><LockKeyhole size={13} aria-hidden="true" />Not available for this MT</span>
      </header>
    </section>
  )
}

function CapabilityTemplate() {
  return (
    <>
      <UnavailableSection icon={FileCog} eyebrow="Data mapping & governance" title="Item and Branch Mapping" description="Mapping workflow สำหรับ Modern Trade นี้ยังไม่เปิดใช้งาน" />
      <UnavailableSection icon={FileSearch} eyebrow="Historical data & coverage" title="Historical Processing" description="File Registry, Historical Backfill และ Data Coverage ยังไม่เปิดใช้งาน" />
      <UnavailableSection icon={SlidersHorizontal} eyebrow="Report configuration" title="Report Preferences" description="การตั้งค่ารายงานเฉพาะ Modern Trade นี้ยังไม่เปิดใช้งาน" />
    </>
  )
}

export function SettingsPage({ focusCoverageKey = 0 }: { focusCoverageKey?: number }) {
  const [activeScope, setActiveScope] = useState<SettingsScope>('global')
  const [dirtyScope, setDirtyScope] = useState<SettingsScope | null>(null)
  const current = scopes.find((scope) => scope.code === activeScope) ?? scopes[0]

  useEffect(() => {
    if (!focusCoverageKey) return
    const timer = window.setTimeout(() => {
      setActiveScope('TWD')
      window.setTimeout(() => {
        document.getElementById('data-coverage-heading')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 0)
    }, 0)

    return () => window.clearTimeout(timer)
  }, [focusCoverageKey])

  const selectScope = (scope: SettingsScope) => {
    if (scope === activeScope) return
    if (dirtyScope === activeScope && !window.confirm('มีการตั้งค่าที่ยังไม่ได้บันทึก ต้องการออกจาก Scope นี้หรือไม่?')) return
    setDirtyScope(null)
    setActiveScope(scope)
  }

  const moveScopeFocus = (scope: SettingsScope) => {
    selectScope(scope)
    window.requestAnimationFrame(() => document.getElementById(`settings-tab-${scope}`)?.focus())
  }

  return (
    <div className="settings-control-plane page-content">
      <div className="settings-control-intro">
        <div>
          <span className="eyebrow">Administration</span>
          <h1>การตั้งค่าระบบ</h1>
          <p>ค่ากลางของระบบและค่าที่มีผลเฉพาะแต่ละ Modern Trade</p>
        </div>
        <div className="settings-scope-context" aria-label="ขอบเขตการตั้งค่าปัจจุบัน">
          <span className="settings-scope-symbol">{activeScope === 'global' ? <Globe2 size={17} aria-hidden="true" /> : <Building2 size={17} aria-hidden="true" />}</span>
          <span>
            <small>{activeScope === 'global' ? 'Global scope' : current.code}</small>
            <strong>{current.name}</strong>
          </span>
          {current.sharedWith && <em><CalendarClock size={12} aria-hidden="true" />ใช้ Source และ Schedule ร่วมกับ {current.sharedWith}</em>}
          <b data-status={current.status}>{statusLabel[current.status]}</b>
        </div>
      </div>

      <nav className="settings-scope-tabs" role="tablist" aria-label="Settings scope">
        {scopes.map((scope) => (
          <button
            key={scope.code}
            id={`settings-tab-${scope.code}`}
            type="button"
            role="tab"
            aria-selected={activeScope === scope.code}
            aria-controls={`settings-panel-${scope.code}`}
            tabIndex={activeScope === scope.code ? 0 : -1}
            data-active={activeScope === scope.code || undefined}
            data-status={scope.status}
            onClick={() => selectScope(scope.code)}
            onKeyDown={(event) => {
              const currentIndex = scopes.findIndex((item) => item.code === scope.code)
              if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                event.preventDefault()
                const step = event.key === 'ArrowRight' ? 1 : -1
                const nextIndex = (currentIndex + step + scopes.length) % scopes.length
                moveScopeFocus(scopes[nextIndex].code)
              }
              if (event.key === 'Home' || event.key === 'End') {
                event.preventDefault()
                moveScopeFocus(event.key === 'Home' ? scopes[0].code : scopes[scopes.length - 1].code)
              }
            }}
          >
            {scope.code === 'global' ? <Globe2 size={16} aria-hidden="true" /> : <Building2 size={16} aria-hidden="true" />}
            <span><strong>{scope.label}</strong><small>{scope.code === 'global' ? 'Shared by all MT' : scope.name}</small></span>
            {scope.sharedWith && <em>Shared</em>}
          </button>
        ))}
      </nav>

      <div id={`settings-panel-${activeScope}`} role="tabpanel" aria-labelledby={`settings-tab-${activeScope}`} className="settings-scope-panel">
        {activeScope === 'global' && (
          <SystemSettingsPage embedded fileShareView="connection" onDirtyChange={(dirty) => setDirtyScope(dirty ? 'global' : null)} />
        )}

        {activeScope === 'TWD' && (
          <>
            <FileShareSettingsCard view="profile" profileCode="TWD" showSaveAction onDirtyChange={(dirty) => setDirtyScope(dirty ? 'TWD' : null)} />
            <TwdSettingsPage embedded />
          </>
        )}

        {(activeScope === 'HP' || activeScope === 'MH') && (
          <>
            <FileShareSettingsCard view="profile" profileCode={activeScope} showSaveAction onDirtyChange={(dirty) => setDirtyScope(dirty ? activeScope : null)} />
            <TwdSettingsPage
              embedded
              mtCode={activeScope}
              mtName={activeScope === 'HP' ? 'HomePro' : 'MegaHome'}
            />
          </>
        )}

        {activeScope === 'HH' && (
          <>
            <FileShareSettingsCard view="profile" profileCode="HH" showSaveAction onDirtyChange={(dirty) => setDirtyScope(dirty ? 'HH' : null)} />
            <TwdSettingsPage embedded mtCode="HH" mtName="HomeHub" />
          </>
        )}

        {['GH', 'SCG', 'TA'].includes(activeScope) && (
          <>
            <UnavailableSection icon={Bell} eyebrow="Data source & automation" title="Source Connection and Schedule" description="Source profile สำหรับ Modern Trade นี้ยังไม่ถูกกำหนด" />
            <CapabilityTemplate />
          </>
        )}
      </div>
    </div>
  )
}
