import { describe, expect, it } from 'vitest'
import { matrixScrollContentWidth } from './matrixScroll'

describe('matrixScrollContentWidth', () => {
  it('adds the measured vertical scrollbar width to the synchronized top track', () => {
    expect(matrixScrollContentWidth(1_000, 600, 584)).toBe(1_016)
    expect(matrixScrollContentWidth(1_000, 600, 600)).toBe(1_000)
  })
})
