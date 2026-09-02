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

## แผนเพิ่มเติม: Manual Import และ Telegram Notification

### Scope และ Non-goals

- เพิ่ม Central Manual Upload สำหรับ TWD ครั้งละหนึ่งไฟล์ พร้อม Preview และ Confirm
- เพิ่ม Activity Log และ Telegram System Setting/Test Notification
- ไม่ทำ Agent, MT อื่น, Replace, Role Enforcement หรือ Daily Summary Scheduler ในรอบนี้

### Technical Architecture

- Frontend ส่งไฟล์เดิมสองครั้ง: Preview และ Confirm เพื่อไม่เก็บ Raw File ค้างบน Server ระหว่างรอ User
- Backend ตรวจ checksum และโครงสร้างซ้ำตอน Confirm; Browser ส่ง expected checksum เพื่อกันไฟล์เปลี่ยน
- ใช้ `extract_twd_file` และ Import Pipeline เดิมเป็น Source of Truth สำหรับการคำนวณ
- ใช้ `AuditEvent` บันทึก Activity ที่สำคัญ และมี Read API แปลงเป็นข้อความสำหรับผู้ใช้
- Telegram Adapter เป็น best-effort side effect หลัง Transaction; ความล้มเหลวของ Telegram ห้ามทำให้ Fact Rollback
- Bot Token เข้ารหัสก่อนเก็บ โดย Encryption Key มาจาก Environment และ API คืนเฉพาะสถานะ configured

### File และ Module Plan

- `backend/app/api/imports.py`: Preview, Confirm และ Activity API
- `backend/app/api/system_settings.py`: Telegram Settings และ Test Message API
- `backend/app/services/twd_import.py`: Import จาก Extract และ Duplicate MT+Period
- `backend/app/services/telegram.py`: Secret encryption และ Telegram sender
- `backend/app/models.py` + Alembic: System Setting และ Unique MT+Period
- `src/features/imports/`: Upload, Preview, Confirm และ Activity Log
- `src/features/settings/`: System Setting สำหรับ Telegram
- `src/app/App.tsx`: เปิด Submenu `สถานะข้อมูล > นำเข้าข้อมูล` และ `การตั้งค่า > ระบบ`

### UI Direction

- ใช้ Design Token และ Typography เดิมทั้งหมด
- หน้ามีลำดับเดียว `เลือกไฟล์ → ตรวจสอบ → ยืนยัน → ผลลัพธ์`; Preview เป็น signature element ของหน้า
- Log อยู่ใต้ Workflow และใช้ Status/เวลา/ข้อความตรงไปตรงมา ไม่แสดง Technical Detailโดย Default

### Verification

1. Tests สำหรับ Preview ที่ไม่เขียน Fact, Confirm, checksum duplicate และ MT+Period duplicate
2. Tests สำหรับ Telegram secret masking, no-config, send failure และ Test Message
3. Frontend tests สำหรับ Navigation, Preview, Confirm, Error และ Log
4. รัน Backend tests/Ruff, Frontend tests/Lint/Build และ Browser QA
5. ทดสอบกับไฟล์ TWD จริงโดยใช้ Preview ก่อน; ห้าม Confirm ไฟล์ Period เดิมในฐานข้อมูล

# System Monitoring — Phase 1 Implementation Plan

## สรุป

เพิ่มหน้า `Monitoring` แบบ Read-only เป็น Main Menu แยก ใช้ข้อมูลจริงจาก FastAPI และ PostgreSQL เปิด `pg_stat_statements` สำหรับ Slow Query และเก็บ Snapshot วันละหนึ่งรายการย้อนหลัง 365 วัน งาน Backup/Restore และ Maintenance Actions ยังเป็นงานภายหลัง

## Architecture

