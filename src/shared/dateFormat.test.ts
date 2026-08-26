import { describe, expect, it } from 'vitest'
import { formatDisplayDate, formatDisplayDateTime, parseDisplayDate } from './dateFormat'

describe('date formatting', () => {
  it('formats a data date as dd/mm/yyyy', () => {
    expect(formatDisplayDate('2026-08-05')).toBe('05/08/2026')
  })

  it('parses dd/mm/yyyy without accepting invalid calendar dates', () => {
    expect(parseDisplayDate('05/08/2026')).toBe('2026-08-05')
    expect(parseDisplayDate('31/02/2026')).toBeNull()
  })

  it('formats a timestamp in Bangkok time', () => {
    expect(formatDisplayDateTime('2026-08-25T03:00:00+00:00')).toBe('25/08/2026 10:00')
  })
})
