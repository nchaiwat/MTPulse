# แผนดำเนินงาน MT Pulse

## สรุปโครงการ

สร้าง MT Pulse เป็น Application ภายในแบบ Desktop-first สำหรับวิเคราะห์ยอดขายและสินค้าคงคลังของ TWD งานส่งมอบแรกคือ Frontend ที่ใช้งานและโต้ตอบได้จริงด้วยข้อมูลตัวอย่าง เพื่อให้ผู้ใช้ตรวจสอบ Workflow ก่อนเริ่ม Backend และงานนำเข้าข้อมูล ระบบ Production ในอนาคตจะรันบน Ubuntu VPS และรับไฟล์จาก On-Premise NAS ผ่าน Upload Agent

## เป้าหมายและสิ่งที่ไม่ทำในรอบแรก

### เป้าหมาย

- ตรวจสอบ Performance Workflow ผ่าน React/TypeScript MVP ภาษาอังกฤษ
- สลับมุมมอง `Item × Branch` และ `Item × Day` ได้ทันที
- เข้าถึง Qty และ Amount ที่ระดับ `SKU × Branch × Day` โดย Amount ของระบบเป็นยอด Ex VAT เสมอ
- วางเส้นทางที่เรียบง่ายไปสู่ FastAPI, PostgreSQL และ Upload/Import Worker
- มี Automated Tests และ Reconciliation Fixtures ที่ตรวจผลได้ชัดเจน

### สิ่งที่ไม่ทำใน Frontend Milestone

- Backend API, PostgreSQL, NAS Access, SAP Access หรือ Production Deployment
- Keycloak, Login Screen และ Permission Enforcement
- หน้า Data Status, Matching Administration และ System Settings แบบสมบูรณ์ นอกเหนือจาก Navigation Placeholder
- Modern Trade อื่นนอกจาก TWD

## Technical Architecture

### Frontend MVP

- React + TypeScript สร้างด้วย Vite
- แยก Feature ตามหน้าที่: App Shell, Performance Filters, Matrix และ Detail Drawer
- ใช้ TanStack Table จัดการ Table State และใช้ TanStack Virtual เมื่อ Wide Matrix จำเป็นต้อง Render ข้อมูลปริมาณ Production
- ใช้ CSS Variables สำหรับ Color, Density, Typography, Focus, Status และ Heatmap Tokens
- รอบแรกใช้ Client-side State และ Sample Repository โดยแยก Data Interface ไว้ให้เปลี่ยนเป็น API ภายหลัง

### Target Production Architecture

- Static Frontend ให้บริการผ่าน TLS Reverse Proxy
- FastAPI สำหรับ Reports, Mappings, Imports, Settings, Health และ OIDC Session ในอนาคต
- PostgreSQL เป็น Source of Truth
- Python Import Worker แยก Process โดย Poll/Claim งานจาก PostgreSQL
- On-Premise Python Upload Agent ทำงานตาม OS Scheduler และเชื่อมออกผ่าน HTTPS
- Docker Compose สำหรับ Local Integration และ Single-VPS Production ระยะแรก
- เชื่อม Keycloak เป็น OIDC Provider ภายหลัง โดยเก็บ External Subject และ Application Roles เท่าที่จำเป็น

## แผนไฟล์และ Module

Frontend Milestone จะสร้างเฉพาะโครงสร้างที่จำเป็น:

- `package.json` และ Config ของ TypeScript, Vite, Lint และ Test
- `src/main.tsx` — Application Entry Point
- `src/app/App.tsx` — App Shell และ Navigation
- `src/features/performance/PerformancePage.tsx` — ประกอบหน้า Performance
- `src/features/performance/PerformanceToolbar.tsx` — Mode, Metric, Dimension, Search และ Filters
- `src/features/performance/PerformanceMatrix.tsx` — Sticky Columns และ Branch/Day Matrix
- `src/features/performance/ItemDetailDrawer.tsx` — รายละเอียด SKU/Cell และ Mapping Context
- `src/features/performance/types.ts` — UI Types ที่ระดับ `SKU × Branch × Day`
- `src/features/performance/sampleData.ts` — Deterministic TWD Fixtures จากข้อมูลเดือนสิงหาคม 2026
- `src/styles/tokens.css` และ `src/styles/app.css` — Design Tokens, Dense Desktop Layout, Responsive และ Accessible States
- Component/Behavior Tests วางร่วมกับ Feature หรือตาม Convention ของ Scaffold