- Frontend: เพิ่ม `MonitoringPage`, API client, Loading/Error/Empty state และปุ่ม Refresh
- Backend: เพิ่ม Monitoring API และ service สำหรับอ่าน PostgreSQL statistics โดย Query แบบ read-only
- PostgreSQL: เปิด `shared_preload_libraries=pg_stat_statements` และสร้าง Extension ผ่าน Migration
- Snapshot: ตาราง `monitoring_snapshots` มี Unique ต่อ `snapshot_date`, เก็บเวลาจับข้อมูล, trigger, health summary, database metrics, MT status และ Top Queries
- Daily capture: เรียก service หลัง Import สำเร็จ; หากยังไม่มี Snapshot ของวันนั้น ให้สร้างเมื่อเปิด Monitoring; Manual Refresh ใช้ Upsert แถวของวันปัจจุบัน
- Retention: ลบ Snapshot ที่เก่ากว่า 365 วันเฉพาะเมื่อมีการ Capture ใหม่

## API Plan

- `GET /api/monitoring` — อ่าน Current Health พร้อม History และสร้าง Daily Snapshot หากวันนั้นยังไม่มี
- `POST /api/monitoring/refresh` — คำนวณใหม่และ Upsert Snapshot ของวันนี้
- Response แยก `health`, `database`, `modernTrades`, `slowQueries`, `history` เพื่อให้ Frontend แสดงผลโดยไม่คำนวณ Business Status ซ้ำ

## UI Plan

- Main Menu: `Monitoring`
- Header: เวลาที่ตรวจล่าสุดและปุ่ม `Refresh`
- Row 1: Health Cards สำหรับ API, PostgreSQL, Data Date, Import และ Warning
- Row 2: Database Size, Fact Records, Table/Index Size, Dead Tuples และ Connections
- Section: Top 10 Slow Queries พร้อม Query ย่อ, Calls, Average, Total และ Rows
- Section: Daily History ย้อนหลัง 365 วัน เรียงวันล่าสุดก่อน
- ใช้สี Healthy/Warning/Critical ตาม Design System เดิมและไม่แก้หน้าปัจจุบัน

## Phases

1. Migration และ PostgreSQL configuration สำหรับ `pg_stat_statements` และ `monitoring_snapshots`
2. Monitoring service/API พร้อม Daily Upsert, Import hook และ Retention
3. Main Menu และ Monitoring UI
4. Backend/Frontend tests, API verification, build และตรวจ Diff

## Test Plan

- API/Database unavailable, Warning threshold และ Healthy state
- Daily Snapshot ไม่สร้างข้อมูลซ้ำ และ Manual Refresh เป็น Upsert
- Retention ไม่เกิน 365 วัน
- Import สำเร็จเรียก Snapshot โดยไม่ทำให้ Import ล้มเหลวหาก Monitoring มีปัญหา
- Slow Query response จำกัด Top 10 และไม่แสดงค่าพารามิเตอร์จริง
- Frontend แสดง Loading/Error/Health/History และ Refresh ได้
- Full backend/frontend regression, lint และ production build

## Out of Scope

- Maintenance commands, Backup/Restore, Host Disk Free, Auto Refresh, Hourly History และ Authentication

# สินค้าทดลองและตัวเลือกหลาย SKU — Implementation Plan

## สรุป

เพิ่ม Metadata ของ Item ที่เป็นอิสระจาก Mapping Status เพื่อรองรับสินค้าทดลองและการซ่อนย้อนหลังแบบไม่ลบข้อมูล พร้อมเปลี่ยนช่องค้นหา Item เดิมเป็น Searchable Multi-select SKU โดยคง Filter และ Matrix อื่นทั้งหมดไว้ตามเดิม

## Data Model และ Migration

- เพิ่ม `item_type` ค่าเริ่มต้น `normal` และ `report_status` ค่าเริ่มต้น `active` ใน Item Mapping
- ทำ Migration ให้ Mapping เดิมทุกแถวเป็น `normal + active`
- ใช้สถานะล่าสุดของ Item เป็น Global Report Scope; `inactive` ถูกตัดออกจากทุกช่วงวันที่
- สร้าง Audit Event เมื่อ Import Excel เปลี่ยน Item Type หรือ Report Status

