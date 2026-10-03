import { useEffect, useRef, useState } from 'react'
import { authRequest } from '../auth/authApi'
import { months, num, type BaseItem, type Cell, type Plan } from './types'
export function ForecastEditor({
  base,
  cell,
  mt,
  plan,
  version,
  coverage,
  onClose,
  onDone,
  onDirty,
  canEdit,
}: {
  base: BaseItem
  cell: Cell
  mt: string
  plan: Plan
  version: number
  coverage?: { days: number; expected: number }[]
  onClose: () => void
  onDone: () => void
  onDirty: (v: boolean) => void
  canEdit: boolean
}) {
  const [values, setValues] = useState(
      cell.forecast.map((v) => (v == null ? '' : String(v))),
    ),
    [pct, setPct] = useState('10'),
    [preview, setPreview] = useState<string[] | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null),
    dirty = useRef(false)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  function change(v: string[]) {
    setValues(v)
    setPreview(null)
    dirty.current = true
    onDirty(true)
  }
  function close() {
    if (!dirty.current || window.confirm('ยกเลิกข้อมูลที่ยังไม่บันทึก?')) {
      onDirty(false)
      onClose()
    }
  }
  const total = values.some((v) => v !== '')
      ? values.reduce((s, v) => s + Number(v || 0), 0)
      : null,
    prior = cell.years[String(plan.year - 1)]?.months || Array(12).fill(null)
  return (
    <dialog
      ref={dialog}
      className="assortment-dialog"
      aria-labelledby="forecast-heading"
      onCancel={(e) => {
        e.preventDefault()
        close()
      }}
    >
      <header>
        <h2 id="forecast-heading">
          {mt} · Forecast {plan.year}
        </h2>
        <button onClick={close}>ปิด</button>
      </header>
      <p>{base.description}</p>
      <p>{plan.name}</p>
      <form
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setError('')
          try {
            await authRequest(
              `/api/assortment/plans/${plan.id}/forecast/${base.id}/${mt}`,
              'PUT',
              { version, months: values.map((v) => (v === '' ? null : v)) },
            )
            dirty.current = false
            onDirty(false)
            onDone()
          } catch (e) {
            setError((e as Error).message)
          } finally {
            setBusy(false)
          }
        }}
      >
        {canEdit && (
          <div className="assortment-toolbar">
            <button
              type="button"
              disabled={busy || prior.every((v) => v == null)}
              onClick={() =>
                change(prior.map((v) => (v == null ? '' : String(v))))
              }
            >
              คัดลอกปีก่อน
            </button>
            <label>
              ปรับ (%)
              <input
                type="number"
                value={pct}
                min={-100}
                max={10000}
                onChange={(e) => {
                  setPct(e.target.value)
                  setPreview(null)
                }}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                const n = Number(pct)
                if (!Number.isFinite(n) || n < -100 || n > 10000) {
                  setError('เปอร์เซ็นต์ต้องอยู่ระหว่าง -100 ถึง 10,000')
                  return
                }
                setPreview(
                  values.map((v) =>
                    v === ''
                      ? ''
                      : String(
                          Math.round(Number(v) * (1 + n / 100) * 10000) / 10000,
                        ),
                  ),
                )
              }}
            >
              ดูผล
            </button>
            {preview && (
              <>
                <span>
                  {num(total)} →{' '}
                  {num(preview.reduce((s, v) => s + Number(v || 0), 0))}
                </span>
                <button type="button" onClick={() => change(preview)}>
                  ใช้ค่า
                </button>
              </>
            )}
          </div>
        )}
        <div className="assortment-months">
          <table className="performance-matrix">
            <thead>
              <tr>
                <th>เดือน</th>
                <th>{plan.year - 2}</th>
                <th>{plan.year - 1}</th>
                <th>Forecast {plan.year}</th>
                <th>Growth</th>
              </tr>
            </thead>
            <tbody>
              {months.map((m, i) => (
                <tr key={m}>
                  <th>{m}</th>
                  <td>{num(cell.years[String(plan.year - 2)]?.months[i])}</td>
                  <td>{num(prior[i])}</td>
                  <td>
                    <input
                      aria-label={'Forecast ' + m}
                      disabled={!canEdit || busy}
                      type="number"
                      min={0}
                      max={1000000000}
                      step="0.0001"
                      placeholder="—"
                      value={values[i]}
                      onChange={(e) =>
                        change(
                          values.map((v, j) => (j === i ? e.target.value : v)),
                        )
                      }
                    />
                  </td>
                  <td>
                    {coverage?.[i]?.days === coverage?.[i]?.expected &&
                    coverage?.[i] != null &&
                    values[i] !== '' &&
                    prior[i] != null &&
                    prior[i] > 0
                      ? num((Number(values[i]) / prior[i] - 1) * 100) + '%'
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          <strong>รวมปี {num(total)}</strong> ·{' '}
          {values.filter((v) => v !== '').length}/12 เดือน
        </p>
        <small>ว่าง = ยังไม่กรอก · 0 = ศูนย์</small>
        <p role="alert">{error}</p>
        <footer>
          <button type="button" onClick={close}>
            ยกเลิก
          </button>
          {canEdit && <button disabled={busy}>บันทึกร่าง</button>}
        </footer>
      </form>
    </dialog>
  )
}
