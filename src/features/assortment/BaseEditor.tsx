import { useEffect, useRef, useState } from 'react'
import { authRequest } from '../auth/authApi'
import { attrs, type BaseItem } from './types'
type Candidate = {
  waItem: string
  description: string
  baseId: string | null
  suggestedBaseId: string | null
  sources: { mt: string; sku: string }[]
}
export function BaseEditor({
  bases,
  initial,
  onDone,
  onClose,
  onDirty,
}: {
  bases: BaseItem[]
  initial?: BaseItem
  onDone: () => void
  onClose: () => void
  onDirty: (v: boolean) => void
}) {
  const blank = (): BaseItem => ({
    id: '',
    description: '',
    attributes: attrs.map(() => ''),
    members: [],
    version: 0,
  })
  const [draft, setDraft] = useState<BaseItem>(initial || blank),
    [search, setSearch] = useState(''),
    [page, setPage] = useState(1),
    [data, setData] = useState<{ items: Candidate[]; total: number }>({
      items: [],
      total: 0,
    }),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  const dirty = useRef(false),
    dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  useEffect(() => {
    let alive = true
    const timer = setTimeout(() => {
      authRequest<typeof data>(
        `/api/assortment/suggestions?search=${encodeURIComponent(search)}&page=${page}`,
      )
        .then((v) => {
          if (alive) setData(v)
        })
        .catch((e) => {
          if (alive) setError(e.message)
        })
    }, 200)
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [search, page])
  function change(v: BaseItem) {
    setDraft(v)
    dirty.current = true
    onDirty(true)
  }
  function close() {
    if (!dirty.current || window.confirm('ยกเลิกข้อมูลที่ยังไม่บันทึก?')) {
      onDirty(false)
      onClose()
    }
  }
  return (
    <dialog
      ref={dialog}
      className="assortment-dialog"
      aria-labelledby="base-heading"
      onCancel={(e) => {
        e.preventDefault()
        close()
      }}
    >
      <header>
        <h2 id="base-heading">Base Item / WA Item</h2>
        <button onClick={close}>ปิด</button>
      </header>
      <label>
        Base Item
        <select
          value={draft.id}
          disabled={busy}
          onChange={(e) => {
            if (
              dirty.current &&
              !window.confirm('ยกเลิกข้อมูลที่ยังไม่บันทึก?')
            )
              return
            setDraft(bases.find((b) => b.id === e.target.value) || blank())
            dirty.current = false
            onDirty(false)
          }}
        >
          <option value="">เพิ่ม Base Item</option>
          {bases.map((b) => (
            <option key={b.id} value={b.id}>
              {b.description}
            </option>
          ))}
        </select>
      </label>
      <form
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          try {
            await authRequest(
              '/api/assortment/bases' + (draft.id ? '/' + draft.id : ''),
              draft.id ? 'PUT' : 'POST',
              draft,
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
        <label>
          Description
          <input
            required
            maxLength={500}
            value={draft.description}
            onChange={(e) => change({ ...draft, description: e.target.value })}
          />
        </label>
        <div className="assortment-attributes">
          {attrs.map((a, i) => (
            <label key={a}>
              {a}
              <input
                maxLength={200}
                value={draft.attributes[i]}
                onChange={(e) =>
                  change({
                    ...draft,
                    attributes: draft.attributes.map((v, j) =>
                      i === j ? e.target.value : v,
                    ),
                  })
                }
              />
            </label>
          ))}
        </div>
        <div className="assortment-members">
          {draft.members.map((wa) => (
            <button
              type="button"
              key={wa}
              onClick={() =>
                change({
                  ...draft,
                  members: draft.members.filter((v) => v !== wa),
                })
              }
            >
              {wa} ×
            </button>
          ))}
        </div>
        <button disabled={busy || !draft.description.trim()}>
          ยืนยัน Base Item และ Mapping
        </button>
      </form>
      <p role="alert">{error}</p>
      <label>
        ค้นหา WA Item
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </label>
      <div className="assortment-candidates">
        <table>
          <thead>
            <tr>
              <th>WA Item</th>
              <th>Description</th>
              <th>MT / SKU</th>
              <th>Mapping</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr key={c.waItem}>
                <td>{c.waItem}</td>
                <td>{c.description || 'ไม่มี Description'}</td>
                <td>{c.sources.map((s) => s.mt + ': ' + s.sku).join(', ')}</td>
                <td>
                  {c.baseId && c.baseId !== draft.id ? (
                    <span>ยืนยันแล้ว</span>
                  ) : (
                    <button
                      disabled={busy || draft.members.includes(c.waItem)}
                      onClick={() =>
                        change({
                          ...draft,
                          description:
                            draft.description || c.description || c.waItem,
                          members: [...draft.members, c.waItem],
                        })
                      }
                    >
                      เลือก
                    </button>
                  )}
                  {c.suggestedBaseId && !c.baseId && (
                    <small>
                      เสนอ:{' '}
                      {
                        bases.find((b) => b.id === c.suggestedBaseId)
                          ?.description
                      }
                    </small>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer>
        <button disabled={page === 1} onClick={() => setPage(page - 1)}>
          ก่อนหน้า
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil(data.total / 50))}
        </span>
        <button
          disabled={page * 50 >= data.total}
          onClick={() => setPage(page + 1)}
        >
          ถัดไป
        </button>
      </footer>
    </dialog>
  )
}