## Excel Mapping Plan

- เพิ่ม Column `Item Type` และ `Report Status` ใน Sheet `Item Mapping`
- Parser รองรับไฟล์เก่าที่ไม่มี Column และช่องว่าง โดย Default เป็น `normal + active`
- Validate เฉพาะค่า `normal/trial` และ `active/inactive`; ค่าอื่นต้องแสดง Error พร้อมเลขแถวและไม่เปลี่ยนข้อมูล
- Export ต้องรวม Item inactive เพื่อให้ User เปิดกลับเป็น active ได้
- Import ต้องอัปเดต Metadata ของ Mapping เดิมได้โดยไม่เปลี่ยน WA Item Code และไม่ทำลายกติกาห้ามแก้ Mapping ทับ

## API และ Query Plan

- เพิ่ม API อ่านรายการ SKU ที่ Active สำหรับ Multi-select พร้อม Search และ Pagination/Limit
- `GET /api/performance` รับ SKU หลายรหัสแบบมีขอบเขต และใช้ Filter เดียวกันกับ Summary, Column Totals, Matrix, Pagination และ Export
- ทุก Query รายงานต้อง Join/อ้างอิง Item Scope เพื่อไม่รวม `inactive` แม้ดูย้อนหลัง
- Response Item เพิ่ม `itemType` เพื่อให้ Frontend แสดง Badge โดยไม่อนุมานจากสีหรือรหัส
- จำกัดจำนวน SKU ต่อ Request และใช้ Index ที่เหมาะสม; ตรวจ Query Plan กับข้อมูลจริงก่อนเพิ่ม Index

## Frontend Plan

- เปลี่ยนช่องค้นหาเดิมเป็น `SkuMultiSelect` แบบ Searchable Dropdown
- แสดง `ทุก SKU` หรือ `เลือก N SKU`; มี Checkbox, เลือกทั้งหมดจากผลค้นหา, ล้างการเลือก, ยกเลิก และแสดงผล
- ใช้ Draft Selection ภายใน Dropdown และเรียก API เมื่อกดแสดงผลเท่านั้น
- ใช้ Virtual Scroll สำหรับรายการ SKU และเก็บค่าที่เลือกใน Current View
- Item Type `trial` ใช้พื้นเหลืองอ่อนเฉพาะส่วน Item พร้อม Badge `สินค้าทดลอง`; Cell ตัวเลขและ Heatmap ไม่เปลี่ยน

## File และ Module Plan

- `backend/app/models.py` + Alembic: Item metadata และค่า Default
- `backend/app/services/item_mapping_exchange.py`: Excel columns, validation, update และ Audit
- `backend/app/api/item_mappings.py`: Export Metadata ทั้ง Active/Inactive
- `backend/app/api/performance.py`: Global active scope, multi-SKU filter และ Item Type response
- `backend/app/services/performance_export.py`: ใช้ Filter SKU/Active ชุดเดียวกับหน้ารายงาน
- `src/features/performance/`: Multi-select component, API contract, persisted state และ Trial style
- Backend/Frontend tests: Excel compatibility, report totals, inactive historical exclusion และ multi-select consistency

## Phased Implementation

1. เพิ่ม Migration, Model และ Excel Import/Export พร้อม Regression Tests
2. บังคับ Active Scope ใน Performance/Download และ Reconcile KPI, SUM, Matrix ย้อนหลัง
3. เพิ่ม SKU Options API และ Searchable Multi-select แบบ Server-side/Virtualized
4. เพิ่ม Trial Badge/สีเฉพาะ Item และ Current View persistence
5. รัน Backend/Frontend tests, Lint, Build, API จริง, Microsoft Excel compatibility และ Browser QA

## Verification