Backend ในระยะถัดไปจะแยกขอบเขตเช่น `backend/app/api`, `backend/app/models`, `backend/app/services`, `backend/app/importers/twd` และ `agent/` โดยไม่เพิ่ม Abstraction เหล่านี้ใน Frontend ก่อนจำเป็น

## ร่าง Data Model

### ตารางหลัก

- `modern_trades`: Code, Name และ Active State
- `mt_settings`: Modern Trade, Key, Typed Value, Effective Interval และ Audit Metadata
- `import_batches`: Source Metadata, Checksum, Receipt/Data Date, Status, Counts, Totals, Timestamps, Error และ Warning
- `sales_inventory_facts`: Batch, MT, Data Date, Source Branch/SKU, Source Attributes, Source Amount, Ex VAT Amount, Qty, Stock OH, Stock On Order และ Source Dates
- `mt_items` และ `wa_items`: Item Master ของแต่ละฝั่ง
- `item_mapping_candidates`: Candidate จาก OSCN หรือ Source อื่น
- `item_mappings`: TWD SKU, WA Item, Effective Interval และ Confirmation Metadata
- `mt_branches` และ `wa_branches`: Branch Master ของแต่ละฝั่ง
- `branch_mappings`: Source Branch, WA Branch, Effective Interval และ Confirmation Metadata
- `audit_events`: Actor, Action, Entity, Before/After JSON, Effective Date และ Event Timestamp

### Constraints และ Indexes

- Checksum ต้อง Unique ต่อ Source/Modern Trade
- Fact ต้อง Unique ต่อ Batch, Data Date, Source Branch และ Source SKU
- Index รองรับ Date Range + SKU, Date Range + Branch และ Mapping Status
- Effective Interval ของ SKU หรือ Branch เดียวกันห้ามซ้อนกัน
- ยอดเงินใช้ Decimal/Numeric ห้ามใช้ Binary Floating Point
- Batch Totals เก็บ Full Precision สำหรับ Reconciliation

## แผน API และ Integration

### Report APIs

- `GET /api/performance` รับ Date Range, Mode, Metric, Dimension, SKU Search, Branch และ Mapping Status
- `GET /api/performance/items/{sku}` ส่งรายละเอียด `SKU × Branch × Day` และ Mapping History
- Response เป็น Paginated UI-oriented Shape ที่มี Totals และ Dynamic Dimension Columns

### Mapping APIs

- Endpoint ค้นหา Candidate จาก OSCN และ WA Master
- Endpoint ยืนยัน/เปลี่ยน Mapping แบบ Effective Date พร้อม Optimistic Concurrency และ Audit Event
- Phase 1 อนุญาตหนึ่ง Active WA Item ต่อ TWD SKU ต่อ Effective Interval

### Import APIs และ Jobs

- Authenticated Upload Endpoint รับ Source Metadata, Checksum, Idempotency Key และ Streamed File
- Batch Status Endpoint สำหรับ Agent Acknowledgement และ Retry Decision
- Worker Flow: Claim Batch, Validate, Parse Period, Stage Facts, Reconcile, Commit แบบ Atomic และลบ Temporary File เสมอ
- Duplicate Checksum คืนผล Batch เดิมแทนการ Import ซ้ำ

### Error Handling

- มี Machine Error Code คงที่และข้อความสำหรับ Operator ที่อ่านเข้าใจได้
- Failed Batch เก็บ Metadata และ Diagnostics แต่ไม่เก็บ Temporary Raw File
- Agent ใช้ Bounded Exponential Backoff และไม่ Retry Permanent Validation Error

## ลำดับการพัฒนา

### Phase 1: Frontend Setup

- Scaffold React/TypeScript/Vite และ Pin Versions ตอนเริ่ม Implementation
- เพิ่ม Lint, Unit/Component Tests และ Deterministic Sample Fixtures
- สร้าง Dense-dashboard Design System ที่ Accessible และ Responsive
- ตรวจให้ Empty Application Build และ Test ผ่าน

### Phase 2: Frontend UX Implementation

- สร้างหน้า Performance ภาษาอังกฤษและ Navigation Placeholders
- สร้าง Sales/Inventory และ Metric Switching
- สร้าง Branch/Day Matrix พร้อม Sticky Identity Columns และ Heatmap ที่อ่านตัวเลขได้
- สร้าง Date, Branch, Mapping และ Search Filters
- สร้าง Row/Cell Selection และ Detail Drawer ที่ระดับ `SKU × Branch × Day`
- เพิ่มตัวอย่าง Negative Value, Pending Mapping, Loading, Empty และ No-result State
- เปรียบเทียบผลกับรูป Excel สองภาพและ HTML Prototype เดิม

