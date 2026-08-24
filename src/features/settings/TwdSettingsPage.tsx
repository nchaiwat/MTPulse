import { useEffect, useState } from 'react'
import { Building2, PackageSearch } from 'lucide-react'
import {
  fetchUnmatchedVisibility,
  updateUnmatchedVisibility,
  type UnmatchedVisibility,
} from './twdSettingsApi'

const defaultSettings: UnmatchedVisibility = {
  showUnmatchedItems: false,
  showUnmatchedBranches: false,
}

export function TwdSettingsPage({ embedded = false }: { embedded?: boolean }) {
  const [settings, setSettings] = useState(defaultSettings)
  const [isLoading, setIsLoading] = useState(true)
  const [updating, setUpdating] = useState<'item' | 'branch' | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchUnmatchedVisibility(controller.signal)
      .then(setSettings)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(error instanceof Error ? error.message : 'โหลดการตั้งค่าไม่สำเร็จ')
        }
      })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false) })
    return () => controller.abort()
  }, [])

  const changeSetting = async (
    target: 'item' | 'branch',
    nextValue: boolean,
  ) => {
    const nextSettings = {
      ...settings,
      [target === 'item' ? 'showUnmatchedItems' : 'showUnmatchedBranches']: nextValue,
    }
    setUpdating(target)
    setMessage(null)
    try {
      const saved = await updateUnmatchedVisibility(nextSettings)
      setSettings(saved)
      setMessage(
        nextValue
          ? `เปิดแสดง ${target === 'item' ? 'Item' : 'Branch'} Unmatch แล้ว ข้อมูลจะถูกนำไปรวมในรายงาน`
          : `ปิดแสดง ${target === 'item' ? 'Item' : 'Branch'} Unmatch แล้ว ข้อมูลจะไม่ถูกนำไปรวมในรายงาน`,
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'บันทึกการตั้งค่าไม่สำเร็จ')
    } finally {
      setUpdating(null)
    }
  }

  return (
    <div className={embedded ? 'settings-page settings-page-embedded' : 'settings-page page-content'}>
      {!embedded && <div className="settings-intro">
        <div>
          <span className="eyebrow">การตั้งค่า / ไทวัสดุ</span>
          <h2>การตั้งค่าไทวัสดุ</h2>
          <p>Mapping ที่ยืนยันจากไฟล์ Excel จะแสดงในรายงานโดยอัตโนมัติ</p>
        </div>
        <div className="scope-rule">
          <span>กฎการคำนวณ</span>
          <strong>Unmatch ที่ไม่แสดง จะไม่ถูกนำไปรวมใน SUM และ KPI</strong>
        </div>
      </div>
}
      <section className="unmatched-settings" aria-labelledby="unmatched-heading">
        <header>
          <span className="eyebrow">Unmatched data</span>
          <h3 id="unmatched-heading">ข้อมูลที่ยังไม่ Mapping</h3>
          <p>เปิดเฉพาะเมื่อต้องการตรวจสอบข้อมูลต้นทางที่ยังไม่ได้ยืนยันใน Excel</p>
        </header>

        <div className="unmatched-options" data-loading={isLoading || undefined}>
          <article>
            <span className="setting-icon"><Building2 size={19} aria-hidden="true" /></span>
            <div>
              <h4>Branch Unmatch</h4>
              <p>Branch ที่ยังไม่มี WA Branch Mapping</p>
              <small>{settings.showUnmatchedBranches ? 'แสดงและรวมยอดในรายงาน' : 'ไม่แสดงและไม่รวมยอด'}</small>
            </div>
            <button
              className="global-scope-switch"
              type="button"
              role="switch"
              aria-checked={settings.showUnmatchedBranches}
              aria-label="แสดง Branch Unmatch"
              disabled={isLoading || updating !== null}
              onClick={() => void changeSetting('branch', !settings.showUnmatchedBranches)}
            >
              <span aria-hidden="true"><i /></span>
              {settings.showUnmatchedBranches ? 'แสดง' : 'ไม่แสดง'}
            </button>
          </article>

          <article>
            <span className="setting-icon"><PackageSearch size={19} aria-hidden="true" /></span>
            <div>
              <h4>Item Unmatch</h4>
              <p>Item ที่ยังไม่มี WA Item Mapping</p>
              <small>{settings.showUnmatchedItems ? 'แสดงและรวมยอดในรายงาน' : 'ไม่แสดงและไม่รวมยอด'}</small>
            </div>
            <button
              className="global-scope-switch"
              type="button"
              role="switch"
              aria-checked={settings.showUnmatchedItems}
              aria-label="แสดง Item Unmatch"
              disabled={isLoading || updating !== null}
              onClick={() => void changeSetting('item', !settings.showUnmatchedItems)}
            >
              <span aria-hidden="true"><i /></span>
              {settings.showUnmatchedItems ? 'แสดง' : 'ไม่แสดง'}
            </button>
          </article>
        </div>

        {message && <div className="settings-message" role="status">{message}</div>}
      </section>
    </div>
  )
}