- Excel เก่าไม่มี Column ใหม่ยัง Import ได้และกลายเป็น `normal + active`
- `trial + active` รวมยอดเท่ากับ Item ปกติและแสดง Badge โดย Heatmap ไม่เปลี่ยน
- เปลี่ยนเป็น `inactive` แล้วหายจากทุกช่วงเวลา, KPI, SUM, Download และ SKU selector แต่ยังอยู่ใน Mapping Export
- เปลี่ยนกลับเป็น `active` แล้วข้อมูลย้อนหลังกลับมาแสดงครบ
- เลือก SKU ที่รหัสไม่คล้ายกันหลายรายการแล้ว KPI, SUM, Matrix และ Download ตรงกัน
- Branch, Date Range, Month, Description, Pagination, Current View และ Performance เดิมไม่ถดถอย

## Out of Scope

- หน้า Setting สำหรับแก้ Metadata ทีละ Item
- การใช้ Excel Cell Color เป็นสถานะ
- การลบ Fact หรือ Mapping ของ Item inactive
- การเปลี่ยน UX/Logic ของ Branch, Date/Month และ Heatmap ที่ไม่เกี่ยวข้อง

# FileShare/UNC Connection — Phase 1 Implementation Plan

## สรุป

เพิ่ม Zone `FileShare` ใน System Settings ให้ Development Admin บันทึกและทดสอบ Base UNC/Credential กลาง พร้อมกำหนด Subfolder ต่อ MT โดยยังไม่ Scan หรือ Import ไฟล์จาก UNC และไม่เปลี่ยน Functional/UI ที่ทำงานดีอยู่แล้ว

## Goals และ Non-goals

### Goals

- เก็บ Base UNC และ NAS Credential ชุดเดียวสำหรับทุก MT อย่างเข้ารหัส
- เก็บ Source Subfolder ต่อ MT เช่น `TWD` และประกอบ Full UNC ฝั่ง Backend
- ทดสอบ Read-only access จาก API Container ไปยัง Base UNC และ MT Folder
- แสดง Secret Reveal เฉพาะ Development/Test Flag และวาง Authorization Boundary สำหรับ AD ในอนาคต
- บันทึก Audit Event สำหรับ Save และ Test Connection

### Non-goals

- Initial Import, Scheduled Import, Background Worker, Retry หรือ File Claim
- AD Login/User Management implementation ในรอบนี้
- การปรับ Report, Mapping, Monitoring, Telegram หรือ Manual Upload เดิม

## Technical Architecture

- เพิ่ม `MTPULSE_AUTH_MODE=development|ad`; Phase นี้ใช้ `development` และ Backend dependency คืน Development System Admin โดยไม่ใช้ Credential ที่ Hard Code ใน Source
- Admin FileShare endpoints อยู่ใต้ Authorization dependency เดียวกัน เพื่อเปลี่ยนเป็น AD Session/Role ได้ภายหลังโดยไม่รื้อ Business Service
- Backend เชื่อม SMB โดยตรงจาก Container ไป TCP 445 ตามค่าที่เก็บในฐานข้อมูล ไม่พึ่ง Windows User Session และไม่ต้อง Restart Docker เมื่อแก้ Path
- ใช้ Encryption Service/Server Key ชุดเดียวกับ System Secret ที่มีอยู่ แต่แยก Setting Keys และ Audit Payload ออกจาก Telegram
- Test Connection ทำเฉพาะ Connect/List/Read Metadata; ห้ามสร้าง, แก้, ย้าย หรือลบไฟล์บน NAS
- ตั้ง Timeout และคืน Error Category เช่น DNS/Network, Authentication, Share Not Found, Permission Denied และ MT Folder Missing

## Data Model Draft