### Phase 3: Frontend Testing และ Review

- Unit Test Aggregation และ Dimension Switching
- Component Test สำหรับ Filters, Metrics, Negative Values และ Drawer
- ตรวจ Keyboard Navigation, Focus, Labels, Contrast, Horizontal Scroll และ Desktop Layout
- รัน Lint, Type Check, Tests และ Production Build
- ส่ง Working UX ให้ผู้ใช้ตรวจ ก่อนเริ่ม Backend

### Phase 4: Backend และ Database Foundation

- เพิ่ม FastAPI, PostgreSQL, Migrations, Docker Compose, Health Check และ Structured Logging
- สร้าง Schema Constraints และ Report Repository Contracts
- เปลี่ยน Sample Repository เป็น API ทีละส่วน

### Phase 5: TWD Import และ Reconciliation

- ทำ Temporary File Handling, TWD Parser, Period Extraction, VAT, Idempotency, Transactional Import และ Cleanup
- Reconcile ข้อมูลวันที่ 16–17 สิงหาคมกับ `PROJECT_CONTEXT.md`
- Test Duplicate, Negative Rows, Invalid Schema, Failed Reconciliation และ Cleanup ทุก Exit Path

### Phase 6: On-Premise Upload และ Operations

- ทำ Read-only NAS Scanner และ HTTPS Uploader
- ตั้ง Schedule, Machine Credential, Retry, Acknowledgement และ Local Logs
- เพิ่ม Data Status และ Import Diagnostics
- ทดสอบ Deployment บน Ubuntu VPS พร้อม Backup และ Monitoring

### Phase 7: Mapping และ Authentication

- เชื่อม OSCN, WA Item Master และ Branch Master
- ทำ Effective-dated Mapping Workflow และ Audit Views
- เชื่อม Keycloak OIDC และบังคับสิทธิ์ User/Admin/Management

## Dependencies

- Frontend: Node.js LTS, React, TypeScript, Vite, TanStack Table และ TanStack Virtual
- Test: Vitest และ React Component Testing Library
- Backend ระยะถัดไป: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL Driver และ `.xls` Reader ที่พิสูจน์กับไฟล์ TWD แล้ว
- Infrastructure: PostgreSQL และ Docker Compose
- เลือกและ Pin Exact Versions ตอน Scaffold แต่ละ Phase โดยไม่เดาหมายเลข Version ในเอกสารนี้

## Security และ Error Handling

- Agent มีสิทธิ์ Read-only ต่อ NAS และห้ามแก้หรือลบ Source File
- Upload ผ่าน TLS ด้วย Machine Credential ที่ Rotate ได้ พร้อม Checksum, Size Limit และ Idempotency
- Secret อยู่นอก Source Control และ Inject ผ่าน Environment/Secret Configuration
- Temporary Directory จำกัดสิทธิ์และ Cleanup ใน Guaranteed Path
- Commit ข้อมูลเมื่อ Validation และ Reconciliation ผ่านครบเท่านั้น
- Log ห้ามมี Credential หรือ Row-level Business Data ที่ไม่จำเป็น
- เมื่อเชื่อม Keycloak ต้องตรวจ Issuer, Audience, Signature และ Expiry ของ Token

## Deployment Checklist

- ยืนยัน VPS CPU, Memory, Disk, Domain, DNS, Firewall และ TLS
- ตั้ง Production Secrets และ Keycloak Metadata เมื่อถึง Phase นั้น
- ตั้ง PostgreSQL Backup อัตโนมัติและทดสอบ Restore
- Build Immutable Images และ Run Migration ก่อน Rollout
- Smoke Test Health, Report, Upload, Duplicate และ Reconciliation
- ตรวจ Temporary-file Cleanup และ Disk Monitoring
- ตรวจว่า On-Premise Agent Upload ออกได้โดยไม่เปิด Inbound Corporate Firewall
- กำหนด Rollback ทั้ง Application Image และ Database Migration

## ประเด็นที่ยังต้องตัดสินใจ

- OS, Scheduler และ Service Identity ของ On-Premise Agent
- วิธีเชื่อม OSCN/WA Item Master ใน Production
- Branch Master และ Normalization Rules
- Exact Dependency Versions ตอน Implementation
- VPS Sizing, TLS Reverse Proxy, Backup Retention, Monitoring และ Operations Owner
- มี Business Case ที่ต้อง Mapping แบบ One-to-many พร้อมกันหรือไม่

