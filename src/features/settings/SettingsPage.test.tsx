import { RoleContext } from '../auth/permissions'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { SettingsPage } from './SettingsPage'

vi.mock('./SystemSettingsPage', () => ({ SystemSettingsPage: () => null }))
vi.mock('./FileShareSettingsCard', () => ({ FileShareSettingsCard: () => null }))
vi.mock('./TwdSettingsPage', () => ({ TwdSettingsPage: () => null }))
vi.mock('./DhPriceMasterPanel', () => ({ DhPriceMasterPanel: () => null }))

it('shows only supported settings scopes and moves keyboard focus from DH to TA', async () => {
  const user = userEvent.setup()
  render(<SettingsPage />)
  expect(screen.getAllByRole('tab')).toHaveLength(8)
  expect(screen.queryByRole('tab', { name: /SCG/ })).not.toBeInTheDocument()
  for (const code of ['Global', 'TWD', 'HP', 'MH', 'HH', 'GH', 'DH', 'TA']) {
    expect(screen.getByRole('tab', { name: new RegExp(`^${code}`) })).toBeInTheDocument()
  }
  await user.click(screen.getByRole('tab', { name: /^DH/ }))
  await user.keyboard('{ArrowRight}')
  expect(screen.getByRole('tab', { name: /^TA/ })).toHaveAttribute('aria-selected', 'true')
})


it('limits operator settings to the seven MT scopes without global secrets', () => {
  render(<RoleContext.Provider value="operator"><SettingsPage /></RoleContext.Provider>)
  expect(screen.queryByRole('tab', { name: /^Global/ })).not.toBeInTheDocument()
  expect(screen.getAllByRole('tab')).toHaveLength(7)
  expect(screen.getByRole('tab', { name: /^TWD/ })).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByRole('heading', { name: 'Central IAM SSO' })).not.toBeInTheDocument()
})