- System FileShare Settings: Base UNC, Domain, Username, Encrypted Password, Configured At/By, Last Tested At และ Last Test Result
- Modern Trade Source Profile: `modern_trade_id`, `source_subfolder`, Enabled และ Audit Metadata
- ไม่เก็บ Full UNC ซ้ำต่อ MT; Backend ประกอบจาก Base UNC + Subfolder และ Validate ป้องกัน Path Traversal
- Password และ Secret ห้ามปรากฏใน Audit `before_json`/`after_json`

## API Plan

- `GET /api/admin/fileshare-settings` — คืนค่าที่ Mask แล้วและสถานะ Configured/Test ล่าสุด
- `PUT /api/admin/fileshare-settings` — บันทึก Base UNC/Domain/Username และแทน Password เฉพาะเมื่อส่งค่าใหม่
- `POST /api/admin/fileshare-settings/test` — ทดสอบ Credential ที่บันทึกหรือ Draft ที่ Admin กำลังกรอก โดยไม่ Persist Draft อัตโนมัติ
- `GET /api/admin/modern-trades/sources` — อ่าน Subfolder และ Test Status ของทุก MT
- `PUT /api/admin/modern-trades/{code}/source` — บันทึก Subfolder ของ MT
- ทุก Endpoint ใช้ Admin dependency และสร้าง Audit Event ตามความเหมาะสม

## UI Plan

- System Settings เพิ่มกรอบ `FileShare` แยกจากกรอบ `Telegram`
- Fields: Base UNC, Domain, Username, Password พร้อมปุ่มลูกตาตาม Environment Flag
- แสดงสถานะ Configured, Last Tested และปุ่ม `ทดสอบการเชื่อมต่อ`
- ภายในกรอบเดียวกันแสดง MT Source Profiles เป็นรายการ MT Code/Name, Subfolder, Full Path Preview และผลทดสอบ
- ใช้ Layout/Design Token เดิมและไม่เพิ่มเมนูหลักใหม่

## File และ Module Plan

- `backend/app/config.py`: Auth mode และ Secret Reveal safeguards
- `backend/app/models.py` + Alembic: FileShare Settings/MT Source Profile fields หรือ tables
- `backend/app/api/`: Admin FileShare/MT Source endpoints
- `backend/app/services/`: Secret persistence, UNC normalization และ SMB test adapter
- `backend/app/main.py`: register router
- `src/features/settings/`: FileShare Zone, API client, Save/Test states และ masked secret UX
- Tests: encryption/masking, path validation, role boundary, SMB error mapping, Audit และ UI states

## Phased Implementation

1. เพิ่ม Config, Migration, Models และ encrypted settings พร้อม unit tests
2. เพิ่ม SMB adapter และ Test Connection API โดย mock network ใน automated tests
3. เพิ่ม Admin APIs, Audit Log และ MT Source Profile
4. เพิ่ม FileShare Zone ใน System Settings โดยไม่แก้ Telegram Zone
5. ทดสอบกับ UNC จริงจาก Test Server, รัน full regression, lint/build และ deploy หลัง Backup

## Verification และ Release Checklist

- Migration upgrade/downgrade ผ่านบนฐานข้อมูลสำเนา
- Password ถูกเข้ารหัส, ไม่อยู่ใน API/log/audit และช่องว่างไม่ลบค่าที่บันทึกเดิม
- Development Secret Reveal ทำงานเมื่อ Flag เปิด และถูกปฏิเสธเมื่อ Flag ปิด
- ทดสอบ `\\WA-NAS-IT03\FileShare-2\SaleOut_RPT\TWD` จาก Test Server แบบ Read-only ได้
- Wrong Password, DNS/Port 445, Share/Folder ไม่พบ และ Permission Denied แสดงสาเหตุแยกกัน
- Report, Manual Upload, Mapping, Monitoring และ Telegram regression tests ผ่าน

## Phase ถัดไปหลัง Phase 1

- AD Authentication, User Profile และ Roles: System Admin, Data Operator, Viewer
- Bootstrap Admin จาก `.env.server`
- Initial Import แบบ Preview/Confirm ครั้งเดียว
- Daily Scheduled Import เวลาเดียวสำหรับทุก MT พร้อม Idempotency, Log และ Telegram Summary