## แผนเพิ่มเติม: Sales Monthly Matrix

### สถานะ: ดำเนินการแล้ว (21 สิงหาคม 2026)

- เพิ่ม `Month` ใน Sales View และซ่อนจาก Inventory
- เพิ่มการรวม Amount/Qty รายเดือนฝั่ง PostgreSQL ผ่าน `grain=month`
- ใช้ `YYYY-MM` เป็น sort key และแสดงผลเป็น `Mon YYYY`
- ตรวจด้วย Frontend Tests, Build, Lint, Backend Tests, API จริง และ Browser interaction แล้ว

### สรุปและ Non-goals

- เพิ่ม Matrix รายเดือนสำหรับ Sales Amount/Qty โดยแสดงทุกเดือนที่มีข้อมูลทันทีและเรียงตาม `YYYY-MM`
- ไม่ทำ Monthly Inventory, ตัวเลือกช่วงเดือน, Forecast หรือ Growth ในรอบนี้

### Technical Architecture

- เพิ่ม `month` ใน Frontend Dimension แต่จำกัดการใช้งานไว้ที่ Mode `sales`
- เพิ่ม Query Parameter สำหรับ Grain/Dimension รายเดือนใน `GET /api/performance`
- เมื่อเป็น Month ให้ Backend รวม `amount` และ `sales_qty` ด้วย PostgreSQL โดย Group ตาม SKU และเดือน พร้อมใช้ Branch filter เดิม
- API คืน Month Key รูปแบบ `YYYY-MM`; Frontend แสดงด้วย `Intl.DateTimeFormat` เป็น `Jan 2025`, `Feb 2025` และเรียงจาก key ไม่เรียงจาก Label
- Query แบบ Month/All Dates ใช้วันที่ต่ำสุดและสูงสุดจริงจาก Fact แทนวันที่ Fixture ที่ hard-code

### File และ Module Plan

- `backend/app/api/performance.py`: รองรับ Monthly aggregation และช่วงข้อมูลทั้งหมด
- `backend/tests/`: เพิ่ม API test สำหรับการรวมเดือน การเรียงข้ามปี Branch filter และค่าติดลบ
- `src/features/performance/types.ts`: เพิ่ม Dimension `month` และชนิด Month Key ที่จำเป็น
- `src/features/performance/performanceApi.ts`: ส่ง Dimension/Grain และไม่ใช้วันที่ตัวอย่างเมื่อ Month เลือกทุกข้อมูล
- `src/features/performance/performanceMath.ts`: รองรับ Month aggregation สำหรับ Fixture/Test โดยใช้ key `YYYY-MM`
- `src/features/performance/PerformanceToolbar.tsx`: เพิ่มปุ่ม `Month` เฉพาะ Sales
- `src/features/performance/PerformanceMatrix.tsx`: สร้างคอลัมน์และ Label เดือนเรียงตามเวลา
- `src/features/performance/PerformancePage.tsx`: จัดการการสลับ Mode/Dimension, Heading และ Page size
- Frontend tests และ sample fixtures: เพิ่มข้อมูลข้ามปีและกรณี Jan 2025–Aug 2026

### Phased Implementation

1. เพิ่ม Backend contract และ tests สำหรับ Monthly aggregation
2. เพิ่ม Frontend type, Month ordering/formatting และ unit tests
3. เพิ่ม Month control และเชื่อม API โดยคง Branch/Date เดิม
4. ตรวจยอดตัวอย่าง Amount/Qty, Heatmap, Horizontal Scroll และ Pagination
5. รัน Backend tests, Frontend tests, Lint, Build และ Browser visual QA

### Verification และ Release Checklist

- ตรวจ `Jan 2025 → Dec 2025 → Jan 2026 → Aug 2026` ว่าเรียงครบและไม่เรียงตามตัวอักษร
- Reconcile Amount/Qty ราย SKU/เดือนและ Total กับ Excel ตัวอย่าง
- ตรวจ All Branch และ Single Branch
- ตรวจ Search, Mapping/Unmap, Description, Heatmap และ Export/Import Mapping ว่าไม่ถดถอย
- ตรวจ Response size/เวลาโหลดด้วยข้อมูลอย่างน้อย 20 เดือน
- ไม่ต้องมี Database Migration หากใช้ Fact และ Index เดิมได้; เพิ่ม Index เฉพาะเมื่อ Query Plan แสดงว่าจำเป็น

### Open Decision

- ไม่มีสำหรับขอบเขตรอบนี้; รอ Product Owner ยืนยันแผนก่อนเริ่ม Implementation

