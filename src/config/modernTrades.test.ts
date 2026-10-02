import { describe, expect, it } from 'vitest'
import { ACTIVE_MODERN_TRADES, MODERN_TRADE_CAPABILITIES, MODERN_TRADES, activeModernTradeCodes } from './modernTrades'

describe('Modern Trade registry', () => {
  it('contains current and future Modern Trades', () => {
    expect(Object.keys(MODERN_TRADES)).toEqual(['TWD', 'HP', 'MH', 'HH', 'GH', 'DH', 'SCG', 'TA'])
    expect(ACTIVE_MODERN_TRADES.map((item) => item.code)).toEqual(['TWD', 'HP', 'MH', 'HH', 'GH', 'DH', 'TA'])
  })

  it('uses the standard English name for TWD navigation', () => {
    expect(MODERN_TRADES.TWD.navigationLabel).toBe('Thai Watsadu')
  })

  it('gives every capability exactly one state', () => {
    Object.values(MODERN_TRADES).forEach((definition) => {
      expect(definition.activeCapabilities.filter((item) => definition.plannedCapabilities.includes(item))).toEqual([])
      expect(new Set([...definition.activeCapabilities, ...definition.plannedCapabilities])).toEqual(new Set(MODERN_TRADE_CAPABILITIES))
    })
  })

  it('locks shared reporting capabilities to all active MT packages', () => {
    ;['dashboard', 'performance', 'mapping', 'shoPro', 'monitoring', 'settings', 'excel'].forEach((capability) => {
      expect(activeModernTradeCodes(capability as Parameters<typeof activeModernTradeCodes>[0])).toEqual(['TWD', 'HP', 'MH', 'HH', 'GH', 'DH', 'TA'])
    })
  })

  it('keeps HH source identity independent and its remaining gaps explicit', () => {
    expect(MODERN_TRADES.HH.sourceOwnerCode).toBe('HH')
    expect(MODERN_TRADES.HH.plannedCapabilities).toEqual([])
    expect(MODERN_TRADES.GH.activeCapabilities).toEqual(MODERN_TRADE_CAPABILITIES)
    expect(MODERN_TRADES.GH.plannedCapabilities).toEqual([])
    expect(MODERN_TRADES.TA.name).toBe('Thai-Aust')
    expect(MODERN_TRADES.TA.sourceOwnerCode).toBe('TA')
    expect(MODERN_TRADES.TA.activeCapabilities).toEqual(MODERN_TRADE_CAPABILITIES)
    expect(MODERN_TRADES.TA.plannedCapabilities).toEqual([])
  })

  it('keeps DH on the complete shared package with Price Master as its extension', () => {
    expect(MODERN_TRADES.DH.name).toBe('DoHome')
    expect(MODERN_TRADES.DH.sourceOwnerCode).toBe('DH')
    expect(MODERN_TRADES.DH.inventoryMetrics).toEqual(['stockOh'])
    expect(MODERN_TRADES.DH.activeCapabilities).toEqual(MODERN_TRADE_CAPABILITIES)
    expect(MODERN_TRADES.DH.plannedCapabilities).toEqual([])
    expect(ACTIVE_MODERN_TRADES.map((item) => item.code)).toContain('DH')
  })
})
