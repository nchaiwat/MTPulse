import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TwdSettingsPage } from './TwdSettingsPage'

describe('TwdSettingsPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses two global controls for unmatched Branch and Item', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: false,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        showUnmatchedItems: false,
        showUnmatchedBranches: true,
      }), { status: 200 }))

    render(<TwdSettingsPage />)

    expect(screen.getByRole('heading', { name: 'การตั้งค่าไทวัสดุ' })).toBeInTheDocument()
    const branchSwitch = await screen.findByRole('switch', { name: 'แสดง Branch Unmatch' })
    expect(screen.getByRole('switch', { name: 'แสดง Item Unmatch' })).toHaveAttribute('aria-checked', 'false')
    expect(branchSwitch).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()

    await userEvent.click(branchSwitch)

    await waitFor(() => expect(branchSwitch).toHaveAttribute('aria-checked', 'true'))
    expect(screen.getByRole('status')).toHaveTextContent('นำไปรวมในรายงาน')
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/settings/twd/unmatched-visibility'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          show_unmatched_items: false,
          show_unmatched_branches: true,
        }),
      }),
    )
  })
})