## Open Decisions

- AD Server/Domain, LDAPS/StartTLS และ Username format จะกำหนดเมื่อเริ่ม Authentication Phase
- เลือกและ Pin SMB client dependency หลังพิสูจน์การเชื่อมต่อกับ NAS จริงบน Test Server

# Existing Application Visual Refresh — Implementation Plan

## สรุป

ปรับ Visual ของ MT Pulse เดิมให้เป็น Modern/Clean/Premium โดยคง React + Vite เพิ่ม Tailwind CSS และ Shadcn/UI foundation แบบ Incremental และไม่สร้าง Dashboard หรือ Feature ใหม่ หน้า TWD Performance ใช้ CSS-only visual skin และห้ามเปลี่ยน Component/Function/Logic โดยเด็ดขาด

## Goals และ Non-goals

### Goals

- Primary `#02abff`, Navy Navigation, Neutral Canvas/Surface และ Soft Semantic Colors
- ปรับ Typography, Border, Radius, Soft Shadow, Hover, Focus และ Feedback States ให้สม่ำเสมอ
- ปรับ App Shell, Import, Monitoring และ Settings เฉพาะ Presentation
- รักษา Information Density ของ Operational Tool และตัวเลขแบบ Tabular

### Non-goals

- Dashboard ภาพรวม, Dashboard ราย MT, Top SKU, Top Branch หรือ Chart ใหม่
- Business Logic, Backend, API Contract, Data Model หรือ Workflow ใหม่
- Responsive Redesign
- Refactor หรือเปลี่ยน Shadcn Component ในหน้า TWD Performance

## Technical Direction

- เพิ่ม Tailwind ผ่าน Vite โดยไม่ใช้ Preflight กับ DOM เดิม เพื่อลดความเสี่ยง CSS Regression
- เพิ่ม Shadcn-compatible token/utilities foundation สำหรับการใช้งาน Incremental ในหน้าอื่นและงานอนาคต
- คง stylesheet เดิมและเพิ่ม Visual Override Layer ที่โหลดท้ายสุด แทนการรื้อ CSS/Component เดิม
- ใช้ CSS Variable เป็น Source of Truth และเก็บ Compatibility Alias สำหรับชื่อ Token เดิม
- จำกัด Motion ที่ 150–200ms และเคารพ `prefers-reduced-motion`

## File Allowlist

- Documentation: `PRD.md`, `implementation_plan.md`, `design-system/mt-pulse/MASTER.md`
- Tooling/Foundation: `package.json`, `package-lock.json`, `vite.config.ts`, `components.json`, `src/lib/utils.ts`
- Presentation: `src/main.tsx`, `src/styles/tokens.css`, `src/styles/visual-refresh.css`
- App Shell Navigation: `src/app/App.tsx`, `src/app/App.test.tsx`
- ห้ามแก้ `src/features/performance/*.ts`, `src/features/performance/*.tsx`, Backend และ Database

## Phased Implementation

1. เก็บ Git/test baseline และตรวจ hash/diff ของ Performance source
2. เพิ่ม Tailwind/Shadcn foundation โดยไม่เปิด Preflight
3. เพิ่ม Token และ Visual Override สำหรับ App Shell/หน้าปัจจุบัน
4. ตรวจ TWD Function/Logic ด้วย tests และยืนยัน diff ของ Performance sourceเป็นศูนย์
5. รัน tests, lint, build และ visual QA แล้วสรุป Review โดยไม่แก้นอกขอบเขต

## Sidebar Collapse Extension

