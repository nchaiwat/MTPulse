const bangkokDate = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'Asia/Bangkok',
})

const bangkokDateTime = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Asia/Bangkok',
})

export function formatDisplayDate(value: string | Date | null | undefined, fallback = '') {
  if (!value) return fallback
  if (typeof value === 'string') {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (match) return match[3] + '/' + match[2] + '/' + match[1]
  }
  const parsed = value instanceof Date ? value : new Date(value)
  return Number.isNaN(parsed.getTime()) ? String(value) : bangkokDate.format(parsed)
}
export function parseDisplayDate(value: string) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim())
  if (!match) return null
  const day = Number(match[1])
  const month = Number(match[2])
  const year = Number(match[3])
  const parsed = new Date(Date.UTC(year, month - 1, day))
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return null
  return match[3] + '-' + match[2] + '-' + match[1]
}


export function formatDisplayDateTime(value: string | Date | null | undefined, fallback = '') {
  if (!value) return fallback
  const parsed = value instanceof Date ? value : new Date(value)
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : bangkokDateTime.format(parsed).replace(',', '')
}
