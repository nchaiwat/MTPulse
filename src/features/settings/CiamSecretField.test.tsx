import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CiamSecretField } from './CiamSecretField'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
it('shows a saved mask, reveals on demand and never submits the revealed value as an edit', async () => {
  const change = vi.fn()
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ value: 'fixture-secret' }) })
  vi.stubGlobal('fetch', fetchMock)
  render(<CiamSecretField label="Client Secret" kind="client" configured value="" onChange={change} />)
  expect(screen.getByLabelText('Client Secret')).toHaveValue('********')
  expect(fetchMock).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'แสดง Client Secret' }))
  await waitFor(() => expect(screen.getByLabelText('Client Secret')).toHaveValue('fixture-secret'))
  expect(fetchMock).toHaveBeenCalledWith('/api/settings/ciam-sso/secrets/client/reveal', expect.objectContaining({ method: 'POST', cache: 'no-store' }))
  expect(change).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'ซ่อน Client Secret' }))
  expect(screen.getByLabelText('Client Secret')).toHaveValue('********')
})
it('uses separate editing with a masked new value and cancel preserves the saved secret', () => {
  const change = vi.fn()
  render(<CiamSecretField label="AD Secret" kind="ad" configured value="new-secret" onChange={change} />)
  fireEvent.click(screen.getByRole('button', { name: 'เปลี่ยน AD Secret' }))
  expect(screen.getByLabelText('AD Secret')).toHaveAttribute('type', 'password')
  expect(screen.getByLabelText('AD Secret')).not.toHaveAttribute('readonly')
  fireEvent.click(screen.getByRole('button', { name: 'แสดง AD Secret' }))
  expect(screen.getByLabelText('AD Secret')).toHaveAttribute('type', 'text')
  fireEvent.click(screen.getByRole('button', { name: 'ยกเลิกเปลี่ยน AD Secret' }))
  expect(screen.getByLabelText('AD Secret')).toHaveValue('********')
  expect(change).toHaveBeenLastCalledWith('')
})
it('keeps mask and shows an error when reveal is denied', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'Denied' }) }))
  render(<CiamSecretField label="AD Secret" kind="ad" configured value="" onChange={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'แสดง AD Secret' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Denied')
  expect(screen.getByLabelText('AD Secret')).toHaveValue('********')
})
