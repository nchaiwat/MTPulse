import { render, screen } from '@testing-library/react'
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
    expect(screen.getAllByRole('button', { name: 'การตั้งค่า' })).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: 'รายงาน' }))
    expect(screen.queryByRole('button', { name: 'รายงาน ไทวัสดุ' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'การตั้งค่า' }))

    expect(screen.getByRole('heading', { level: 1, name: 'การตั้งค่า' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'ไทวัสดุ' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'การแจ้งเตือน' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'การตั้งค่า' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('มี Token บันทึกอยู่')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('กรอก Token ใหม่เฉพาะเมื่อต้องการเปลี่ยน')).toBeInTheDocument()

    const tokenInput = screen.getByLabelText('Bot Token')
    await userEvent.type(tokenInput, '123456:test-token')
    await userEvent.click(screen.getByRole('button', { name: 'แสดง Bot Token' }))
    expect(tokenInput).toHaveAttribute('type', 'text')
  })
})