- คง Navigation เป็น Vertical Sidebar ด้านซ้ายทุก Breakpoint
- เพิ่ม Expanded/Collapsed state เฉพาะ App Shell; ค่าเริ่มต้นเป็น Expanded
- Collapsed state แสดง Icon Rail 72px, ซ่อน Label/Submenu เชิงภาพ แต่คง Accessible Name และ Navigation Target
- เมื่อย่อ Group Icon จะเปิดหน้าหลักของกลุ่มโดยตรง
- ไม่แก้ Component, State, Handler, API หรือ Data Logic ใต้ `src/features/performance`

## Verification

- Frontend tests และ build ผ่านเท่ากับหรือดีกว่า Baseline 37 tests
- Backend tests ผ่านเท่ากับ Baseline 53 tests โดยใช้ workspace basetemp เมื่อ Windows Temp มี permission error
- Ruff ผ่านสำหรับ `backend/app` และ `backend/tests`; Full Backend Ruff อาจยังพบไฟล์ Preview/Migration เดิมที่อยู่นอกขอบเขต
- หน้า Performance ยังมี Filter, KPI, Matrix, SUM, Pagination, Drawer, Import/Export และทุก Control เดิม
- `git diff -- src/features/performance` ไม่มีผลลัพธ์
- ตรวจ Loading, Empty, Error, Hover, Focus และ `prefers-reduced-motion`

## TWD Excel Error Remediation

1. แก้ Numeric Parser ให้ตรวจ `XL_CELL_ERROR` ก่อนแปลง Decimal และไม่นำ Error Code มารวมยอด
2. เพิ่ม Regression Test สำหรับ `#VALUE!` และ Real Sample Reconciliation
3. จัดทำ Dry-run Tool ที่จับคู่ Batch กับไฟล์ต้นทางด้วย SHA-256 และตรวจ Data Date/Source Total
4. แก้เฉพาะ Fact ที่พิสูจน์ได้ว่าเปลี่ยนจาก Error Code 15 เป็น 0 โดย Transaction เดียว
5. สำรอง PostgreSQL ก่อน Apply, สร้าง Audit Event ต่อ Batch และตรวจยอด Batch/Fact หลัง Apply
# TWD Sales Dashboard — Implementation Plan

1. เพิ่ม read-only endpoint `/api/dashboards/twd` ที่อ่าน Monthly Sales Summary และคืน Summary, Monthly, Top Branch และ Top SKU
2. เพิ่ม Backend regression tests สำหรับขอบเขต MT, ช่วงเวลา, YoY และอันดับ
3. เพิ่มหน้า Dashboard TWD แยก module พร้อม Loading/Empty/Error และ accessible chart/table
4. เพิ่มเมนู `แดชบอร์ด > ไทวัสดุ` ใน App Shell และลิงก์กลับรายงานเดิม
5. รัน Backend/Frontend tests, Ruff, ESLint, production build, ตรวจ responsive และยืนยัน `git diff -- src/features/performance` ว่าง

# Automatic FileShare Import — TWD Phase 1 Implementation Plan

## Summary และ Non-goals

- เพิ่ม File Registry, Run History, Schedule ต่อ MT, Run Now และ TWD Background Worker บน FileShare ที่ตั้งค่าไว้แล้ว
- ใช้ Import/Corrective business rules เดิมและเพิ่ม `.xlsx` adapter โดยให้ `.xls`/`.xlsx` คืน normalized TWD extract แบบเดียวกัน
- Non-goals: MT อื่น, `.zip`, การแทนที่อัตโนมัติ, การลบ Fact ตามไฟล์ต้นทาง และการแก้หน้า TWD Performance

## Data Model Draft

- `source_files`: MT, normalized path, filename, size, modified time, checksum, detected data date, discovery/status timestamps, status และ error category
- `import_runs`: MT, trigger (`scheduled|manual|catch_up`), status, started/finished by, counts found/imported/skipped/pending/failed และ summary
- Modern Trade เพิ่ม `schedule_enabled`, `schedule_time` และ scheduling metadata ที่จำเป็นต่อ catch-up
- Constraints: unique normalized source path ต่อ MT, checksum lookup ต่อ MT และ active-run guard ต่อ MT

