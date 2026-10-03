import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CiamAgentPanel } from './CiamAgentPanel'
afterEach(() => vi.unstubAllGlobals())
it('shows persisted status and saves only agent settings without posting mask', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false, app_code: 'mtpulse', key_configured: true, pending_results: 2 }) })
  vi.stubGlobal('fetch', fetch)
  const dirty = vi.fn()
  render(<CiamAgentPanel onDirtyChange={dirty} />)
  const key = await screen.findByLabelText('Agent API Key')
  expect(key).toHaveValue('********')
  fireEvent.change(screen.getByLabelText('Outbound Agent'), { target: { value: 'true' } })
  expect(dirty).toHaveBeenCalledWith(true)
  fireEvent.click(screen.getByRole('button', { name: 'บันทึก Agent' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch.mock.calls[1][0]).toBe('/api/settings/ciam-agent')
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ enabled: true, app_code: 'mtpulse' })
})
it('preserves draft fields when refreshing status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false, app_code: 'mtpulse', key_configured: false, pending_results: 0 }) }))
  render(<CiamAgentPanel onDirtyChange={() => {}} />)
  fireEvent.change(await screen.findByLabelText('App Code'), { target: { value: 'changed' } })
  fireEvent.click(screen.getByRole('button', { name: 'รีเฟรชสถานะ Agent' }))
  await screen.findByText('อัปเดตสถานะแล้ว')
  expect(screen.getByLabelText('App Code')).toHaveValue('changed')
})