## แผนเพิ่มเติม: Date SUM และ Performance

### สถานะ: ดำเนินการแล้ว (21 สิงหาคม 2026)

- เพิ่มแถว `SUM` ใน Sales Date View ให้แสดง Grand Total และยอดรวมรายวันของ Amount/Qty จากทุก SKU ที่ผ่าน Filter
- เพิ่ม API grain `day_total` เพื่อ Aggregate ตาม SKU และ Date ที่ PostgreSQL ก่อนส่งข้อมูล ลด payload และงานรวมข้อมูลใน Browser
- ยืนยันกับข้อมูลจริงว่าผลรวมรายวันเท่ากับ KPI ด้านบน และ response ลดจากประมาณ 1.16 MB เหลือ 52 KB
- เพิ่ม regression tests สำหรับ Date SUM และการเลือก `grain=day_total`

## แผนเพิ่มเติม: Branch by Month และ Matrix Column Totals

### สถานะ: ดำเนินการแล้ว (21 สิงหาคม 2026)

### สรุปและขอบเขต

- เปลี่ยน Sales Branch View ให้ใช้เดือนเป็นช่วงข้อมูล โดยเลือกเดือนล่าสุดอัตโนมัติและเลือกเดือนอื่นได้
- เพิ่มยอดรวมบนหัว `Total`, Branch และ Month สำหรับ Amount/Qty โดยคำนวณจากทุก SKU ที่ผ่าน Filter
- คง Date View, Inventory, Mapping และชื่อ Branch เดิม; การปรับ Branch Master อยู่นอกขอบเขตรอบนี้

### Technical Architecture

- Backend เพิ่ม monthly branch grain เพื่อ Group ตาม `source_sku + source_branch_code + year + month` ก่อนส่ง Browser
- API คืนรายการเดือนที่มีข้อมูล, เดือนที่เลือก และ `columnTotals` แยก Amount/Qty สำหรับ Branch/Month พร้อมใช้ `summary` เป็น Grand Total
- Branch View ที่ยังไม่ได้ระบุเดือนให้ Backend resolve เป็นเดือนล่าสุดที่มี Fact; Frontend แสดงค่าที่ resolve แล้วใน Month selector
- Month View ใช้ monthly aggregation เดิมและเพิ่มยอดรวมราย Month จากทุก SKU ที่ผ่าน Filter
- Column totals ต้อง Query แยกจาก SKU Pagination เพื่อไม่ให้ยอดเปลี่ยนเมื่อเปลี่ยนหน้า

### File และ Module Plan

- `backend/app/api/performance.py`: เพิ่ม latest-month resolution, branch-month aggregation และ column totals
- `src/features/performance/types.ts`: เพิ่ม API fields สำหรับ available months, selected month และ column totals
- `src/features/performance/performanceApi.ts`: ส่ง month/grain ตาม View
- `src/features/performance/PerformanceToolbar.tsx`: แสดง Month selector สำหรับ Branch View
- `src/features/performance/PerformancePage.tsx`: จัดการเดือนล่าสุด/เดือนที่เลือกและส่ง totals ให้ Matrix
- `src/features/performance/PerformanceMatrix.tsx`: เพิ่ม summary row บนหัวคอลัมน์และใช้ totals จาก Server
- Tests: ครอบคลุม Amount/Qty, Return, latest month, Branch filter, Search/Mapping filter และยอดรวมที่ไม่ขึ้นกับ Pagination

### Phased Implementation

1. เพิ่ม Backend contract และ tests สำหรับ latest month, branch-month cells และ column totals
2. เพิ่ม Frontend types/API state และ Month selector ใน Branch View
3. เพิ่ม summary row บน Matrix สำหรับ Branch และ Month
4. Reconcile ตัวอย่าง 4 ระดับกับ Excel ทั้ง Amount และ Qty
5. รัน Backend/Frontend tests, Lint, Build และ Browser visual QA

### Release Checklist

- Branch View เปิดเดือนล่าสุดและเปลี่ยนเดือนได้
- ยอด Cell, Column Total, Row Total และ Grand Total ตรงกันทุกหน้า Pagination
- Month View เรียงเดือนข้ามปีถูกต้อง
- Amount และ Qty ให้โครงสร้างเดียวกัน รวมค่าติดลบ
- Date View และ Inventory ไม่ถดถอย

### Open Decision

- ไม่มีสำหรับขอบเขตรอบนี้; รอ Product Owner ยืนยันแผนก่อนเริ่ม Implementation
