import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { AssortmentPage } from './AssortmentPage'
import { RoleContext } from '../auth/permissions'
const base = {
  id: 'b',
  description: 'ประตูขาว',
  attributes: ['FA', 'F10', '', '', '', '', '080050'],
  members: ['WA'],
  version: 1,
}
const cell = {
  years: {
    '2025': { months: Array(12).fill(2), total: 24, snapshot: null },
    '2026': { months: Array(12).fill(3), total: 36, snapshot: null },
  },
  forecast: [0, ...Array(11).fill(null)],
  forecastTotal: 0,
  filled: 1,
  growth: null,
}
beforeEach(() => {
  vi.stubGlobal('innerWidth', 1440)
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input)
      const data = url.includes('/catalog')
        ? {
            bases: [base],
            plans: [
              { id: 'p', name: 'Plan', year: 2027, version: 1, primary: false },
            ],
            mts: ['TWD'],
            pageSize: 25,
          }
        : url.includes('/report?')
          ? {
              items: [{ ...base, cells: { TWD: cell } }],
              total: 1,
              page: 1,
              pageSize: 25,
              mts: ['TWD'],
              year: 2027,
              coverage: {
                TWD: {
                  '2025': { days: 365, expected: 365 },
                  '2026': { days: 2, expected: 365 },
                },
              },
              planVersion: 1,
            }
          : options?.method === 'PUT'
            ? { version: 2 }
            : {}
      return { ok: true, status: 200, json: async () => data }
    }),
  )
})
afterEach(() => vi.unstubAllGlobals())
it('keeps Description when hiding attributes and synchronizes horizontal scroll', async () => {
  render(<AssortmentPage onDirtyChange={() => {}} />)
  await screen.findByText('ประตูขาว')
  fireEvent.click(screen.getByRole('button', { name: 'รายละเอียด' }))
  expect(screen.getByText('ประตูขาว')).toBeVisible()
  expect(
    screen.queryByRole('columnheader', { name: 'ขนาด' }),
  ).not.toBeInTheDocument()
  const top = screen.getByRole('region', { name: 'เลื่อนตารางแนวนอนด้านบน' }),
    bottom = screen.getByLabelText('ตาราง Assortment')
  top.scrollLeft = 100
  fireEvent.scroll(top)
  expect(bottom.scrollLeft).toBe(100)
})
it('preserves zero and blank months when saving with version', async () => {
  render(<AssortmentPage onDirtyChange={() => {}} />)
  await screen.findByText('ประตูขาว')
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Forecast TWD ประตูขาว' }),
    ).toBeEnabled(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Forecast TWD ประตูขาว' }))
  expect(screen.getByLabelText('Forecast ม.ค.')).toHaveValue(0)
  expect(screen.getByLabelText('Forecast ก.พ.')).toHaveValue(null)
  fireEvent.change(screen.getByLabelText('Forecast ก.พ.'), {
    target: { value: '25' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'บันทึกร่าง' }))
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/forecast/b/TWD'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          version: 1,
          months: ['0', '25', ...Array(10).fill(null)],
        }),
      }),
    ),
  )
})
it('viewer can read but has no mapping or plan mutation controls', async () => {
  render(
    <RoleContext.Provider value="viewer">
      <AssortmentPage onDirtyChange={() => {}} />
    </RoleContext.Provider>,
  )
  await screen.findByText('ประตูขาว')
  expect(
    screen.queryByRole('button', { name: 'Base Item / Mapping' }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'เพิ่มแผน' }),
  ).not.toBeInTheDocument()
})
it('blocks editing immediately when refreshing the same report', async () => {
  render(<AssortmentPage onDirtyChange={() => {}} />)
  const button = await screen.findByRole('button', {
    name: 'Forecast TWD ประตูขาว',
  })
  await waitFor(() => expect(button).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'รีเฟรช' }))
  expect(button).toBeDisabled()
  await waitFor(() => expect(button).toBeEnabled())
})
