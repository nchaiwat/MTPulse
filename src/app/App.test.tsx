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
      if (url.includes('/api/settings/system/technical-notifications')) {
        return new Response(JSON.stringify({
          dailyEnabled: true,
          dailyTime: '07:00',
          criticalEnabled: true,
          recoveryEnabled: true,
          cooldownMinutes: 60,
          thresholds: {
            cpu: { warning: 80, critical: 95 },
            memory: { warning: 80, critical: 90 },
            disk: { warning: 80, critical: 90 },
            connections: { warning: 80, critical: 95 },
            deadTuples: { warning: 10, critical: 20 },
          },
        }), { status: 200 })
      }
      return new Response(JSON.stringify(performanceResponse), { status: 200 })
    })

    render(<App />)

    const appShell = document.querySelector('.app-shell')
    expect(appShell).toHaveAttribute('data-navigation', 'expanded')
    await userEvent.click(screen.getByRole('button', { name: 'ย่อเมนู' }))
    expect(appShell).toHaveAttribute('data-navigation', 'collapsed')
    expect(screen.getByRole('button', { name: 'ขยายเมนู' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'รายงาน' })).toHaveAttribute('aria-current', 'page')
    await userEvent.click(screen.getByRole('button', { name: 'ขยายเมนู' }))
    expect(appShell).toHaveAttribute('data-navigation', 'expanded')

    expect(screen.getByRole('button', { name: 'รายงาน' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'แดชบอร์ด' })).toHaveAttribute('aria-expanded', 'true')
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
    expect(screen.getByRole('heading', { name: 'Technical Health' })).toBeInTheDocument()
    expect(screen.getByLabelText('เวลารายงาน Technical Health')).toHaveValue('07:00')

    const tokenInput = screen.getByLabelText('Bot Token ID')
    await userEvent.click(screen.getByRole('button', { name: 'แสดง Bot Token' }))
    expect(tokenInput).toHaveAttribute('type', 'text')
    expect(tokenInput).toHaveValue('123456:test-token')
  })

  it('opens the TWD dashboard from its own navigation group', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (!String(input).includes('/api/dashboards/twd')) {
        return new Response(JSON.stringify(performanceResponse), { status: 200 })
      }
      return new Response(JSON.stringify({
        meta: {
          mtCode: 'TWD', mtName: 'ไทวัสดุ', year: 2026, previousYear: 2025,
          period: 'ytd', latestDataDate: '2026-06-30', availableYears: [2025, 2026],
          loadedDays: 181, expectedDays: 181, completenessPercent: 100,
        },
        summary: {
          currentAmount: 230736315, previousAmount: 233979658, amountYoY: -1.4,
          currentQty: 83140, previousQty: 86801, qtyYoY: -4.2,
        },
        monthly: [],
        topBranches: [],
        topSkus: [],
      }), { status: 200 })
    })

    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'แดชบอร์ด ไทวัสดุ' }))

    expect(screen.getByRole('heading', { level: 1, name: 'แดชบอร์ดไทวัสดุ' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'ภาพรวม Performance ไทวัสดุ' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'แดชบอร์ด ไทวัสดุ' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /เปิดรายงานรายละเอียด/ })).toBeInTheDocument()
  })
})
