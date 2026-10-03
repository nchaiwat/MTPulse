import { useEffect, useState } from 'react'
import { authRequest } from '../auth/authApi'
import type { Catalog } from './types'
export function AssortmentSettings() {
  const [size, setSize] = useState(25),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(true)
  useEffect(() => {
    let alive = true
    authRequest<Catalog>('/api/assortment/catalog')
      .then((v) => {
        if (alive) setSize(v.pageSize)
      })
      .catch((e) => {
        if (alive) setMessage(e.message)
      })
      .finally(() => {
        if (alive) setBusy(false)
      })
    return () => {
      alive = false
    }
  }, [])
  return (
    <section className="ciam-settings">
      <h2>Assortment</h2>
      <form
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          try {
            await authRequest('/api/assortment/display', 'PUT', {
              page_size: size,
            })
            setMessage('บันทึกแล้ว')
          } catch (e) {
            setMessage((e as Error).message)
          } finally {
            setBusy(false)
          }
        }}
      >
        <label>
          รายการต่อหน้า
          <select
            value={size}
            disabled={busy}
            onChange={(e) => setSize(Number(e.target.value))}
          >
            {[25, 50, 100, 0].map((n) => (
              <option key={n} value={n}>
                {n || 'ทั้งหมด'}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy}>บันทึก</button>
      </form>
      <p role="status">{message}</p>
    </section>
  )
}
