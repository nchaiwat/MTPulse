import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { TransactionLogsPanel } from './TransactionLogsPanel'

afterEach(() => vi.unstubAllGlobals())
it('filters on the server and supports pagination with safe text details', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [{ id: 1, event_code: 'SSO-02', category: 'ciam_sso', status: 'failed', message: 'ยืนยันตัวตนไม่สำเร็จ', triggered_by: 'anonymous', created_at: '2026-10-02T00:00:00Z', details: { error: '<script>unsafe</script>' }, duration_ms: 12, records_count: 0 }], total: 26, page: 1, page_size: 25 }) })
  vi.stubGlobal('fetch', fetchMock)
  render(<TransactionLogsPanel />)
  expect(await screen.findByText('SSO-02')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('ผลลัพธ์'), { target: { value: 'failed' } })
  fireEvent.click(screen.getByRole('button', { name: 'ค้นหา' }))
  await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('status=failed'))
  await screen.findByText('SSO-02')
  fireEvent.click(screen.getByRole('button', { name: 'ถัดไป' }))
  await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('page=2'))
  expect(document.querySelector('script')).toBeNull()
})
it('shows failures and allows retry', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unavailable')))
  render(<TransactionLogsPanel />)
  expect(await screen.findByRole('alert')).toHaveTextContent('network unavailable')
  expect(screen.getByRole('button', { name: 'ลองใหม่' })).toBeInTheDocument()
})
