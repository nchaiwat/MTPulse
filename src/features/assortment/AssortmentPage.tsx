import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Download, Eye, EyeOff, RefreshCw } from 'lucide-react'
import { apiFetch, authRequest } from '../auth/authApi'
import { useCanEdit, useIsAdmin } from '../auth/permissions'
import {
  attrs,
  num,
  type BaseItem,
  type Catalog,
  type Plan,
  type Report,
} from './types'
import { BaseEditor } from './BaseEditor'
import { ForecastEditor } from './ForecastEditor'
import './assortment.css'
const api = import.meta.env.VITE_API_BASE_URL ?? ''
export function AssortmentPage({
  onDirtyChange,
}: {
  onDirtyChange: (v: boolean) => void
}) {
  const admin = useIsAdmin(),
    canEdit = useCanEdit()
  const [catalog, setCatalog] = useState<Catalog>({
      bases: [],
      plans: [],
      mts: [],
      pageSize: 25,
    }),
    [report, setReport] = useState<Report | null>(null),
    [loadedQuery, setLoadedQuery] = useState('')
  const [year, setYear] = useState(2027),
    [planId, setPlanId] = useState(''),
    [mt, setMt] = useState(''),
    [search, setSearch] = useState(''),
    [group, setGroup] = useState(''),
    [model, setModel] = useState(''),
    [mode, setMode] = useState('sales'),
    [basis, setBasis] = useState('net'),
    [page, setPage] = useState(1),
    [details, setDetails] = useState(window.innerWidth >= 1280),
    [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [baseEdit, setBaseEdit] = useState<BaseItem | null | undefined>(undefined),
    [edit, setEdit] = useState<{
      base: Report['items'][number]
      mt: string
    } | null>(null),
    [dirty, setDirty] = useState(false)
  const top = useRef<HTMLDivElement>(null),
    bottom = useRef<HTMLDivElement>(null),
    table = useRef<HTMLTableElement>(null),
    spacer = useRef<HTMLDivElement>(null)
  const plan = catalog.plans.find((p) => p.id === planId),
    plans = catalog.plans.filter((p) => p.year === year)
  const query = new URLSearchParams({
    year: String(year),
    mode,
    basis,
    page: String(page),
    search,
    group,
    model,
    ...(mt ? { mt } : {}),
    ...(planId ? { plan_id: planId } : {}),
  }).toString()
  const refresh = () => setRevision((v) => v + 1)
  const markDirty = (v: boolean) => {
    setDirty(v)
    onDirtyChange(v)
  }
  useEffect(() => {
    if (!dirty) return
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])
  useEffect(() => {
    let alive = true
    authRequest<Catalog>('/api/assortment/catalog')
      .then((c) => {
        if (alive) {
          setCatalog(c)
          setPlanId((p) =>
            c.plans.some((x) => x.id === p && x.year === year)
              ? p
              : c.plans.find((x) => x.year === year && x.primary)?.id ||
                c.plans.find((x) => x.year === year)?.id ||
                '',
          )
        }
      })
      .catch((e) => {
        if (alive) setError(e.message)
      })
    return () => {
      alive = false
    }
  }, [revision, year])
  useEffect(() => {
    let alive = true
    const timer = setTimeout(() => {
      setLoading(true)
      setError('')
      authRequest<Report>('/api/assortment/report?' + query)
        .then((v) => {
          if (alive) {
            setReport(v)
            setLoadedQuery(query)
            if (v.total > 0 && (page - 1) * v.pageSize >= v.total) setPage(1)
          }
        })
        .catch((e) => {
          if (alive) {
            setError(e.message)
            setReport(null)
          }
        })
        .finally(() => {
          if (alive) setLoading(false)
        })
    }, 200)
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [query, revision, page])
  useLayoutEffect(() => {
    const sync = () => {
      if (top.current && bottom.current && table.current && spacer.current) {
        top.current.style.width = bottom.current.clientWidth + 'px'
        spacer.current.style.width = table.current.scrollWidth + 'px'
        top.current.scrollLeft = bottom.current.scrollLeft
      }
    }
    sync()
    const observer = new ResizeObserver(sync)
    if (bottom.current) observer.observe(bottom.current)
    if (table.current) observer.observe(table.current)
    return () => observer.disconnect()
  }, [report, details])
  async function task(fn: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function newPlan(copy?: Plan) {
    const name = window.prompt(
      'ชื่อแผน',
      copy ? copy.name + ' (สำเนา)' : 'Forecast ' + year,
    )
    if (!name?.trim()) return
    await task(async () => {
      const v = await authRequest<{ id: string }>(
        '/api/assortment/plans',
        'POST',
        { name, year, copy_id: copy?.id },
      )
      setPlanId(v.id)
      refresh()
    })
  }
  const reportLoading = loading || loadedQuery !== query
  const selected = report?.mts || [],
    offset = (details ? 7 * 64 : 0) + 44
  const identity = (base: BaseItem, index: number) => (
    <>
      <td className="as-no">
        {admin ? (
          <button className="sku-link" onClick={() => setBaseEdit(base)}>
            {index + 1 + (page - 1) * (report?.pageSize || 25)}
          </button>
        ) : (
          index + 1 + (page - 1) * (report?.pageSize || 25)
        )}
      </td>
      {details &&
        base.attributes.map((v, i) => (
          <td
            className="as-attr"
            style={{ left: 44 + i * 64 }}
            key={i}
            title={v}
          >
            {v || '—'}
          </td>
        ))}
      <td className="as-description" style={{ left: offset }}>
        <span title={base.description}>{base.description}</span>
        {!base.members.length && <small>ยังไม่ยืนยัน Mapping</small>}
      </td>
    </>
  )
  return (
    <div className="page-content assortment-page" data-performance-source="TWD">
      <header className="assortment-heading">
        <h1>Assortment</h1>
        {admin && (
          <button onClick={() => setBaseEdit(null)}>Base Item / Mapping</button>
        )}
      </header>
      <div className="assortment-toolbar">
        <div className="segmented-control">
          {['sales', 'inventory'].map((v) => (
            <button
              key={v}
              aria-pressed={mode === v}
              onClick={() => {
                setMode(v)
                setPage(1)
              }}
            >
              {v === 'sales' ? 'Sales Qty / Forecast' : 'Inventory'}
            </button>
          ))}
        </div>
        <label>
          ปี Forecast
          <input
            aria-label="ปี Forecast"
            type="number"
            min={2002}
            max={2100}
            value={year}
            onChange={(e) => {
              const v = Number(e.target.value)
              if (v >= 2002 && v <= 2100) {
                setPlanId('')
                setYear(v)
                setPage(1)
              }
            }}
          />
        </label>
        {mode === 'sales' && (
          <label>
            Sales basis
            <select value={basis} onChange={(e) => setBasis(e.target.value)}>
              <option value="net">Net</option>
              <option value="gross">Gross</option>
            </select>
          </label>
        )}
        <label>
          MT
          <select
            value={mt}
            onChange={(e) => {
              setMt(e.target.value)
              setPage(1)
            }}
          >
            <option value="">ทุก MT</option>
            {catalog.mts.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          แผน
          <select value={planId} onChange={(e) => setPlanId(e.target.value)}>
            <option value="">ไม่มีแผน</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.primary ? ' · หลัก' : ''}
              </option>
            ))}
          </select>
        </label>
        {canEdit && (
          <>
            <button disabled={busy} onClick={() => void newPlan()}>
              เพิ่มแผน
            </button>
            <button disabled={busy || !plan} onClick={() => void newPlan(plan)}>
              คัดลอก
            </button>
            <button
              disabled={busy || reportLoading || !plan || plan.primary}
              onClick={() =>
                void task(async () => {
                  await authRequest(
                    '/api/assortment/plans/' + planId + '/primary',
                    'PUT',
                    { version: report?.planVersion ?? plan?.version },
                  )
                  refresh()
                })
              }
            >
              ใช้แผนหลัก
            </button>
          </>
        )}
      </div>
      <div className="assortment-toolbar">
        <label className="as-search">
          ค้นหา
          <input
            value={search}
            placeholder="Description / WA Item"
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </label>
        {[
          ['กลุ่ม', group, setGroup, 0],
          ['รุ่น', model, setModel, 1],
        ].map(([label, value, setter, i]) => (
          <label key={String(label)}>
            {String(label)}
            <select
              value={String(value)}
              onChange={(e) => {
                ;(setter as (v: string) => void)(e.target.value)
                setPage(1)
              }}
            >
              <option value="">ทั้งหมด</option>
              {[
                ...new Set(
                  catalog.bases
                    .map((b) => b.attributes[Number(i)])
                    .filter(Boolean),
                ),
              ]
                .sort()
                .map((v) => (
                  <option key={v}>{v}</option>
                ))}
            </select>
          </label>
        ))}
        <button
          onClick={() => {
            setSearch('')
            setGroup('')
            setModel('')
            setPage(1)
          }}
        >
          ล้าง
        </button>
        <button aria-label="รีเฟรช" onClick={refresh}>
          <RefreshCw size={15} />
        </button>
        <div className="as-actions">
          <button aria-pressed={details} onClick={() => setDetails(!details)}>
            {details ? <Eye size={15} /> : <EyeOff size={15} />}รายละเอียด
          </button>
          <button
            disabled={busy || reportLoading || !report}
            onClick={() =>
              void task(async () => {
                const r = await apiFetch(
                  api +
                    '/api/assortment/report?' +
                    query +
                    '&download=true&details=' +
                    details,
                )
                if (!r.ok) throw new Error('Download ไม่สำเร็จ')
                const url = URL.createObjectURL(await r.blob()),
                  a = document.createElement('a')
                a.href = url
                a.download = `Assortment_${year}_${mode}.xlsx`
                a.click()
                setTimeout(() => URL.revokeObjectURL(url), 1000)
                setMessage('ดาวน์โหลดแล้ว')
              })
            }
          >
            <Download size={15} />
            Download Excel
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="exchange-error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <section className="matrix-frame" aria-busy={reportLoading}>
        <div
          className="matrix-top-scroll"
          ref={top}
          role="region"
          tabIndex={0}
          aria-label="เลื่อนตารางแนวนอนด้านบน"
          onScroll={(e) => {
            if (bottom.current)
              bottom.current.scrollLeft = e.currentTarget.scrollLeft
          }}
        >
          <div className="matrix-top-scroll-spacer" ref={spacer} />
        </div>
        <div
          className="matrix-scroll"
          ref={bottom}
          tabIndex={0}
          aria-label="ตาราง Assortment"
          onScroll={(e) => {
            if (top.current) top.current.scrollLeft = e.currentTarget.scrollLeft
          }}
        >
          <table className="performance-matrix" ref={table}>
            <thead>
              <tr>
                <th rowSpan={2} className="as-no">
                  No.
                </th>
                {details &&
                  attrs.map((a, i) => (
                    <th
                      rowSpan={2}
                      className="as-attr"
                      style={{ left: 44 + i * 64 }}
                      key={a}
                    >
                      {a}
                    </th>
                  ))}
                <th
                  rowSpan={2}
                  className="as-description"
                  style={{ left: offset }}
                >
                  Description
                </th>
                {selected.map((code) => (
                  <th
                    key={code}
                    colSpan={mode === 'sales' ? 4 : 2}
                    className="as-mt"
                  >
                    {code}
                  </th>
                ))}
              </tr>
              <tr>
                {selected.flatMap((code) =>
                  [year - 2, year - 1]
                    .map((y) => (
                      <th key={code + y}>
                        {y}
                        <small>
                          {mode === 'sales'
                            ? `${report?.coverage[code]?.[y]?.days ?? 0}/${report?.coverage[code]?.[y]?.expected ?? 365} วัน`
                            : 'Stock ล่าสุดในปี'}
                        </small>
                      </th>
                    ))
                    .concat(
                      mode === 'sales'
                        ? [
                            <th key={code + 'f'}>{year} · Forecast</th>,
                            <th key={code + 'g'}>Growth {year - 1}</th>,
                          ]
                        : [],
                    ),
                )}
              </tr>
            </thead>
            <tbody>
              {report?.items.map((b, i) => (
                <tr key={b.id}>
                  {identity(b, i)}
                  {selected.flatMap((code) => {
                    const c = b.cells[code]
                    return [year - 2, year - 1]
                      .map((y) => (
                        <td className="numeric-column" key={code + y}>
                          {num(c.years[y]?.total)}
                          {mode === 'inventory' && (
                            <small>
                              {c.years[y]?.snapshot || 'ไม่มี Snapshot'}
                            </small>
                          )}
                        </td>
                      ))
                      .concat(
                        mode === 'sales'
                          ? [
                              <td key={code + 'f'} className="numeric-column">
                                <button
                                  aria-label={`Forecast ${code} ${b.description}`}
                                  disabled={!plan || reportLoading}
                                  onClick={() => setEdit({ base: b, mt: code })}
                                >
                                  {num(c.forecastTotal)}
                                  <small>{c.filled}/12 เดือน</small>
                                </button>
                              </td>,
                              <td key={code + 'g'} className="numeric-column">
                                {num(c.growth)}
                                {c.growth != null ? '%' : ''}
                              </td>,
                            ]
                          : [],
                      )
                  })}
                </tr>
              ))}
              {!report?.items.length && (
                <tr>
                  <td colSpan={40}>
                    {loading
                      ? 'กำลังโหลด…'
                      : 'ยังไม่มี Base Item ที่ตรงกับตัวกรอง'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="assortment-pagination">
          <span>
            {report?.total ?? 0} รายการ · หน้า {page} /{' '}
            {Math.max(
              1,
              Math.ceil((report?.total || 0) / (report?.pageSize || 25)),
            )}
          </span>
          <button
            disabled={loading || page === 1}
            onClick={() => setPage(page - 1)}
          >
            ก่อนหน้า
          </button>
          <button
            disabled={
              loading || !report || page * report.pageSize >= report.total
            }
            onClick={() => setPage(page + 1)}
          >
            ถัดไป
          </button>
        </footer>
      </section>
      {baseEdit !== undefined && (
        <BaseEditor
          bases={catalog.bases}
          initial={baseEdit || undefined}
          onDirty={markDirty}
          onClose={() => setBaseEdit(undefined)}
          onDone={() => {
            setBaseEdit(undefined)
            refresh()
          }}
        />
      )}
      {edit && plan && report?.planVersion != null && (
        <ForecastEditor
          base={edit.base}
          cell={edit.base.cells[edit.mt]}
          mt={edit.mt}
          plan={plan}
          version={report.planVersion}
          coverage={report.coverage[edit.mt]?.[year - 1]?.months}
          canEdit={canEdit}
          onDirty={markDirty}
          onClose={() => setEdit(null)}
          onDone={() => {
            setEdit(null)
            refresh()
          }}
        />
      )}
    </div>
  )
}
