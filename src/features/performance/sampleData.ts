import type { Branch, PerformanceItem, PerformanceResponse } from './types'

export const branches: Branch[] = [
  { id: '60920', name: 'บางนา' },
  { id: '60926', name: 'ลำปาง' },
  { id: '60930', name: 'ชะอำ' },
  { id: '60982', name: 'สงขลา' },
  { id: '60995', name: 'สระแก้ว' },
]

export const dates = ['2026-08-16', '2026-08-17']

const point = (
  date: string,
  branchId: string,
  amount: number,
  qty: number,
  stockOh: number,
  stockOnOrder: number,
) => ({ date, branchId, amount, qty, stockOh, stockOnOrder })

export const performanceItems: PerformanceItem[] = [
  {
    sku: '60424005',
    twdDescription: 'หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA 4 บาน มีมุ้ง FSSF',
    waItem: 'FAE32-W22512-180110',
    waDescription: 'FA ECO FRAME X หน้าต่าง FSSF + เหล็กดัดลายกนก มีมุ้ง สีขาว 180 × 110 รุ่นใหม่',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 21400, 6, 7, 0),
      point('2026-08-16', '60926', 10700, 3, 3, 0),
      point('2026-08-16', '60930', 21400, 6, 4, 2),
      point('2026-08-17', '60920', 14200, 4, 8, 0),
      point('2026-08-17', '60982', 7100, 2, 2, 0),
      point('2026-08-17', '60995', 10700, 3, 5, 0),
    ],
  },
  {
    sku: '60424006',
    twdDescription: 'หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA 4 บาน มีมุ้ง FSSF',
    waItem: 'FAE32-W22514-180110',
    waDescription: 'FA ECO FRAME X หน้าต่าง FSSF + เหล็กดัดลายกนก มีมุ้ง สีขาว 180 × 110 รุ่นใหม่',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 17200, 5, 5, 0),
      point('2026-08-16', '60930', 6880, 2, 4, 0),
      point('2026-08-17', '60926', 10320, 3, 3, 0),
      point('2026-08-17', '60982', 13760, 4, 4, 1),
    ],
  },
  {
    sku: '60406627',
    twdDescription: 'หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA 2 บาน มีมุ้ง SS เหล็กดัดลายโมเดิร์น',
    waItem: 'FAE32-W14414-120110',
    waDescription: 'FA ECO FRAME X หน้าต่าง SS + เหล็กดัดลายโมเดิร์น มีมุ้ง สีดำ 120 × 110 รุ่นใหม่',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 48600, 12, 18, 3),
      point('2026-08-16', '60930', 24300, 6, 9, 0),
      point('2026-08-17', '60920', 32400, 8, 17, 2),
      point('2026-08-17', '60926', 12150, 3, 6, 0),
      point('2026-08-17', '60982', 12150, 3, 5, 0),
    ],
  },
  {
    sku: '60406629',
    twdDescription: 'หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA 2 บาน มีมุ้ง SS สีดำ',
    waItem: 'FAE32-W12114-120110',
    waDescription: 'FA ECO FRAME X หน้าต่าง SS + เหล็กดัดลายยอดคฤหาสน์ มีมุ้ง สีดำ 120 × 110 รุ่นใหม่',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 62130, 15, 22, 4),
      point('2026-08-16', '60926', 24852, 6, 8, 0),
      point('2026-08-17', '60920', 41420, 10, 20, 2),
      point('2026-08-17', '60930', 28994, 7, 10, 0),
      point('2026-08-17', '60995', 12426, 3, 5, 0),
    ],
  },
  {
    sku: '60358971',
    twdDescription: 'ไม่มีรายละเอียด TWD',
    waItem: 'FAE09-W6612-100100',
    waDescription: 'FA ECO FRAME X หน้าต่าง SS + เหล็กดัดลายทะเล มีมุ้ง สีขาว 100 × 100 รุ่นใหม่',
    mappingStatus: 'pending',
    points: [
      point('2026-08-16', '60920', 8300, 2, 4, 0),
      point('2026-08-17', '60920', -4150, -1, 3, 0),
      point('2026-08-17', '60930', 8300, 2, 2, 0),
      point('2026-08-17', '60982', 8300, 2, 2, 0),
    ],
  },
  {
    sku: '60358968',
    twdDescription: 'ไม่มีรายละเอียด TWD',
    waItem: null,
    waDescription: null,
    mappingStatus: 'unmatched',
    points: [
      point('2026-08-16', '60926', 5400, 1, 1, 0),
      point('2026-08-17', '60930', 16200, 3, 4, 1),
      point('2026-08-17', '60995', 5400, 1, 2, 0),
    ],
  },
  {
    sku: '60400218',
    twdDescription: 'หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA 2 บาน มีมุ้ง SS ECO 100 × 100',
    waItem: 'FAE00-W0112-100100',
    waDescription: 'FA ECO หน้าต่างอลูมิเนียม SS มีมุ้ง สีดำ 100 × 100 รุ่นใหม่',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 119680, 28, 34, 6),
      point('2026-08-16', '60926', 47017, 11, 12, 0),
      point('2026-08-16', '60930', 25646, 6, 9, 0),
      point('2026-08-17', '60920', 141050, 33, 37, 4),
      point('2026-08-17', '60926', 38469, 9, 13, 0),
      point('2026-08-17', '60982', 42743, 10, 10, 2),
      point('2026-08-17', '60995', 21372, 5, 8, 0),
    ],
  },
  {
    sku: '60310022',
    twdDescription: 'ช่องแสง อลูมิเนียม WINDOW ASIA สีขาว 150 × 40',
    waItem: 'FA09-F1002-150040',
    waDescription: 'FA FRAME X ช่องแสง สีขาว 150 × 40',
    mappingStatus: 'confirmed',
    points: [
      point('2026-08-16', '60920', 11200, 4, 6, 0),
      point('2026-08-17', '60920', 8400, 3, 5, 0),
      point('2026-08-17', '60930', 5600, 2, 4, 0),
    ],
  },
]

export const samplePerformanceResponse: PerformanceResponse = {
  branches,
  dates,
  items: performanceItems,
  meta: { page: 1, pageSize: 100, totalSkus: 2043, totalPages: 21, totalBranches: 102 },
  summary: { amount: 942009, qty: 232, mappingAttention: 2 },
  latestImport: {
    dataDate: '2026-08-17',
    status: 'imported_with_warnings',
    rowCount: 12561,
    warnings: ['Stock On Hand: calculated=77941.0, source=77416'],
  },
}
