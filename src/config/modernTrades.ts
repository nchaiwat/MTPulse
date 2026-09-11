export const MODERN_TRADE_CAPABILITIES = [
  'dashboard',
  'performance',
  'manualImport',
  'folderImport',
  'automaticImport',
  'correctiveImport',
  'mapping',
  'skuBackfill',
  'shoPro',
  'monitoring',
  'settings',
  'excel',
] as const

export type ModernTradeCapability = typeof MODERN_TRADE_CAPABILITIES[number]
export type ModernTradeCode = 'TWD' | 'HP' | 'MH' | 'HH' | 'GH' | 'SCG' | 'TA'
export type ActiveModernTradeCode = 'TWD' | 'HP' | 'MH' | 'HH'

export type ModernTradeDefinition = {
  code: ModernTradeCode
  name: string
  displayName: string
  navigationLabel: string
  sourceGroupCode: string
  sourceOwnerCode: ModernTradeCode
  inventoryMetrics: readonly ('stockOh' | 'stockOnOrder' | 'stockValue')[]
  activeCapabilities: readonly ModernTradeCapability[]
  plannedCapabilities: readonly ModernTradeCapability[]
}

const complete = MODERN_TRADE_CAPABILITIES
const hpMhActive = [
  'dashboard', 'performance', 'manualImport', 'folderImport', 'automaticImport',
  'mapping', 'skuBackfill', 'shoPro', 'monitoring', 'settings', 'excel',
] as const satisfies readonly ModernTradeCapability[]
const hhActive = [
  'dashboard', 'performance', 'manualImport', 'folderImport', 'automaticImport', 'correctiveImport', 'mapping', 'skuBackfill', 'shoPro',
  'monitoring', 'settings', 'excel',
] as const satisfies readonly ModernTradeCapability[]

export const MODERN_TRADES: Readonly<Record<ModernTradeCode, ModernTradeDefinition>> = {
  TWD: {
    code: 'TWD', name: 'Thai Watsadu', displayName: 'TWD', navigationLabel: 'ไทวัสดุ',
    sourceGroupCode: 'TWD', sourceOwnerCode: 'TWD', inventoryMetrics: ['stockOh', 'stockOnOrder'],
    activeCapabilities: complete, plannedCapabilities: [],
  },
  HP: {
    code: 'HP', name: 'HomePro', displayName: 'HomePro (HP)', navigationLabel: 'HomePro',
    sourceGroupCode: 'HP_MH', sourceOwnerCode: 'HP', inventoryMetrics: ['stockOh', 'stockValue'],
    activeCapabilities: hpMhActive, plannedCapabilities: ['correctiveImport'],
  },
  MH: {
    code: 'MH', name: 'MegaHome', displayName: 'MegaHome (MH)', navigationLabel: 'MegaHome',
    sourceGroupCode: 'HP_MH', sourceOwnerCode: 'HP', inventoryMetrics: ['stockOh', 'stockValue'],
    activeCapabilities: hpMhActive, plannedCapabilities: ['correctiveImport'],
  },
  HH: {
    code: 'HH', name: 'HomeHub', displayName: 'HomeHub (HH)', navigationLabel: 'HomeHub',
    sourceGroupCode: 'HH', sourceOwnerCode: 'HH', inventoryMetrics: ['stockOh', 'stockValue'],
    activeCapabilities: hhActive,
    plannedCapabilities: [],
  },
  GH: {
    code: 'GH', name: 'Modern Trade GH', displayName: 'Modern Trade GH (GH)', navigationLabel: 'GH',
    sourceGroupCode: 'GH', sourceOwnerCode: 'GH', inventoryMetrics: [],
    activeCapabilities: [], plannedCapabilities: complete,
  },
  SCG: {
    code: 'SCG', name: 'Modern Trade SCG', displayName: 'Modern Trade SCG (SCG)', navigationLabel: 'SCG',
    sourceGroupCode: 'SCG', sourceOwnerCode: 'SCG', inventoryMetrics: [],
    activeCapabilities: [], plannedCapabilities: complete,
  },
  TA: {
    code: 'TA', name: 'Modern Trade TA', displayName: 'Modern Trade TA (TA)', navigationLabel: 'TA',
    sourceGroupCode: 'TA', sourceOwnerCode: 'TA', inventoryMetrics: [],
    activeCapabilities: [], plannedCapabilities: complete,
  },
}

export const ACTIVE_MODERN_TRADES = (['TWD', 'HP', 'MH', 'HH'] as const)
  .map((code) => MODERN_TRADES[code])

export function activeModernTradeCodes(capability: ModernTradeCapability): ActiveModernTradeCode[] {
  return ACTIVE_MODERN_TRADES
    .filter((definition) => definition.activeCapabilities.includes(capability))
    .map((definition) => definition.code as ActiveModernTradeCode)
}

export function isModernTradeCapabilityActive(
  code: string,
  capability: ModernTradeCapability,
): boolean {
  const definition = MODERN_TRADES[code as ModernTradeCode]
  return Boolean(definition?.activeCapabilities.includes(capability))
}
