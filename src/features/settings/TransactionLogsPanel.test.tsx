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


it('explains historical AD tests using stored target and separate actor', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    items: [{ id: 8, event_code: 'CFG-03', category: 'system_setting', action: 'ad_gateway_test',
      status: 'success', message: 'ทดสอบบัญชีกับ AD Gateway: mtpulse-emergency',
      triggered_by: 'user:mtpulse-emergency', created_at: '2026-10-02T09:26:34Z',
      details: { tested_username: 'chaiwat.n', gateway_status: 'success', mtpulse_status: 'ready',
        ip: '172.18.0.3', ip_source: 'server_observed' }, records_count: 0, duration_ms: 100 }],
    total: 1, page: 1, page_size: 25,
  }) }))
  render(<TransactionLogsPanel />)
  expect(await screen.findByRole('cell', { name: /ทดสอบบัญชี AD: chaiwat.n/ })).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: /mtpulse-emergency/ })).toBeInTheDocument()
  expect(screen.getByText('AD ยืนยันตัวตนสำเร็จ')).toBeInTheDocument()
  expect(screen.getByText(/มีสิทธิ์เข้า MTPulse/)).toBeInTheDocument()
  expect(screen.getByText(/IP ที่ Server เห็น/)).toBeInTheDocument()
})
