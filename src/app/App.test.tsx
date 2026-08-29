import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const performanceResponse = {
  branches: [],
  dates: [],
  months: [],
  items: [],
  meta: { page: 1, pageSize: 25, totalSkus: 0, totalPages: 1, totalBranches: 0 },
  summary: { amount: 0, qty: 0, mappingAttention: 0 },
  latestImport: null,
}

describe('App navigation', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses collapsible submenus and one settings workspace', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/settings/twd/unmatched-visibility')) {
        return new Response(JSON.stringify({
          showUnmatchedItems: false,
          showUnmatchedBranches: false,
        }), { status: 200 })
      }
      if (url.includes('/api/settings/system/telegram/token')) {
        return new Response(JSON.stringify({ botToken: '123456:test-token' }), { status: 200 })
      }
      if (url.includes('/api/settings/system/telegram')) {
        return new Response(JSON.stringify({
          telegramConfigured: true,
          maskedToken: null,
          groupId: '',
          notifyManualImport: true,
        }), { status: 200 })
      }
      return new Response(JSON.stringify(performanceResponse), { status: 200 })
    })

    render(<App />)

    expect(screen.getByRole('button', { name: 'รายงาน' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'สถานะข้อมูล' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'รายงาน ไทวัสดุ' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Monitoring' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'การตั้งค่า' })).toHaveLength(1)
    expect(
      within(screen.getByRole('navigation', { name: 'Primary navigation' })).queryByText('Mapping'),
    ).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'รายงาน' }))
    expect(screen.queryByRole('button', { name: 'รายงาน ไทวัสดุ' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'การตั้งค่า' }))

    expect(screen.getByRole('heading', { level: 1, name: 'การตั้งค่า' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'ไทวัสดุ' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'การตั้งค่าระบบ' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'การตั้งค่า' })).toHaveAttribute('aria-current', 'page')
    expect(screen.queryByText('มี Token บันทึกอยู่')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('https://api.telegram.org')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('********')).toBeInTheDocument()

    const tokenInput = screen.getByLabelText('Bot Token ID')
    await userEvent.click(screen.getByRole('button', { name: 'แสดง Bot Token' }))
    expect(tokenInput).toHaveAttribute('type', 'text')
    expect(tokenInput).toHaveValue('123456:test-token')
  })
})