## Backend และ Worker Plan

1. เพิ่ม `.xlsx` parser dispatch พร้อม parity/regression tests เทียบ normalized extract กับ `.xls`
2. เพิ่ม File Registry discovery แบบ recursive เฉพาะ `TWD\<date-folder>\<file>` และรองรับ `.xls`/`.xlsx`
3. เพิ่ม Initial Scan ที่ Hash/อ่าน Data Date เพื่อจับคู่ Batch เดิม แต่ไม่เขียน Fact ซ้ำ
4. เพิ่ม idempotent import decision service: unchanged skip, new import, same-period conflict pending review, warning pending review
5. เพิ่ม worker loop และ persisted schedule evaluation ใน `Asia/Bangkok` พร้อม per-MT lock และ same-day catch-up
6. ใช้ transaction ต่อไฟล์ เพื่อให้ไฟล์เสียไม่ Rollback ไฟล์อื่น และสร้าง Run/Audit result ทุกกรณี

## API Plan

- `GET/PATCH /api/admin/modern-trades/{code}/schedule` สำหรับเวลาและ Enabled
- `POST /api/admin/modern-trades/{code}/runs` สำหรับ Run Now พร้อม idempotent trigger
- `GET /api/admin/import-runs` และ `GET /api/admin/import-runs/{id}` สำหรับ Monitoring/รายละเอียดไฟล์
- Conflict ใช้ Corrective Preview/Replace เดิม โดยเพิ่มการเชื่อมจาก Source File/Run ไปยัง Batch ที่ชนกัน
- ทุก mutation ใช้ System Admin dependency; response และ audit ห้ามมี Password

## UI Plan

- ใน `การตั้งค่า > การตั้งค่าระบบ > FileShare` เพิ่มคอลัมน์ `Schedule`, `เวลา`, `Run ล่าสุด`, `Run ถัดไป`, `สถานะ` และ `Run ทันที` ต่อ MT
- ปุ่ม Run Now เปิด Confirmation Modal แสดง MT, Full Path และข้อความว่า Import เฉพาะไฟล์ใหม่
- ระหว่าง Run ปิด Trigger ซ้ำเฉพาะ MT นั้น พร้อมแสดง progress/status โดยไม่บล็อก MT อื่น
- Monitoring เพิ่ม Run Summary และ Pending Review พร้อมทางไป Preview/Keep Existing/Replace
- คงปุ่ม Save ระบบปุ่มเดียว และบันทึกเฉพาะ Settings section ที่เปลี่ยน

## Phases

1. Schema, migrations, `.xlsx` parser parity และ unit tests
2. File discovery/registry และ Initial Scan dry-run tests กับ Batch เดิม
3. Import decision service, run history, per-MT lock และ corrective integration
4. Schedule worker, catch-up, Run Now APIs, Audit และ Telegram summary
5. Settings/Monitoring UI states และ confirmation workflow
6. Backup, migration rehearsal, local NAS verification, Ubuntu DNS/SMB verification และ staged enablement เริ่มจาก TWD

## Verification และ Release Gate

- Initial Scan บนข้อมูลปัจจุบันต้องไม่เพิ่ม `import_batches` หรือ Fact สำหรับไฟล์เดิม
- Run ซ้ำด้วย source state เดิมให้ Imported = 0 และไม่มี duplicate rows
- Same-period/different-checksum และ reconciliation warning ต้อง Pending Review โดย Fact เดิมไม่เปลี่ยน
- Concurrent triggers ของ TWD ต้องมีงาน active เพียงหนึ่งงาน; MT อื่นไม่ถูกบล็อก
- Server restart ภายในวันเดียวกันสร้าง catch-up ไม่เกินหนึ่งครั้ง
- File ต้นทางหายไม่ลบ Batch/Fact และมี Monitoring event
- Frontend/backend tests, lint/build ผ่าน และ `git diff -- src/features/performance` ว่าง
