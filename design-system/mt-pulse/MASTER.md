# ระบบออกแบบ MT Pulse

## แนวคิด

MT Pulse ใช้แนวคิด **Operations Ledger** สำหรับทีมที่ต้องอ่านยอดจำนวนมากตลอดวัน หน้าจอต้องหนาแน่น เป็นระเบียบ และให้ตัวเลขเด่นกว่างานตกแต่ง ไม่ใช้แนว Landing Page, Hero ขนาดใหญ่ หรือ Card ลอยจำนวนมาก

จุดจดจำของระบบคือ **Data Context** ที่แสดงวันข้อมูลล่าสุดใกล้หัวหน้า Page; หน้ารายงานเดิมที่มี Pulse Strip ยังคงใช้ได้โดยไม่เปลี่ยน Workflow

## Design Dials

- Variance: 3/10 — สุขุมและคงเส้นคงวา
- Motion: 2/10 — ใช้เฉพาะ Feedback และ Drawer
- Density: 9/10 — เหมาะกับ Desktop Dashboard และ Wide Matrix

## สี

| หน้าที่ | สี | CSS Token |
|---|---|---|
| Navigation ink | `#102A43` | `--ink-900` |
| Primary sky | `#02ABFF` | `--primary-500` |
| Sky tint | `#E5F6FF` | `--primary-50` |
| Canvas | `#F4F8FB` | `--canvas` |
| Surface | `#FFFFFF` | `--surface` |
| Main text | `#172534` | `--text-900` |
| Muted text | `#617181` | `--text-600` |
| Border | `#D7E0E3` | `--line` |
| Warning | `#A66400` | `--amber-700` |
| Negative/error | `#B73846` | `--red-700` |

- สี Heatmap ใช้ Sky Blue หลายระดับสำหรับค่าบวก และ Red tint สำหรับค่าติดลบ
- ตัวเลขจริงต้องแสดงเสมอ ห้ามใช้สีเพียงอย่างเดียวในการสื่อค่า
- Focus Ring ใช้ `#02ABFF` และต้องเห็นชัดบนทุก Surface

## ตัวอักษร

- UI และหัวข้อภาษาไทย: `Leelawadee UI`, `Aptos`, `Segoe UI`, system sans-serif
- ตัวเลขและรหัส: `Cascadia Mono`, `Consolas`, monospace พร้อม `font-variant-numeric: tabular-nums`
- Type scale มาตรฐาน: Page title 24px/700, Section title 16px/700, KPI 20px/700, Body/Control/Data 12px และ Label/Caption 10px
- ใช้น้ำหนัก 400/600/700 เท่านั้น เพื่อให้แต่ละระดับชัดและหลีกเลี่ยงการสร้างน้ำหนัก Font ปลอม
- Report ใช้ Compact density (Control 34px) ส่วน Dashboard ใช้ Standard density (Control 40px)
- ใช้ Sentence case และลด Letter spacing ของข้อความไทย; ตัวพิมพ์ใหญ่ใช้กับ Label สั้นเท่านั้น

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
- Navigation Rail คงอยู่ด้านซ้ายทุก Breakpoint และย่อเป็น Icon Rail 72px ได้ โดย Expanded เป็นค่าเริ่มต้น
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

## Existing Application Visual Refresh — 1 กันยายน 2026

- Visual Direction: Modern/Clean/Premium Internal SaaS Tool โดยคง Operations Ledger และ Density เดิม
- ใช้ Soft Shadow และ Radius 12–16px เฉพาะ Surface/Control ที่เหมาะสม ไม่ทำทุกส่วนเป็น Card
- หน้า TWD Performance เป็น Visual Template ของ Report สำหรับ TWD, HP และ MH โดยทั้งสามหน้าต้องใช้ Layout, Typography, Density, Surface และ Interaction pattern เดียวกันผ่าน shared component/CSS
- ความสามารถและ Business Logic เฉพาะ MT เช่น Metric capability, Sho/Pro, TOM/TOD, Inventory Month, Mapping และ Data source ให้คงแยกตาม MT เดิม ห้ามเพิ่มหรือลดเพื่อให้หน้าตาเหมือนกัน
- ห้ามเปลี่ยนตำแหน่ง Control, Matrix, Column, Pagination, Drawer หรือ Data Workflow ของ TWD
- รอบนี้ไม่สร้าง Dashboard, Chart, Top SKU หรือ Top Branch
- ไม่เพิ่ม Responsive Behavior ใหม่; Matrix ยังคง Desktop-first และ Horizontal Scroll
- Tailwind/Shadcn ใช้แบบ Incremental โดยห้าม Preflight หรือ Component replacement กระทบหน้า TWD
