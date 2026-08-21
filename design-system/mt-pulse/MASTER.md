# ระบบออกแบบ MT Pulse

## แนวคิด

MT Pulse ใช้แนวคิด **Operations Ledger** สำหรับทีมที่ต้องอ่านยอดจำนวนมากตลอดวัน หน้าจอต้องหนาแน่น เป็นระเบียบ และให้ตัวเลขเด่นกว่างานตกแต่ง ไม่ใช้แนว Landing Page, Hero ขนาดใหญ่ หรือ Card ลอยจำนวนมาก

จุดจดจำของระบบคือ **Pulse Strip** แถบสถานะข้อมูลแนวนอนใต้ Header ซึ่งบอก Data Date, File Arrival, Completeness และ Import Result ในตำแหน่งเดียวก่อนเริ่มอ่าน Matrix

## Design Dials

- Variance: 3/10 — สุขุมและคงเส้นคงวา
- Motion: 2/10 — ใช้เฉพาะ Feedback และ Drawer
- Density: 9/10 — เหมาะกับ Desktop Dashboard และ Wide Matrix

## สี

| หน้าที่ | สี | CSS Token |
|---|---|---|
| Navigation ink | `#10263D` | `--ink-900` |
| Primary teal | `#087F75` | `--teal-600` |
| Teal tint | `#DDF2EF` | `--teal-100` |
| Canvas | `#F3F6F5` | `--canvas` |
| Surface | `#FFFFFF` | `--surface` |
| Main text | `#172534` | `--text-900` |
| Muted text | `#617181` | `--text-600` |
| Border | `#D7E0E3` | `--line` |
| Warning | `#A66400` | `--amber-700` |
| Negative/error | `#B73846` | `--red-700` |

- สี Heatmap ใช้ Teal หลายระดับสำหรับค่าบวก และ Red tint สำหรับค่าติดลบ
- ตัวเลขจริงต้องแสดงเสมอ ห้ามใช้สีเพียงอย่างเดียวในการสื่อค่า
- Focus Ring ใช้ `#087F75` และต้องเห็นชัดบนทุก Surface

## ตัวอักษร

- UI และหัวข้อ: `Aptos`, `Segoe UI`, system sans-serif
- ตัวเลขและรหัส: `Cascadia Mono`, `Consolas`, monospace พร้อม `font-variant-numeric: tabular-nums`
- Base font 14px บน Desktop เพื่อรองรับ Density สูง แต่ Control สำคัญต้องมีพื้นที่กดอย่างน้อย 40px
- ใช้ Sentence case และข้อความภาษาอังกฤษที่ตรงกับสิ่งที่ผู้ใช้ควบคุม

## Layout

```text
┌ Navigation rail ┬ Top bar: page / context / user ───────────────┐
│ Performance     ├ Pulse strip: data date | arrival | status      │
│ Data status     ├ Mode + Metric + View controls                  │
│ Matching        ├ KPI ledger                                     │
│ Settings        ├ Filters                                        │
│                 ├ Sticky identity │ Total │ Branch or Day matrix │
└─────────────────┴─────────────────────────────────────────────────┘
```

- Desktop ใช้ Navigation Rail ทางซ้ายเพื่อเหลือพื้นที่แนวตั้งให้ Matrix
- Matrix เป็น Surface หลัก ไม่วางใน Card ที่มี Decoration หนา
- Sticky Identity Columns และ Header ต้องแยกจาก Numeric Cells อย่างชัดเจน
- Detail Drawer เปิดจากด้านขวาและไม่ทำให้ผู้ใช้เสีย Filter Context
- Mobile ยอมให้ Matrix Scroll แนวนอนภายใน Wrapper โดย Shell ต้องไม่ล้น Viewport

## Interaction

- Hover/Focus Transition 150–200ms และเคารพ `prefers-reduced-motion`
- ทุกปุ่มมี Visible Focus และ `cursor: pointer`
- Segmented Controls ใช้ `aria-pressed`; Drawer มีชื่อและปุ่ม Close ที่อ่านได้
- Cell ที่คลิกได้ต้องเป็น Button หรือมี Keyboard Equivalent
- Empty State ต้องบอกวิธีแก้ เช่น Clear filters
- Heatmap เปิด/ปิดได้

## สิ่งที่ห้ามใช้

- Hero, Marketing CTA, Gradient ขนาดใหญ่ หรือ Oversized Typography
- Card Grid แบบ Template ทั่วไปและ Border Radius มากเกินจำเป็น
- Emoji เป็น Icon
- Animation เพื่อการตกแต่ง
- Heatmap ที่ซ่อนตัวเลขหรือใช้สีเป็นข้อมูลเพียงอย่างเดียว
- Hover ที่ทำให้ Layout Shift

## Checklist ก่อนส่งมอบ

- [ ] Branch/Day, Sales/Inventory และทุก Metric สลับได้ด้วย Keyboard
- [ ] Numeric Cells ใช้ Tabular Numbers และค่าติดลบแยกชัดเจน
- [ ] Sticky Columns/Headers ทำงานใน Horizontal Scroll
- [ ] Focus Contrast ผ่านและไม่มีการลบ Outline
- [ ] Drawer ปิดได้ด้วยปุ่ม Close และ Escape
- [ ] รองรับ 375, 768, 1024 และ 1440px โดย App Shell ไม่ล้น
- [ ] เคารพ `prefers-reduced-motion`
