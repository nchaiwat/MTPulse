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


# TWD Import Progress และ Direct FileShare Import — Implementation Plan

## Project Summary

ปรับหน้า `นำเข้าข้อมูล` ให้บอกความคืบหน้าของ Manual Upload ตาม Byte จริง และเพิ่มเส้นทางเลือกไฟล์ TWD สถานะ `ready` จาก File Registry เพื่อให้ Server อ่าน NAS โดยตรง ทั้งสองเส้นทางใช้ Preview/Confirm และกฎ Import ชุดเดียวกัน โดยไม่แก้หน้า TWD Performance

## Goals และ Non-goals

### Goals

- Manual Upload แสดง Upload Percentage, Processing Phase และ Timing Breakdown
- FileShare Ready List อ่านจาก PostgreSQL โดยไม่ Rescan NAS
- FileShare Preview/Confirm อ่าน NAS แบบ Read-only และตรวจ Checksum ซ้ำก่อน Import
- ใช้ Summary, Warning, Duplicate Protection, SKU Interest, Notification และ Audit behavior เดิม
- UI เป็น Operations Ledger แบบ Modern/Clean/Premium และเข้าถึงได้ด้วย Keyboard

### Non-goals

- ไม่ปรับ SMB protocol, Wi-Fi/LAN, NAS หรือ Nginx infrastructure ในรอบนี้
- ไม่สร้าง Streaming Parser, SSE, WebSocket หรือ Background Job ใหม่สำหรับ Manual Preview
- ไม่เปลี่ยน Schedule, Run Now, Initial Scan หรือ Corrective rules
- ไม่รองรับ MT อื่นหรือ `.zip`
- ไม่แก้ไฟล์ใต้ `src/features/performance`

## Technical Architecture

- ใช้ `XMLHttpRequest.upload.onprogress` เฉพาะ Manual Upload เพราะ Fetch API ปัจจุบันไม่เปิด Upload Progress
- หลัง Browser ส่งครบ UI เปลี่ยนจาก `uploading` เป็น `processing`; Backend ใช้ `perf_counter` วัด read/download, parse และ duplicate check แล้วคืน Timing metadata
- ใช้ `source_files` เดิมเป็น Registry; ไม่มี Migration ใหม่
- Direct FileShare endpoint โหลด Credential ฝั่ง Backend, ใช้ `download_twd_extract` เดิม และไม่คืน Secret/Full Path
- Preview และ Confirm รับ `source_file_id` พร้อม `expected_checksum`; Confirm อ่าน Source ใหม่เพื่อป้องกันไฟล์เปลี่ยนหลัง Preview
- แยก helper เฉพาะส่วน Import completion ที่จำเป็นให้ Manual/FileShare ใช้ผลลัพธ์และ Notification แบบเดียวกัน โดยไม่เปลี่ยน Parser หรือ `import_twd_extract`

## API Plan

- `GET /api/imports/fileshare-ready?limit=1000`
  - คืน TWD Source File เฉพาะ `status=ready`
  - เรียง `detected_data_date DESC, id DESC`
  - Response: id, filename, dataDate, sizeBytes, discoveredAt; ไม่คืน sourcePath
- `POST /api/imports/fileshare/{source_file_id}/preview`
  - ตรวจ Source ownership/status, Download/Parse และคืน Import Preview เดิมพร้อม source mode/timings
- `POST /api/imports/fileshare/{source_file_id}/confirm`
  - รับ expected checksum, Download/Parse ซ้ำ, ตรวจ checksum และ Import transaction เดิม
  - อัปเดต Source File เป็น imported เฉพาะหลัง Import สำเร็จ
- `POST /api/imports/preview` และ `POST /api/imports/confirm`
  - Contract เดิมยังใช้ได้ เพิ่ม optional `timings` โดยไม่ทำให้ Client เดิมเสีย
- Error ต้องบอกทางแก้: ไฟล์หาย/เปลี่ยนให้ Run Scan ใหม่, Duplicate ให้ดู Batch เดิม, FileShare ใช้ไม่ได้ให้ตรวจ Settings/Network

## Frontend/UI Plan

- เพิ่ม Segmented Source Switch ด้านบน Workflow: `จากเครื่อง` / `จาก FileShare`
- Manual mode คง File Input เดิมและเพิ่ม Compact Pipeline Strip:
  - Uploading: Progressbar พร้อม Percentage และขนาดที่ส่ง
  - Processing: `กำลังอ่าน Excel และตรวจข้อมูล`
  - Ready/Error: Timing Breakdown และคำแนะนำ
- FileShare mode แสดง Ready List แบบตารางกะทัดรัด มีวันที่ข้อมูล, ชื่อไฟล์, ขนาด, เวลาที่พบ และปุ่ม Preview
- เมื่อ Preview สำเร็จ ใช้ Preview Summary/Footer เดิม; ปุ่ม Confirm เลือก API ตาม Source Mode
- Empty state บอกให้ใช้ Initial Scan/Run Now; Error state มี Retry
- สี Primary `#02ABFF`, Navy/Slate, Soft Shadow และ Radius ตาม Design System; Motion 150–200ms และเคารพ reduced motion

## File และ Module Plan

- `backend/app/api/imports.py`: timing helpers, FileShare list/preview/confirm endpoints และ shared completion path
- `backend/app/services/automatic_import.py`: reuse download/credential behaviorเท่าที่จำเป็น โดยไม่เปลี่ยน decision logic
- `backend/tests/test_manual_import.py` และ endpoint tests: filtering, preview read-only, checksum change, success/source update และ errors
- `src/features/imports/importApi.ts`: upload-progress transport, FileShare list/preview/confirm contracts
- `src/features/imports/ImportPage.tsx`: source mode, progress phases, ready list และ shared preview
- `src/features/imports/ImportPage.test.tsx`: progress, source switch, ready/empty/error, preview และ confirm
- `src/styles/app.css`: scoped Import workflow stylesเท่านั้น
- Documentation: `PRD.md`, `implementation_plan.md`

## Phased Implementation

1. เพิ่ม Backend tests สำหรับ Ready List และ FileShare Preview/Confirm
2. เพิ่ม Backend endpoints/timings โดย reuse Import rules เดิม
3. เพิ่ม XHR upload progress client พร้อม unit tests
4. เพิ่ม Source Switch, Pipeline Strip และ Ready List โดย reuse Preview UI เดิม
5. รัน frontend/backend regression, Ruff, ESLint, build และตรวจ diff ของ Performance
6. ทดสอบ Local ด้วยไฟล์ 5–6 MB และทดสอบ WA-MTPULSE-TEST หลัง Backup/Deploy approval

## Verification Plan

- Backend: Preview ไม่เพิ่ม ImportBatch/Fact; Confirm เพิ่มครั้งเดียว; duplicate/changed/missing/status-not-ready ถูกปฏิเสธ
- Security: response ทุก endpoint ไม่มี Base UNC, Domain, Username หรือ Password
- Frontend: Progressbar มี accessible name/value, keyboard source switch, loading/empty/error/retry และ reduced motion
- Regression: Manual Upload auto-preview, Corrective, Activity Log, Automatic Run และ Telegram ยังทำงาน
- Quality gates: full pytest, Ruff, frontend tests, ESLint, production build และ `git diff -- src/features/performance` ต้องว่าง
- Server validation: เปรียบเทียบเวลาจริงของ Local upload กับ Direct FileShare และตรวจ Source File/Batch/Audit หลัง Confirm

## Risks และ Mitigations

- NAS ยังช้าจาก Wi-Fi: UI แสดงช่วง `กำลังอ่านจาก FileShare` และเวลาจริง; Direct path ตัด Browser hop แต่ไม่ทำให้ NAS เร็วขึ้น
- Source เปลี่ยนหลัง Preview: Confirm re-download และ checksum guard
- Shared flow ทำให้ Manual behavior ถดถอย: รักษา endpoint contract เดิมและเพิ่ม regression tests ก่อนแก้
- FileShare list ใหญ่: จำกัด 1,000 รายการล่าสุดและใช้ Registry query/index เดิม โดยยังไม่อ่านเนื้อหา NAS จนกดตรวจสอบ

## Release Checklist

- ไม่มี Migration และไม่มีการแก้ TWD fact schema
- Backup PostgreSQL ก่อน deploy ตามขั้นตอน Test Server เดิม
- Deploy API/Web เท่านั้นหลังไม่มี Automatic Run active
- Smoke test Manual Upload progress, Ready List, FileShare Preview และ Error state
- ไม่ Trigger Confirm กับข้อมูลจริงโดยอัตโนมัติ; ให้ผู้ใช้เป็นผู้ยืนยัน Import


# TWD View Date Performance — Implementation Plan

## Baseline และ Root Cause

- `/api/performance?grain=day_total&page=1` ใช้ 8.09–8.71 วินาทีและคืน JSON 5.58 MB
- PostgreSQL aggregate จาก 4.51 ล้าน facts ซ้ำทุก request; query หลักใช้ 1.90–2.55 วินาที และหลาย summary/distinct queries รวมเวลาเพิ่มเติม
- `work_mem` 4 → 64/256 MB ลด spill ได้แต่ไม่แก้ full scan; 256 MB ยังใช้ 2.12 วินาทีเฉพาะ query หลัก
- Gzip ลด payload เหลือ 0.62 MB แต่ TTFB ไม่เปลี่ยน จึงไม่ใช่ root-cause fix
- Temporary Daily SKU Summary ลด main query เหลือ 62.8 ms และ daily total เหลือ 20.4 ms

## Implementation

1. เพิ่ม model/migration `daily_sku_summaries` คีย์ `modern_trade_id + data_date + source_sku`
2. Backfill Amount, Qty, Stock On Hand และ Stock On Order จาก `sales_inventory_facts`
3. เพิ่ม `refresh_daily_sku_summary()` และเรียกหลัง Import/Corrective Replace ก่อน commit
4. เพิ่ม safe fast path ใน Performance API เฉพาะ unfiltered `grain=day_total`
5. Daily Summary รวมเฉพาะ Active Branch Mapping; rebuild เมื่อ Branch Mapping เปลี่ยน และ fallback ไป Fact path เมื่อเปิดแสดงสาขาที่ยังไม่ Mapping
6. เพิ่ม Gzip สำหรับ JSON ใน Nginx พร้อมคง API contract เดิม

## Verification

- Unit test refresh/delete-reinsert ของวันที่เดียวโดยไม่กระทบวันอื่น/MT อื่น
- Equivalence test รัน fast path และบังคับ fallback จากข้อมูลเดียวกัน แล้วเทียบ response ทุก field
- Test ว่า Date/Branch/SKU/Search/Mapping filter ไม่เข้า fast path
- Test Import และ Replace refresh Daily/Monthly summary ใน transaction เดิม
- Migration upgrade/backfill/downgrade rehearsal บนฐานข้อมูลจำลอง
- Full pytest, Ruff, frontend tests, ESLint และ build
- ก่อน deploy backup PostgreSQL, ยืนยันไม่มี active import run และ benchmark endpoint 5 รอบหลัง migration

## Expected Result และ Rollback

- เป้าหมาย API unfiltered View Date ไม่เกิน 2 วินาทีบน WA-MTPULSE-TEST
- หาก response ไม่เท่ากันหรือ latency ไม่ถึงเป้า ให้ Performance API fallback Fact query ได้ทันทีโดย Fact data ไม่เปลี่ยน
- Rollback schema ลบเฉพาะ `daily_sku_summaries`; ไม่มีการเปลี่ยนหรือลบ Fact/Batch/Mapping

# Event-scoped Import Notification และ Daily Technical Health — Implementation Plan

## Summary และ Non-goals

- แยก `scan totals` สำหรับ Monitoring/Audit ออกจาก `event totals` สำหรับ Telegram โดยไม่เปลี่ยน Import decision หรือข้อมูลเดิม
- เพิ่ม persisted Daily Health schedule, adjustable thresholds, alert state/cooldown/recovery และ daily technical snapshot
- Non-goals: External Watchdog, Remote auto-remediation, Docker socket access, Auto VACUUM/REINDEX, การเพิ่ม RAM/Disk อัตโนมัติ และ Visual redesign เต็มระบบใน Phase นี้

## Technical Architecture

- เพิ่ม Event classification ให้ outcome ของ Automatic Import ระบุว่าไฟล์ `unchanged` หรือถูกประมวลผล/เปลี่ยนใน Run นี้อย่างชัดเจน
- `_finish_run` คง Run counters เดิมสำหรับ UI/Audit แต่สร้าง Telegram summary จาก event outcomes เท่านั้น
- เพิ่ม Health evaluator ที่เก็บ Host/Runtime, PostgreSQL และ Pipeline metrics โดย reuse `collect_monitoring_metrics` และไม่สร้าง query ซ้ำโดยไม่จำเป็น
- Worker เดิมเป็น scheduler หลัก: ตรวจ Due Daily Report และ Technical thresholds ทุก 5 นาที พร้อม persisted last-sent/alert-state เพื่อทน Restart และป้องกันส่งซ้ำ
- Host metrics อ่านจาก Linux `/proc` และ filesystem usage เท่าที่ Container มองเห็น โดยไม่ mount Docker socket; Metric ที่อ่านไม่ได้แสดง `ไม่พร้อมใช้งาน` ไม่ตีความเป็น Healthy
- Telegram delivery failure ไม่ทำให้ Import หรือ Monitoring transaction rollback; ทุกการส่งสร้าง Audit Event พร้อมสถานะ sent/skipped/failed

## Data Model และ Settings

- `system_settings`: daily enabled/time, critical enabled, recovery enabled, cooldown และ threshold pairs โดยใช้ service validation กลาง
- เพิ่ม Technical snapshot/alert state ที่จำเป็นสำหรับ daily deduplication, trend, cooldown และ recovery; Migration ต้องมี upgrade/downgrade และไม่แตะ Fact/Batch
- เก็บ `last_worker_heartbeat` เพื่อแสดงความสดของ Worker; ไม่อ้างว่าสามารถแจ้งเองเมื่อ Worker/Server ดับ
- ค่าเริ่มต้น: 07:00, evaluation 5 นาที, cooldown 60 นาที, CPU 80/95, RAM 80/90, Disk 80/90, Connections 80/95 และ Dead tuples 10/20

## API Plan

- ขยาย System Settings GET/PATCH ด้วย `technicalNotifications` โดยคง Telegram contract เดิมและรองรับ client เก่า
- ขยาย Monitoring response ด้วย Host/Runtime, worker heartbeat, capacity recommendation และ technical alert state
- ใช้ endpoint Save ระบบเดิมหรือ orchestration เดิมเพื่อให้หน้า UI มีปุ่ม Save เดียวและบันทึกเฉพาะ section ที่เปลี่ยน
- ทุก mutation อยู่หลัง System Admin authorization boundary และสร้าง Audit Event

## UI Plan — Phase นี้

- คง Main Menu และ TWD pages เดิม; ปรับเฉพาะ System Settings ที่จำเป็นต่อ Feature ใหม่
- จัด Telegram panel เป็นสองกลุ่มอ่านง่าย: `ช่องทางส่งข้อความ` และ `นโยบายแจ้งเตือน`
- เพิ่ม `Technical Health` แบบ Operations Ledger: Daily time/toggles ด้านบน และ Threshold table ด้านล่าง โดยแต่ละแถวแสดง Metric, Warning, Critical, หน่วย และคำอธิบาย
- ใช้ Primary `#02abff`, Soft semantic colors, Lucide icons, radius/shadow ตาม Design System เดิม; ไม่ทำเป็น Card Grid ฟุ่มเฟือย
- คง Single Save Bar พร้อม dirty state, loading, inline validation, success/error และ keyboard/focus accessibility

## Antigravity Visual-only Phase — หลัง Functional Release

- เปิดโปรเจกต์ใน isolated worktree/branch และส่ง `PRD.md`, `MEMORY.md`, `design-system/mt-pulse/MASTER.md` พร้อมภาพหน้าปัจจุบันเป็น context
- Workspace Rules ต้องห้ามแก้ `backend/**`, migrations, API clients/contracts, tests เชิง behavior, state, handlers และ `src/features/performance/**`
- ให้ Antigravity ส่ง Design Plan/Mockup/Browser screenshots ก่อนเขียนโค้ด และใช้ file allowlist สำหรับ App Shell, Settings presentation และ CSS/tokens เท่านั้น
- ก่อน merge ตรวจ diff, interaction parity, tests, responsive 375/768/1024/1440, keyboard/focus และ visual regression; หาก protected file เปลี่ยนให้ reject ทั้ง change set

## Phased Implementation

1. เพิ่ม deterministic tests ที่ reproduce การแจ้ง Warning/Failed เก่าซ้ำ และล็อก expected event-only message
2. เพิ่ม Event classification/message formatter โดยคง Run History counters เดิม
3. เพิ่ม settings validation, migration และ persisted alert state/snapshot
4. เพิ่ม Host/DB/Pipeline collector, daily formatter, 5-minute evaluator, cooldown และ recovery
5. เพิ่ม System Settings/Monitoring UI เฉพาะส่วน Technical Health และ single-save orchestration
6. รัน regression/lint/build, migration rehearsal, local time simulations และ Telegram mocks
7. Backup/Deploy WA-MTPULSE-TEST, smoke test Daily trigger แบบเวลาจำลอง และตรวจ Audit โดยไม่ส่งข้อความทดสอบซ้ำเกินจำเป็น

## Verification และ Rollback

- Test unchanged registry หลายร้อยไฟล์พร้อม historical failed/pending แล้ว Telegram ต้องรายงานว่าไม่มี Event ใหม่
- Test new/changed/missing/failed อย่างละกรณี รวม mixed run และยืนยันว่า Monitoring totals ไม่เปลี่ยน
- Test 06:59/07:00/restart/catch-up/time change และ timezone Asia/Bangkok; Daily ส่งได้หนึ่งครั้งต่อ local date
- Test threshold boundary, Warning→Critical, cooldown, Critical→Healthy recovery และ delivery failure
- Test inaccessible CPU/RAM/Disk metric เป็น Unknown พร้อมคำอธิบาย ไม่เป็น Healthy ปลอม
- Rollback ปิด Technical scheduler/alerts ผ่าน setting ได้ก่อน downgrade; Migration rollback ลบเฉพาะโครงสร้างใหม่และไม่แตะ Import/Fact/Mapping

# Manual Health Check และ Single-SKU Historical Backfill — Implementation Plan

## Summary และ Non-goals

- เพิ่ม Manual Technical Health delivery ที่ใช้ collector/formatter เดิม แต่ไม่แตะ state ของ Daily/Critical/Recovery
- เพิ่ม TWD Backfill ครั้งละหนึ่ง SKU โดย reuse File Registry, Import Batch, parser, queue และ active-run protection เดิม
- เติมเฉพาะ Data Date ที่ยังไม่มี Fact ของ SKU และมี Normal Import Batch อยู่แล้ว; ไม่ replace, merge บาง Branch หรือลบข้อมูลเดิม
- Non-goals: Multi-SKU backfill, Partial Batch creation,แก้ไฟล์ NAS, Backfill MT อื่น, Auto-resolve file conflicts, เปลี่ยน TWD Performance behavior และ Antigravity code changes ใน Phase นี้
- Product Owner ไม่อนุมัติให้เปลี่ยน Telegram Bot/Token, Rotate Token หรือแก้ HTTP client logging ใน Phase นี้

## Manual Technical Health Architecture

- เพิ่ม service function สำหรับ fresh collection + Telegram delivery + Audit โดย reuse `collect_monitoring_metrics`, `evaluate_technical_metrics` และ health formatter
- เพิ่ม `POST /api/settings/system/technical-notifications/check` ส่งผล `{status, message, checkedAt, overallStatus, metrics}` โดยไม่คืน Secret
- Function นี้ห้ามเขียน `technical_last_daily_sent_date`, `technical_last_daily_attempt_at`, `technical_alert_state` หรือ timestamp ที่ใช้ Critical cooldown
- Frontend เพิ่มปุ่ม `ตรวจสอบและส่งทันที` ใน Technical Health header มี loading lock, success/error และ last checked summary
- Test แยกยืนยันว่ากด Manual ก่อน/หลัง 07:00 แล้ว Daily ยังส่งตามปกติ และ Critical cooldown/state ไม่เปลี่ยน

## Backfill Data Model Direction

- Reuse `import_runs` เพื่อให้ partial unique index `uq_import_run_active_mt` ป้องกัน Automatic Import และ Backfill ทำงานซ้อนกันโดยไม่สร้างระบบ Lock ชุดใหม่
- Migration เพิ่ม nullable fields ที่จำเป็น เช่น `target_sku`, `range_start`, `range_end`, `stop_requested_at` และใช้ `mode=sku_backfill`
- `results_json` เก็บ per-date outcome และ checkpoint หลังจบแต่ละไฟล์; counters เดิม map เป็น discovered/inserted/skipped/attention/failed ผ่าน API adapter สำหรับ UI
- Resume ใช้ Run เดิมกลับเข้า `queued` หลังตรวจว่าไม่มี Active Run และใช้ Fact existence + per-date outcome เป็น idempotency guard
- ทุก confirm, stop request, resume, per-date failure และ completion สร้าง Audit Event ที่ไม่บันทึก Credential หรือ UNC เต็มในข้อความ User-facing

## Source Selection และ Preview

- Query `source_files` ด้วย MT + `detected_data_date` ในช่วงที่เลือก และแสดง Registry `max(last_seen_at)` เป็น freshness
- ต่อ Data Date เลือก SourceFile ที่ผูก `imported_batch_id` ตรงกับ Import Batch ของวันนั้นเป็นตัวเลือกหลัก
- หากไม่มี Batch, ไม่มี SourceFile, status อ่านไม่ได้/หาย หรือมี candidate ขัดแย้งที่ตัดสินไม่ได้ ให้ Preview เป็น attention และไม่เตรียม Insert
- Preview ตรวจ `sales_inventory_facts` grouped by Data Date สำหรับ target SKU; ถ้าวันใดมี Fact อย่างน้อยหนึ่ง Branch ให้ข้ามทั้งวันเป็น `already_present`
- Preview endpoint เป็น read-only และไม่สร้าง Run: `POST /api/admin/modern-trades/TWD/sku-backfills/preview`
- Request ระบุ SKU และ start mode/date; Server คำนวณ end date จาก latest registered/imported data และคืน counts กับ per-date reason

## Confirm, Worker และ Stop/Resume

- Confirm endpoint ตรวจ Preview token/version หรือ revalidate source metadata ก่อนสร้าง queued `ImportRun`; ห้ามเชื่อผลจาก Browser โดยตรง
- Worker `claim_next_run` เดิมรับ queued row แล้ว dispatch ตาม `mode`; `sku_backfill` ใช้ service แยก ไม่เปลี่ยน normal `process_run` decision path
- ต่อหนึ่ง Data Date: download temporary copy ด้วย credential service เดิม, parse ด้วย TWD parser เดิม, เลือกเฉพาะ target SKU, recheck Fact existence, insert rows ผูก Batch เดิม, refresh summaries และ commit checkpoint transaction เดียวกัน
- หาก target SKU ไม่พบในไฟล์ ให้ outcome `sku_not_found`; หาก file/download/parser fail ให้เก็บเหตุผลและทำวันถัดไป
- Stop endpoint ตั้ง `stop_requested_at`; Worker ตรวจหลัง transaction ของไฟล์ปัจจุบันแล้วเปลี่ยนสถานะ `stopped`
- Resume endpoint revalidate mapping/source/active-run แล้วเปลี่ยน `stopped` เป็น `queued`; วันที่สำเร็จหรือมี Fact แล้วถูกข้ามอัตโนมัติ
- Completion ใช้ Event ของ Backfill Run นั้นสร้าง Telegram หนึ่งข้อความและเก็บรายละเอียดเต็มใน Run/Monitoring

## Mapping Integration

- หลัง Import Mapping ให้ sync เฉพาะ SKU candidates ที่ `status=confirmed` และ `report_status=active` ไป `sku_interests.status=active`
- หาก SKU เดิม Pending/Ignored ให้สร้าง Audit before/after; Mapping ที่ inactive ห้าม activate interest
- Preview ตรวจ active confirmed mapping ณ requested start date
- หาก Mapping ใหม่มี `effective_from` หลังวันเริ่ม Backfillและเป็น mapping เดียวกันโดยไม่มีประวัติชนกัน ให้ส่ง proposed effective-date adjustment ใน Preview และแก้เมื่อ Confirm พร้อม Audit
- หากมี Mapping history คนละ WA Item หรือช่วง effective date ซ้อน ให้ Block Backfill และส่งให้ User ตรวจ Mapping เอง ห้ามแก้อัตโนมัติ

## Summary Refresh และ Data Integrity

- ห้ามแก้ Batch source totals/checksum/status เพราะ Batch ยังคงอธิบายไฟล์ต้นทางทั้งวัน
- เพิ่ม targeted summary refresh สำหรับ MT + SKU + Date/Month หรือพิสูจน์ด้วย test ว่า helper เดิมให้ผลเท่ากันโดยไม่เปลี่ยน SKU อื่น
- Unique constraint `(batch_id, source_branch_code, source_sku)` เป็น safety net เพิ่มเติม แต่ service ต้องตรวจล่วงหน้าและไม่ใช้ exception เป็น flow ปกติ
- ทุกวันที่ทำสำเร็จต้องเปรียบเทียบจำนวน Branch และผลรวม Amount/Qty/Stock ของ target SKU กับ extract subset ก่อน commit

## Frontend UI Plan

- `SystemSettingsPage`: ปุ่ม Secondary `ตรวจสอบและส่งทันที` ใน header Technical Health พร้อม inline result; ไม่เพิ่ม Card หรือหน้าใหม่
- `TwdSettingsPage`: section `ดึงข้อมูลย้อนหลังเฉพาะ SKU` ต่อจาก Item Mapping ใช้ searchable SKU selector เฉพาะ confirmed/active, ตัวเลือก `ไฟล์แรกที่พบ`/`เลือกวันที่`, date input และ Registry freshness
- Preview เป็น Operations Ledger แสดง Ready, Already present, No batch, Missing/Unreadable/Conflict และ proposed Mapping effective date ก่อนเปิด Confirm dialog
- Active Run แสดง Progress, current Data Date, counts, elapsed time, `หยุดหลังจบไฟล์ปัจจุบัน`; Stopped state แสดง Resume
- `MonitoringPage`: เพิ่ม Run table/filter สำหรับ SKU Backfill และ attention dates แบบ compact โดยไม่แก้ TWD Performance layout
- รองรับ Loading, Empty, Error, Validation, Disabled, Stop requested และ partial completion; ใช้ `#02abff`, soft semantic colors, existing spacing/radius/type scale

## API และ Module Plan

- `backend/app/api/system_settings.py`: Manual health check endpoint
- `backend/app/services/technical_health.py`: side-effect-free manual delivery path
- `backend/app/api/sku_backfills.py`: Preview/Confirm/Status/Stop/Resume endpoints
- `backend/app/services/sku_backfill.py`: candidate resolution, validation, per-date processing, checkpoints และ Telegram summary
- `backend/app/worker.py`: mode dispatch โดยคง scheduled import path เดิม
- `backend/app/services/item_mapping_exchange.py`: confirmed+active interest synchronization
- `backend/app/models.py` + Alembic migration: ImportRun backfill metadata
- `src/features/settings/*`: Manual Check และ Backfill workspace/API/types
- `src/features/monitoring/*`: Backfill run visibility

## Test Plan

- Manual Health: fresh values, Telegram success/failure, Audit, disabled/unconfigured Telegram และ invariant ของ Daily/Critical state
- Preview: earliest/custom start, latest end, stale Registry, already-present whole date, no Batch, missing/failed/conflict file และ mapping date proposal/block
- Processing: one SKU only, correct Batch linkage, no mutation of existing facts/batch metadata, target totals, per-date commit, failure continues, retry idempotency
- Concurrency: queued/running Automatic Import blocks Backfill และ Backfill blocks scheduled/manual Import
- Stop/Resume: stop after current file, completed dates retained, resume remaining only, worker restart recovery
- Mapping: confirmed+active auto-accepts Pending/Ignored; inactive/pending mapping does not; conflicting history blocks
- Regression: existing TWD import, automatic notification, manual import, mapping exchange, summaries, Performance API/UI, backend full suite, Ruff, frontend full suite, ESLint และ production build

## Deployment และ Rollback

1. ตรวจ dirty files และ stage เฉพาะ scope; ห้ามรวม business files/temp/Secrets
2. Backup PostgreSQL และ verify ด้วย `pg_restore --list`
3. Deploy migration/code ไป WA-MTPULSE-TEST โดยยังไม่กด Backfill แทน User
4. Smoke Manual Health Check ด้วย User authorization เพราะจะส่ง Telegram จริง
5. สร้าง Preview ด้วย test SKU/date ที่ไม่ mutation แล้วให้ User ตรวจ
6. ทดลอง Backfill SKU ที่ User เลือกหนึ่งรายการและ reconcile ก่อน/หลังระดับ SKU × Date × Branch
7. Rollback application ก่อน schema; nullable fields ทำให้ code เดิมอ่านต่อได้ แล้ว downgrade migration เมื่อไม่มี active run

## Antigravity Visual-only Phase 2

- สร้าง isolated worktree/branch จาก Functional release ที่ tests ผ่าน และไม่ส่ง `.env`, database dump, NAS credential หรือ business files ให้ agent
- เพิ่ม Always On Workspace Rule ใน `.agents/rules` พร้อม protected paths และ frontend allowlist
- ตั้ง Antigravity เป็น Review-driven development ให้สร้าง Implementation Plan/Task List/Mockup ก่อน Code ตาม workflow ที่เอกสารทางการรองรับ
- ให้ Browser artifact จับภาพ desktop/tablet/mobile, hover/focus/loading/empty/error และ walkthrough ของ workflow สำคัญ
- กลับมาตรวจ diff กับ allowlist, reject protected changes, รัน regression และให้ Product Owner อนุมัติ screenshots ก่อน merge/deploy

## Open Decision Before Implementation

- ไม่มี Business Rule ค้างสำหรับ Phase 1; รอ Product Owner อนุมัติ PRD/Implementation Plan ก่อนเริ่ม Code

# Shared HP/MH FileShare Import และ Dashboard — Implementation Plan

## Architecture และ Migration

- เพิ่ม Shared Source Group สำหรับ `HP_MH` และผูกสมาชิก HP/MH โดยเก็บ configuration/schedule เพียงชุดเดียว; seed ModernTrade `HP`/`MH` แบบ idempotent
- เพิ่ม Shared Import Run/Pair registry เพื่อให้ source file หนึ่งชุดถูก discover/download/parse ครั้งเดียว และเก็บ per-MT outcome ภายใน run เดียว
- เพิ่ม source kind, pair timestamp, business fingerprint, selected/superseded state และ coverage metadata ที่จำเป็นผ่าน Alembic migration โดยไม่แก้ uniqueness/behavior เดิมของ TWD
- ใช้ transaction boundary ต่อ Data Date ครอบคลุม HP/MH batches, facts, interest discovery และ summaries; corrected-day replacement ลบ/สร้างเฉพาะสอง MT และวันเป้าหมายใน transaction เดียว

## Parser และ Import Pipeline

- เพิ่ม `hp_mh` importer สำหรับ ZIP/CSV: validate metadata/header, normalize Excel-style quoted values, parse internal date และ classify Inventory/Sales
- Pair candidates ตาม Data Date + kind; เลือก generation timestamp ล่าสุด, mark older candidates superseded และ validate internal dates match
- Split branch prefix S/M, aggregate Sales และ sparse Inventory เป็น grain MT × Date × Branch × SKU; merge metrics ก่อน reconcile
- คำนวณ Sales Ex.VAT ด้วย VAT policy เดิม, เก็บ gross/source amount, Return และ Stock Value source โดยไม่สร้าง Stock On Order ปลอม
- Discover SKU candidate เฉพาะ Sale Out และ apply interest/mapping แยก MT; store coverage ของ Inventory แยกจาก sparse facts
- เพิ่ม initial, incremental 7-day + failed retry และ date-range rescan paths พร้อม business fingerprint/idempotency/reimport audit

## API, Worker และ Notification

- Generalize automatic-import dispatch จาก TWD-only เป็น strategy ตาม source group โดยรักษา TWD path เดิม
- เพิ่ม Shared HP/MH run endpoints/status payload และ per-stage progress; scheduler enqueue เพียงหนึ่ง run ต่อ shared schedule
- Settings API อ่าน/บันทึก Shared profile หนึ่งจุดและคืน child status/counters ของ HP/MH; connection test ทดสอบ shared pathครั้งเดียว
- Telegram formatter ส่งหนึ่ง event-scoped message มี HP/MH sections และไม่รวม registry event เก่า

## Frontend

- เพิ่ม shared source group card ใน System Settings พร้อม visual grouping, shared controls และ HP/MH child cards
- เพิ่ม HP/MH routes/menu โดย parameterize/reuse TWD Dashboard components และ API contract; ซ่อน Stock On Order และใช้ label Stock Value (Source) สำหรับ HP/MH
- เพิ่มเมนูและ route `รายงาน > HomePro (HP)` และ `รายงาน > MegaHome (MH)` โดย parameterize หน้า Performance เดิมแทนการคัดลอก component ทั้งหน้า
- สร้าง Metric capability จาก API ต่อ MT: TWD ใช้ความสามารถเดิม; HP/MH Sales แสดง Amount Ex.VAT/Qty และ Inventory แสดง Stock On Hand/Stock Value (Source) โดยไม่แสดง Stock On Order ที่ไม่มี Source
- แยก source-field adapter (`Sales.QTY`, `Sales.VALUE`, `Inventory.QTY`, `Inventory.AMT`) ออกจาก report contract เพื่อรองรับ field ใหม่ภายหลังโดยไม่เปลี่ยน URL/UI contract หรือ Fact metric เดิม
- เพิ่ม loading/error/empty/progress/superseded/reimport states และ record counts แยก MT โดยไม่เปลี่ยน TWD presentation/behavior

## Tests และ Rollout

- Parser tests จาก fixture ย่อส่วนที่สะท้อน ZIP จริง: metadata/date, S/M split, negative rows, totals, zero sparse, malformed/missing/mismatched pair
- Service tests: atomic rollback, per-day continuation, latest pair selection, rename duplicate, corrected replacement, interest isolation, mapping pending และ incremental window
- API/UI tests: shared schedule/run, child counters, HP/MH routes/metrics, Telegram sections และ TWD regression
- Run Alembic upgrade/downgrade rehearsal, backend full suite + Ruff, frontend tests + ESLint + production build
- Deploy ไป WA-MTPULSE-TEST หลัง commit/push และ backup DB; smoke connection/preview ก่อน Initial Scan จริง และ Rollback application/migration หาก reconciliation ไม่ผ่าน

## Implementation Order

1. Migration/models + parser fixtures/tests
2. Pairing, fingerprint, atomic import และ summaries
3. Worker/API/scheduler/Telegram
4. Settings UI + HP/MH report pages
5. HP/MH dashboards
6. Full regression, migration rehearsal, commit/push/deploy และ server smoke test
# Settings Control Plane Standard — Implementation Plan

## Goals และ Non-goals

- สร้างหน้า Settings หน้าเดียวที่มี Scope tabs `Global / TWD / HP / MH / GH / SCG / HH / TA`
- ย้ายการจัดวาง UI ให้ตรงตาม ownership ของค่า โดยคง API และ business behavior เดิมเท่าที่ทำได้
- สร้าง reusable Settings template สำหรับ Section, status, disabled capability และ save feedback
- ไม่แก้หน้าอื่น, ไม่เพิ่ม Window Asia และไม่เปิด capability ที่ backend ยังไม่รองรับ

## Visual Direction

- คง `Operations Ledger` จาก `design-system/mt-pulse/MASTER.md`: สุขุม, dense, เน้นข้อมูลและสถานะมากกว่างานตกแต่ง
- Signature element คือ `Scope Rail Tabs` แนวนอนใต้ Page intro: Global แยกจากกลุ่ม Modern Trade อย่างชัดเจน พร้อม readiness badge และ shared-source marker
- ใช้ Palette/Type/Radius/Shadow เดิมทั้ง Application ไม่สร้างสีประจำแบรนด์ต่อ MT; ความแตกต่างเกิดจาก label, code และสถานะเท่านั้น
- Layout desktop: Scope tabs → scope summary strip → standardized sections → sticky save bar
- Layout narrow: tabs scroll แนวนอน, section header/actions wrap เป็นลำดับ, control grid ลดเหลือหนึ่ง column โดยไม่ซ่อน Function

```text
┌ Settings / scope explanation ──────────────────────────────────────┐
├ Global │ TWD │ HP · shared │ MH · shared │ GH │ SCG │ HH │ TA ───┤
├ Scope summary: ownership · source · readiness · last updated ─────┤
├ 01 Data Source & Automation ───────── status ───── contextual action┤
│  controls / disabled capability message                            │
├ 02 Data Mapping & Governance ──────── status ───── contextual action┤
├ 03 Historical Data & Coverage ─────── status ───── contextual action┤
├ 04 Report Configuration ───────────── status ───── contextual action┤
└ dirty summary ───────────────────────────────────── Save changes ──┘
```

## Component Plan

- `SettingsPage.tsx`: เป็น Scope controller, tab semantics, dirty-state aggregation และ focus routing
- เพิ่ม config registry สำหรับ label/capability ของ Global และแต่ละ MT; ห้ามกระจายเงื่อนไข MT ซ้ำใน JSX
- เพิ่ม reusable `SettingsScopeTabs`, `SettingsSection` และ `UnavailableCapability` โดยใช้ semantic HTML และ existing design tokens
- แยก Global content จาก `SystemSettingsPage`: Data Connection, Notifications, System Health & Alerting
- parameterize MT settings shell จาก `TwdSettingsPage` ให้รับ MT code/capability โดย TWD ใช้ Function เดิมครบ
- refactor `FileShareSettingsCard` ให้ Global แสดงเฉพาะ Base UNC/AD credential และแต่ละ MT Tab แสดง profile Subfolder/Automation/Run status
- HP/MH ใช้ shared source/schedule object เดิม แก้จาก Tab ใดเรียก save path เดียวกันและ invalidate/refetch ทั้งสอง view
- GH/SCG/HH/TA แสดง Section template ครบพร้อม Disabled state โดยไม่เรียก endpoint ที่ไม่มี

## State และ Save Contract

- เก็บ draft แยกตาม scope แต่รวม dirty fields ที่ Page controller
- `Save changes` บันทึกเฉพาะ endpoint/field ที่เปลี่ยน และแสดงผลสำเร็จหรือผิดพลาดแยกตาม Scope โดยไม่ล้าง draft ส่วนที่บันทึกไม่สำเร็จ
- Immediate actions ไม่ถือเป็น dirty setting และคง loading/disabled/result feedback ของเดิม
- สลับ Tab ไม่ทิ้ง draft; ออกจากหน้าเมื่อมี unsaved changes ต้องแจ้งเตือนตาม pattern ที่ระบบรองรับ
- Deep-link/focus จาก Monitoring ไป Data Coverage ต้องเปิด TWD Tab และ focus Section เป้าหมาย

## Implementation Phases

1. เพิ่ม Settings capability/config model และ reusable visual primitives พร้อม tests
2. สร้าง Global tab และย้าย Data Connection/Telegram/Technical Health โดยคง handlers/API เดิม
3. สร้าง TWD tab จาก Function เดิมและเชื่อม dirty/save orchestration
4. สร้าง HP/MH tabs พร้อม shared-source/shared-schedule indicator และ synchronized state
5. เพิ่ม GH/SCG/HH/TA template แบบ Disabled พร้อม readiness explanation
6. Responsive/accessibility polish, browser QA และ full regression

## Verification Plan

- Component tests: keyboard tabs, active/current semantics, consistent section order และ disabled capability
- Save tests: changed-only requests, multi-scope dirty state, partial failure, retry และ tab switching ไม่ทำ draft หาย
- HP/MH tests: edit schedule จาก HP แล้ว MH สะท้อนค่าเดียวกัน, run result แยก MT, ไม่สร้าง duplicate schedule
- Navigation test: Monitoring → Data Coverage เปิด Settings/TWD/target section ถูกต้อง
- Regression: FileShare test/save, Telegram, Technical Health, TWD mapping/backfill/coverage/report setting และ automatic run เดิม
- Run frontend full test, ESLint, production build, backend full test/Ruff และตรวจ desktop 1440/1024 กับ narrow 768/375

## Deployment และ Rollback

- Phase นี้ควรเป็น frontend-first; backend เปลี่ยนเฉพาะเมื่อ API ปัจจุบันไม่สามารถแยก global/profile payload โดยไม่แตะ business logic
- Deploy หลัง screenshot review และ Product Owner ยืนยัน Global/TWD/HP/MH อย่างน้อย
- Rollback ด้วย application version เดิม; ไม่มี migration/data transformation ใน scope ที่วางแผนไว้

## Open Decisions

- ไม่มี Business Rule ค้าง; รอ Product Owner ยืนยัน PRD และ Implementation Plan ก่อนเริ่มแก้โค้ด

# TWD Settings Parity for HP/MH — Implementation Plan

## Architecture Direction

- เปลี่ยน `TwdSettingsPage` เป็น reusable `ModernTradeSettingsPage` ที่รับ `mtCode` และ `mtName`; TWD ใช้ Component เดียวกันด้วย props `TWD` เพื่อรักษา Reference Logic
- เปลี่ยน client API ที่ hardcode TWD ให้รับ `mtCode` ทุกคำสั่ง รวมทั้ง Settings, Mapping exchange, Coverage และ SKU Backfill
- เพิ่ม generic backend routes ภายใต้ Modern Trade scope และคง TWD legacy routes/response contract ไว้ระหว่าง refactor เพื่อลด regression risk
- จำกัด allowlist ของ Function ชุดนี้ที่ `TWD`, `HP`, `MH`; MT อื่นห้าม fallback ไป TWD

## Backend Work

1. Generalize TWD settings service ให้ lookup ModernTrade จาก code และคำนวณ Mapping attention/report setting ต่อ MT
2. Generalize Mapping export/import service ให้รับ ModernTrade ที่ resolve แล้ว แทนการ query TWD ภายใน service; filename, audit actor และข้อความ conflict ใช้ code ปัจจุบัน
3. ใช้ Data Coverage endpointเดิมที่รองรับ `mt_code` และเพิ่ม availability response ใน Settings summary เพื่อแยก no-data จาก count zero
4. เปิด Backfill API สำหรับ HP/MH ด้วย strategy ตาม source group:
   - TWD ใช้ downloader/parser/append path เดิมโดยไม่แก้ behavior
   - HP/MH อ่าน shared Inventory/Sales ZIP pair แต่ filter และ append เฉพาะ prefix/SKU ของ MT เป้าหมาย
   - Run, progress, result, stop/resume, audit และ notification ผูก MT เป้าหมาย ไม่ใช้ sibling MT เป็น owner ของ SKU Backfill
5. เพิ่ม transaction and isolation tests เพื่อพิสูจน์ว่า HP action ไม่แก้ MH และกลับกัน

## Frontend Work

1. สร้าง MT Settings Template กลางจาก markup และ interaction ของ TWD โดยคง section order และ styles เดิม
2. ส่ง `mtCode` เข้า Mapping export/import, Unmatched settings, Report page size, Coverage download และ Backfill ทุกครั้ง
3. เปลี่ยน copy ที่ระบุ “ไทวัสดุ” ให้ใช้ชื่อ MT ปัจจุบัน โดยข้อความและ action name อื่นคงมาตรฐานเดียวกัน
4. ใช้ availability metadata แสดง `ยังไม่มีข้อมูล` โดยไม่แสดงตัวเลขเมื่อยังไม่มี source data; Loading, Error และ true-zero แสดงคนละ state
5. แทน Disabled capability cards ใน HP/MH ด้วย Function จริงชุดเดียวกับ TWD; GH/SCG/HH/TA ยังไม่เรียก API

## Verification

- Backend tests: generic settings lookup, per-MT mapping export/import, empty vs zero, HP/MH backfill isolation, authorization และ legacy TWD contract
- Frontend tests: TWD/HP/MH API URLs, Section parity, MT-specific copy, empty/loading/error, keyboard tabs และ cross-tab state
- Regression: TWD mapping workbook, TWD backfill, report settings, coverage download และ unmatched logic ต้องให้ผลเดิม
- Run Ruff/backend suite, ESLint/frontend suite และ production build ก่อน deploy

## Delivery Gate

- Phase 1 เริ่มจาก generic Settings/Mapping contract และ Template UI
- Phase 2 เปิด HP/MH SKU Backfill strategy พร้อม isolation tests
- ยังไม่ deploy จนกว่า Product Owner ตรวจหน้า Local และอนุมัติ

## Open Decision

- ไม่มี Business Rule ค้างหลังยืนยันขอบเขต TWD/HP/MH, per-MT ownership และข้อความ `ยังไม่มีข้อมูล`
# TWD Performance Multi-Range and Inventory Turnover Prototype — Implementation Plan

## Project Summary

ขยาย TWD Matrix Performance ให้รองรับ Date ranges สูงสุด 12 ช่วงแบบไม่ทับกัน แก้คอลัมน์ขวาสุดที่ถูก Scrollbar บัง และเพิ่ม TOM/TOD พร้อมค่าเฉลี่ยใน Inventory โดยให้ App/API/Excel ใช้ Filter และสูตรเดียวกัน รอบนี้ทำเฉพาะ TWD Prototype และไม่เปลี่ยน Logic เดิมนอก Scope

## Goals And Non-Goals

### Goals

- Date range editor ที่ตรวจ Conflict ทันทีและใช้ Keyboard ได้
- Canonical range union ที่ทุก Performance query และ Export ใช้ร่วมกัน
- TOM/TOD แบบ Decimal ROUND_HALF_UP ตรงตาม Business Rule
- Sticky identity + TOM/TOD และ right-end scroll clearance ที่อ่านตัวเลขได้ครบ
- Header average คำนวณจาก Filtered SKU universe ก่อน Pagination
- Automated tests ครอบคลุม Single/multi range, turnover edge cases, export parity และ UI regression

### Non-Goals

- ไม่ rollout ไป HP/MH/MT อื่นใน Phase นี้
- ไม่เปลี่ยน Month selector, Mapping, Detail workflow, Pagination policy หรือ metric definitions เดิม
- ไม่เพิ่มตารางฐานข้อมูลหรือ migration หาก Query จาก summaries/facts เดิมทำได้ตาม performance target

## Technical Architecture

### Frontend

- เปลี่ยน view state จาก `dateFrom/dateTo` เดี่ยวเป็น canonical `dateRanges[]` พร้อม migration จาก Local Storage shape เดิม
- Date picker เก็บ draft rows, normalize เมื่อ Apply และแสดง row-level/cross-row error แบบ `aria-live`
- API client serialize ranges ด้วย contract เดียวสำหรับ Performance, Item detail และ Excel export
- Matrix รับ `tom`, `tod`, `averageTom`, `averageTod`; render เฉพาะ Inventory และคำนวณ Sticky offsets ตาม Description state

### Backend

- เพิ่ม query parser สำหรับ Date range list สูงสุด 12 ช่วง และรองรับ `date_from/date_to` เดิมระหว่าง compatibility window
- Normalize และ sort ranges; reject incomplete/invalid/overlapping ranges ด้วย HTTP 422 ที่บอกช่วง Conflict
- สร้าง shared SQL date-union predicate และใช้กับ row selection, summary, column total, pagination scope, item detail และ export
- Turnover service ใช้ Reference Date, positive Sales Qty lookback 3 เดือน และ Decimal `ROUND_HALF_UP`; ไม่คำนวณจากค่าที่ Frontend aggregate เอง
- Inventory response เพิ่ม per-item turnover และ global turnover summary; Sales response เดิมไม่เปลี่ยน

## File And Module Plan

### Frontend Files

- `src/features/performance/types.ts`: เพิ่ม `DateRange` และ turnover response types
- `src/features/performance/DateRangePicker.tsx`: multi-row editor สูงสุด 12 ช่วง, add/remove, immediate validation
- `src/features/performance/PerformanceToolbar.tsx`: เปลี่ยน DateRangePicker contract เฉพาะตำแหน่งเดิม
- `src/features/performance/PerformancePage.tsx`: state migration, canonical ranges, summary wiring และ export/detail parity
- `src/features/performance/performanceApi.ts`: serialize ranges ให้ทุก request path
- `src/features/performance/PerformanceMatrix.tsx`: TOM/TOD/AVG columns และ semantic labels
- `src/features/performance/performanceMath.ts`: เฉพาะ display/range helpers ที่ไม่ทำ Business calculation
- `src/styles/app.css`: multi-range layout, inline error, sticky offsets และ scrollbar/end gutter
- Tests คู่กับ component/API/math filesข้างต้น

### Backend Files

- `backend/app/api/performance.py`: parse/validate ranges, shared predicate wiring และ turnover response
- เพิ่ม utility/service เฉพาะ range/turnover หาก route file ใหญ่เกินกว่าจะรักษาความชัดเจน
- `backend/app/services/performance_export.py`: ใช้ query/filter/turnover contract เดียวกับ App
- `backend/tests/test_performance.py`: ranges, pagination, summary และ turnover cases
- `backend/tests/test_performance_export.py`: workbook parity และ TOM/TOD

### Documentation

- `README.md`: อัปเดต Performance API example หลัง contract คงที่
- `HANDOFF.md`: บันทึก formula, rollout boundary และผล verification หลังเสร็จ
- `design-system/mt-pulse/pages/twd-performance.md`: เพิ่มเฉพาะ page override สำหรับ multi-range/sticky columns โดยไม่แก้ Master tokens

## Data Model Draft

- ไม่มี migration ในแผนเริ่มต้น
- ใช้ `DailySkuSummary` สำหรับ positive Sales Qty lookback และ inventory snapshot เมื่อ coverage ถูกต้อง
- ใช้ Fact fallback ตามกลไกเดิมเมื่อ summary coverage ไม่ครบ
- หาก profiling พบ bottleneck จึงเสนอ index เพิ่มเป็นงานแยกพร้อม `EXPLAIN ANALYZE`; ห้ามเพิ่ม index โดยไม่มีหลักฐาน

## API And Integration Plan

- เพิ่ม query parameter แบบ repeated value เช่น `date_range=YYYY-MM-DD,YYYY-MM-DD` สูงสุด 12 ค่า หรือรูปแบบเทียบเท่าที่ผ่าน test ก่อนยืนยัน contract ใน Code
- Compatibility: request ที่มี `date_from/date_to` เดิมต้องแปลงเป็น range เดียวและให้ผลเดิม
- ถ้าส่ง contract ใหม่และเก่าพร้อมกัน ให้ Server reject อย่างชัดเจนเพื่อไม่ให้เกิด Filter ambiguity
- Response Inventory item เพิ่ม `tom: number | null`, `tod: number | null`
- Response Inventory summary เพิ่ม `averageTom: number | null`, `averageTod: number | null`, `turnoverSkuCount`
- Export endpoint รับ Filter contract เดียวกับ Performance endpoint
- Error payload ต้องระบุ index ของช่วงที่ผิด/ทับกันเพื่อ map กลับไปยัง UI row

## Phased Implementation

### Phase 1: Reproduction And Contract Tests

1. เพิ่ม failing frontend test สำหรับ overlap, boundary-touch overlap, max 12 และ Apply disabled
2. เพิ่ม deterministic layout assertion/end-clearance regression สำหรับคอลัมน์ขวาสุด
3. เพิ่ม backend failing tests สำหรับ date union และสูตร TOM/TOD ทุก edge case
4. เพิ่ม export parity test ก่อนแก้ implementation

### Phase 2: Backend Range And Turnover

1. Implement range parser/normalizer/validator
2. Refactor date predicates ให้ใช้ shared union filter โดยรักษา legacy single range
3. Implement reference-date and 3-full-month turnover query
4. Add filtered-universe averages before pagination
5. Extend export ด้วย filter/turnover values เดียวกัน

### Phase 3: Frontend Multi-Range

1. เพิ่ม `dateRanges` state และ migrate Local Storage เดิมแบบ non-destructive
2. Implement 1–12 range rows พร้อม immediate validation และ accessible feedback
3. Wire Performance, detail และ download requests ให้ใช้ ranges เดียวกัน
4. แสดง selected-range summary แบบกระชับโดยไม่ทำ Toolbar ขยายผิดปกติ

### Phase 4: Matrix TOM/TOD And Scroll Fix

1. Render TOM/TOD หลัง WA Description หรือหลัง WA Item เมื่อซ่อน Description
2. Render AVG TOM/TOD จาก Server summary ใน Inventory header
3. เพิ่ม sticky offsets/dividers/z-index สำหรับทุก Description state
4. เพิ่ม right-end clearance และ sync top/bottom scrollbar width โดยไม่มีข้อมูลหลอก

### Phase 5: Verification And Documentation

1. Backend full tests + Ruff
2. Frontend full tests + ESLint + production build
3. Visual checks: Description on/off × Branch/Date/Month × Sales/Inventory × 1/12 ranges
4. Verify keyboard, focus, `aria-live`, 1024/1440 desktop และ classic Windows scrollbar
5. Compare App กับ Excel ด้วย fixture เดียวกันและตัวอย่างสูตร `5/3 → 1.67; 10/1.67 → 5.99; 5.99×30 → 179.70`
6. อัปเดต README/HANDOFF และเตรียม screenshot ให้ Product Owner ตรวจ

## Dependencies

- ใช้ React 19.2.8, TypeScript 6.0.3, FastAPI/SQLAlchemy/Decimal และ Excel library ที่โครงการใช้อยู่
- ไม่เพิ่ม Frontend date-picker หรือ calculation package ในแผนเริ่มต้น

## Security And Error Handling

- Server validate จำนวนช่วง, ISO date, from/to และ overlap ซ้ำทุก request
- จำกัด input lengths/count เพื่อป้องกัน query amplification
- Invalid ranges ไม่รัน report query และคืนข้อความที่ระบุจุดแก้ได้
- Export ต้องใช้ authorization/filter boundary เดียวกับ report เดิม

## Test And Verification Plan

- Range unit tests: 1, 12, 13 ranges; same-day; adjacent; contained; partial; reversed; unsorted; duplicated
- Query integration: gap exclusion ใน rows/dates/summary/columns/pagination/detail/export
- Turnover: normal, zero month, all-zero sales, missing reference-date stock, negative stock, zero stock, returns only, Branch/SKU filters, rounding half-up
- Average: all filtered SKUs across pages, exclude null turnover, remain stable on page change
- UI: immediate error, conflict labels, add/remove limits, Apply disabled, Local Storage migration
- Matrix: sticky order Description on/off, all Inventory views, last column readable at max scroll
- Regression: legacy single range and all existing Performance tests

## Deployment Or Release Checklist

- รอบนี้พัฒนาและตรวจ Local ก่อน
- Product Owner ตรวจ Prototype และ Excel parity ก่อนอนุมัติ rollout/deploy
- Commit แยก Feature จาก dirty worktree เดิมเท่าที่ทำได้ และไม่รวมไฟล์ชั่วคราว
- ก่อน deploy ต้อง backup, run migrations เฉพาะถ้ามี (คาดว่าไม่มี), smoke API/UI/export และมี rollback revision
- ยังไม่ push/deploy จนกว่าผู้ใช้สั่งชัดเจน

## Open Decisions

- ไม่มี Business Rule ค้าง; API serialization exact shape เลือกระหว่าง implementation โดยต้องรักษา compatibility และ testability ตามแผน

# TWD Sho/Pro SKU Attention Flags — Implementation Plan

## Project Summary

เพิ่ม Shared Sho/Pro metadata สำหรับ TWD SKU ใน Matrix และ Excel โดยเก็บใน PostgreSQL แยกจากข้อมูล Fact/Mapping, บันทึกทันที และใช้ Filter ฝั่ง Server ก่อน Summary/Pagination ทั้งหมด

## Goals And Non-Goals

### Goals

- Sticky Sho/Pro checkbox columns ก่อน TWD SKU ในทุก Mode/View
- Shared state ข้าม User profile ด้วย key `TWD + Source SKU`
- Instant partial update พร้อม optimistic UI, pending state, rollback และ Error feedback
- Flag filter ครบ 5 ค่าและใช้ Scope เดียวกับ KPI/SUM/AVG/Pagination/Export
- Excel แสดง Sho/Pro และสีตรงตาม Screen

### Non-Goals

- ไม่เปลี่ยน Fact, Mapping, Import, Sales/Inventory/TOM/TOD formulas
- ไม่เปลี่ยน default SKU ordering
- ไม่เพิ่ม Bulk edit, Auto-tag หรือ Admin permission
- ไม่ rollout HP/MH ใน Phase แรก

## Technical Architecture

### Database

- Migration ใหม่ต่อจาก Alembic head ปัจจุบัน เพิ่ม `sku_analysis_flags`
- Columns: id, modern_trade_id FK, source_sku, is_showroom, is_promotion, updated_at และ actor field ตาม convention ที่ระบบรองรับ
- Unique constraint `(modern_trade_id, source_sku)` และ index `(modern_trade_id, is_showroom, is_promotion, source_sku)` สำหรับ Filter
- Row อยู่ต่อเมื่อ Mapping/SKU ถูก Inactive และไม่ถูกกระทบจาก Import

### Backend API

- เพิ่ม enum query `sku_flag=all|sho|pro|both|none` ใน `GET /api/performance` และ `/api/performance/export`
- Join/exists Flag predicate ใน Candidate SKU query ก่อน total SKU, active Branch, totals, column totals, TOM/TOD และ pagination
- Item projection ส่ง `isSho`, `isPro`; Missing row ตีความเป็น false/false
- เพิ่ม PATCH endpoint แบบ partial updateสำหรับ `isSho` หรือ `isPro` ทีละ Field; upsert ด้วย unique key และสร้าง AuditEvent
- Update response ส่ง canonical state กลับให้ Frontend; endpoint ต้อง validate MT/SKU และไม่แก้ Mapping/Interest
- Export เรียก Performance contract เดิมพร้อม `sku_flag` เพื่อหลีกเลี่ยง Logic ซ้ำ

### Frontend

- `types.ts`: เพิ่ม `SkuFlagFilter`, `isSho`, `isPro`
- `performanceApi.ts`: serialize filter และเพิ่ม mutation function สำหรับ partial flag update
- `PerformancePage.tsx`: state/filter persistence, mutation state, optimistic patch และ refetch เมื่อ Active Flag filter ทำให้ Scope เปลี่ยน
- `PerformanceToolbar.tsx`: เพิ่ม Filter `ทั้งหมด/Sho/Pro/Sho + Pro/ยังไม่กำหนดสถานะ`
- `PerformanceMatrix.tsx`: เพิ่ม Sticky Sho/Pro ก่อน Source SKU, accessible labels และ pending/disabled state เฉพาะ checkbox ที่กำลังบันทึก
- `app.css`/TWD visual layer: explicit sticky offsets และ row overlay statesที่อยู่ร่วมกับ Heatmap/Selected/negative values
- Detail Drawer แสดง Sho/Pro ของ SKU เดียวกันแบบ read-only status เพื่อรักษาบริบททุก View

### Excel

- `performance_export.py`: เพิ่ม Sho/Pro columns ก่อน Source SKU, text `SHO`/`PRO`, column widths, freeze pane offset และ filter metadata
- ใส่ translucent-equivalent fills/accent สำหรับ Sho only, Pro only และ Both โดยรักษา Heatmap conditional formatting และ number formats
- Export ทุก Row ที่ผ่าน Filter ไม่ขึ้นกับหน้าปัจจุบัน และ Summary ใช้ชุดข้อมูลเดียวกับ App

## Phased Implementation

### Phase 1 — Contract, Migration And Failing Tests

1. เพิ่ม model/migration และ backend tests สำหรับ unique scope, persistence หลัง Mapping change และ partial update
2. เพิ่ม API/query contract tests สำหรับ 5 filters, summary/pagination และ TWD-only scope
3. เพิ่ม Frontend type/API tests และ Matrix interaction tests ก่อนแก้ implementation

### Phase 2 — Backend State And Filtering

1. Implement repository/service สำหรับ read/upsert Flag และ Audit
2. Wire Item projection และ Flag predicate เข้า shared Performance filter builder
3. ยืนยัน KPI/SUM/AVG TOM/TOD/Branch/SKU counts ตรงกับ filtered SKU set
4. Wire Export endpoint ด้วย query contract เดียวกัน

### Phase 3 — TWD Matrix And Filter UI

1. เพิ่ม Filter control และ Local Storage migration ที่ backward compatible
2. เพิ่ม Sho/Pro sticky columns, optimistic interaction, pending indicator และ rollback on failure
3. เพิ่ม four row states: none, Sho, Pro, Both โดยคง Heatmap/Selected/Return semantics
4. ตรวจ Description on/off, TOM/TOD offsets และ horizontal scroll end clearance

### Phase 4 — Excel Parity

1. เพิ่ม status columns/text/colors และ filter metadata
2. ตรวจ Workbook ด้วย openpyxl และเปิดด้วย Microsoft Excel ว่าไม่เกิด Repair warning
3. Compare Screen/Excel สำหรับทั้ง 5 filters, Sales/Inventory และทุก View

### Phase 5 — Performance And Regression

1. Benchmark API all/sho/pro/both/none บนข้อมูล TWD จริง; เปรียบเทียบ baseline ล่าสุด
2. ตรวจ Toggle latency และไม่ rerender numeric matrix โดยไม่จำเป็น
3. รัน Backend full suite + Ruff, Frontend full suite + ESLint + production build
4. Browser QA keyboard/focus/contrast และความชัดของ Row states บน Heatmap on/off

## Test Matrix

- State: none, Sho, Pro, Both; check/uncheck; refresh; Browser/Profile อื่น; Mapping inactive/reactivate
- Concurrent: User A เปลี่ยน Sho ขณะ User B เปลี่ยน Pro โดยค่าหนึ่งไม่ทับอีกค่า
- Filters: all/sho/pro/both/none ก่อน pagination พร้อม KPI/SUM/AVG/Branch counts
- Views: Sales/Inventory × Branch/Date/Month × Description on/off × Heatmap on/off
- Visual: selected + flag, negative/return + flag, trial/unmatched + flag, loading/error rollback
- Excel: columns, text, colors, totals, formulas, auto-filter, freeze panes, no repair warning และ page-independent export
- Regression: date ranges, TOM/TOD, report page size, SKU/Branch filters, detail drawer และ performance fast paths

## Deployment And Rollback

- พัฒนาและตรวจ TWD Local ก่อน; ยังไม่ Push/Deploy จน Product Owner อนุมัติ
- ก่อน Server migration สำรอง PostgreSQL และตรวจ backup archive
- Deploy migration + API + Web; smoke shared persistence ด้วยสอง Browser sessions และ Excel export
- Rollback application revision ได้โดยเก็บตาราง Flag ไว้; downgrade migration ลบเฉพาะ `sku_analysis_flags` และห้ามแตะ Fact/Batch/Mapping

## Confirmation Gate

- Phase แรกสร้างเฉพาะ TWD Prototype
- Sho/Pro เป็น Shared metadata ไม่มีผลต่อสูตร แต่ Filter มีผลต่อ Scope ของ Summary/Excel เหมือน Filter อื่น
- รอ Product Owner ยืนยัน PRD และแผนนี้ก่อนเริ่ม Phase 1 implementation

## Implementation Status — 9 September 2026

- Phase 1 complete: model, Alembic migration, TWD-only partial PATCH endpoint, AuditEvent, frontend types/query/mutation contract และ automated contract tests พร้อมแล้ว
- Phase 2 complete: `sku_flag=all|sho|pro|both|none` ทำงานจริงใน Performance และ Export API โดยกรอง candidate SKU ก่อน summary, pagination, branch count, column totals และ TOM/TOD
- Performance item projection ส่ง `isSho`/`isPro` สำหรับ TWD และตีความ SKU ที่ไม่มี Flag row เป็น false/false
- Daily/Monthly summary fast paths ใช้ Flag predicate เดียวกับ Fact path; Export ส่ง filter เข้า Performance contract เดิมโดยไม่สร้าง Query logic ซ้ำ
- Phase 3 complete: TWD Matrix มี Sticky `Sho`/`Pro`, Filter 5 ค่า, Optimistic save, per-field pending/rollback, Error feedback และ read-only status ใน Detail Drawer
- Row state แยก none/Sho/Pro/Both ด้วยข้อความ Checkbox + Amber/Violet/Dual overlay โดยคง Heatmap, negative typography และ Blue selected boundary
- Filter ถูกเก็บใน TWD view preference แบบ backward compatible; HP/MH ไม่แสดง control และไม่เปลี่ยน behavior
- Frontend full suite 80 tests, Backend full suite 127 tests, ESLint, production build และ Ruff เฉพาะ Sho/Pro backend paths ผ่าน
- ยังไม่เปลี่ยน summary/calculation, TOM/TOD, Excel layout หรือ rollout ไป HP/MH
- ยังไม่ Push/Deploy ตาม Deployment Gate; ขั้นต่อไปคือ Phase 4 Excel Parity เมื่อ Product Owner สั่งเริ่ม
# Multi-MT Import Operations Workspace — Implementation Plan (10 September 2026)

## Project Summary

ปรับหน้า Import เดิมจาก TWD single-file form ให้เป็น Operations Workspace แบบหลาย MT พร้อม Admin Folder Batch จากเครื่อง User, strict MT detection, per-file duplicate/validation, background processing, retry และ 7-day staging retention โดยรักษา Import Pipeline เฉพาะ TWD/HP/MH เดิมและย้าย actionable import issues ออกจาก Monitoring

## Goals And Non-goals

### Goals

- Compact header และ shared visual template ตาม MT Pulse Operations Ledger
- Overview + dynamic MT tabs สำหรับ TWD/HP/MH และ MT ที่เปิดในอนาคต
- Single-file upload สำหรับ User ทุกคนและ Folder Batch สูงสุด 200 ไฟล์สำหรับ Admin
- MT detection ที่ไม่พึ่ง SKU format พร้อม Quarantine/Strict Validation
- Upload concurrency 3, per-file resume/retry, background worker และ partial success
- Import issue management อยู่หน้า Import; Monitoring เป็น summary + deep link

### Non-goals

- ไม่เปลี่ยน parser, pairing, reconciliation, mapping, duplicate หรือ transaction logic ของ TWD/HP/MH
- ไม่เปิด GH/SCG/HH/TA จนมี Importer และ Configuration จริง
- ไม่อ่าน Subfolder, ไม่เฝ้า Folder ต่อเนื่อง และไม่แก้ UNC/Schedule
- ไม่เพิ่ม Force Import หรือ Admin override ข้าม Strict Validation

## UX And Visual Direction

- ใช้ `design-system/mt-pulse/MASTER.md` เป็น Source of Truth: Primary sky/navy, Leelawadee UI/Aptos, Cascadia Mono สำหรับรหัส/ตัวเลข, Control 34px และ density 9/10
- ไม่ใช้ผลค้นหาแนว Exaggerated Minimalism/สีเขียว เพราะขัดกับ Application Theme และความต้องการพื้นที่ข้อมูลสูง
- Header เป็นแถวเดียว: Page title + compact context/status; ตัด Breadcrumb ซ้ำ, Phase badge และคำอธิบายยาว
- Top workspace: source selector + action ด้านซ้าย, Batch summary/progress ด้านขวา; ถัดลงมาเป็น Overview/MT tabs และ File ledger
- File ledger ใช้ stable file ID, server-side pagination/filter, status icon+text, inline error, per-file Retry และ bulk confirm เฉพาะ eligible files
- Activity เดิมรวมเข้า Batch ledger/history ไม่วาง Card แยกยาวที่ดันข้อมูลสำคัญลงล่าง

## Technical Architecture

### Frontend

- Refactor `ImportPage.tsx` เป็น container ขนาดเล็กและแยก `ImportHeader`, `ImportTabs`, `ImportSourcePanel`, `FolderUploadPanel`, `ImportBatchSummary`, `ImportFileLedger`, `ImportIssueActions` และ `ImportHistory`
- ใช้ `<input type="file" webkitdirectory multiple>` สำหรับ browser fallback; filter เฉพาะ `webkitRelativePath` ระดับแรกและแสดงไฟล์ระดับลึกที่ถูกละเว้น
- Upload queue ส่งพร้อมกันสูงสุด 3 ไฟล์และเก็บ server file/session ID เพื่อ Retry เฉพาะรายการ
- Poll active batch แบบ bounded interval และหยุดเมื่อ terminal; page reload โหลด active/recent batches จาก Server
- Route/query contract รองรับ `?mt=HP&status=failed&batchId=...` สำหรับ Monitoring deep link
- User role ควบคุมการแสดง Folder mode; Server authorization เป็น enforcement หลัก

### Backend Services

- เพิ่ม detector registry ที่คืน source group/MT, confidence state, evidence และ strict validator callback
- TWD detector เรียกโครงสร้าง/validation ของ TWD importer เดิม; HP/MH detector ระบุ `HP_MH` source group, จับคู่ Sales/Inventory และปล่อย splitter/importer เดิมแยก HP/MH
- แยก Staging service, upload-session service, batch orchestrator, cleanup service และ issue projection ออกจาก route
- Worker claim queued files/jobs แบบ transaction-safe; อัปเดต progress และ heartbeat โดยไม่เก็บผลรายไฟล์ขนาดใหญ่ใน JSON ก้อนเดียว
- Reuse existing checksum/business fingerprint/period conflict checks ก่อน Confirm และก่อน Import จริงอีกครั้ง

## Data Model Draft

### `manual_upload_batches`

- `id`, `status`, `source_mode`, `detected_source_group`, `detection_status`
- `requested_by`, `created_at`, `upload_completed_at`, `confirmed_at`, `finished_at`
- counters: total/uploaded/new/duplicate/eligible/imported/failed/needs_review
- `expires_at`, `last_activity_at`, optional summary/error

### `manual_upload_files`

- `id`, `upload_batch_id`, safe display filename, size, checksum, staging object key
- relative-depth metadata โดยไม่เก็บ client absolute path
- detected MT/source group, source kind, data date, business fingerprint, validation status/reason
- processing status, retry count, resulting import batch/source file references และ timestamps
- unique upload idempotency key ภายใน Batch และ indexes สำหรับ batch/status/detected MT/expiry

Final migration naming และ reuse กับ `ImportRun`/`SourceFile` ให้ตัดสินหลังเพิ่ม contract tests; ห้ามยัดรายการ 200 ไฟล์ลง `results_json` เพราะเคยพิสูจน์แล้วว่าสร้าง Monitoring payload bottleneck

## API Plan

- `POST /api/import-upload-batches` — สร้าง Folder/Single session; Server enforce role และ limits
- `POST /api/import-upload-batches/{id}/files` — ส่งหนึ่งไฟล์พร้อม idempotency key
- `POST /api/import-upload-batches/{id}/complete-upload` — ปิดรับไฟล์และ queue detection/validation
- `GET /api/import-upload-batches` และ `GET /{id}` — filter/paginate summary + files
- `POST /api/import-upload-batches/{id}/confirm` — confirm eligible files ครั้งเดียว
- `POST /api/import-upload-files/{id}/retry` — retry terminal failed file เท่านั้น
- `POST /api/import-upload-files/{id}/resolve-mt` — Admin ระบุ expected MT แล้วเรียก strict validation ใหม่; ไม่มี force flag
- Existing single-file endpoints คง compatibility ระหว่าง rollout และค่อย route ผ่าน service เดียวกันเมื่อ parity tests ผ่าน
- Monitoring response ส่ง counts/link context เท่านั้น ไม่ embed file list

## Background Job And Storage Plan

- เพิ่ม persistent staging volume บน WA-MTPULSE-TEST/production แยกจาก application image
- เขียนไฟล์เป็น generated object key และ finalize แบบ atomic หลังรับครบ; checksum ขณะ stream และไม่อ่านทั้ง 25 MB เข้า memory หาก refactor path ใหม่
- Queue phases: `uploading → detecting → awaiting_confirmation → queued → processing → completed_with_issues/completed/failed`
- File states แยก `uploaded/detected/duplicate/needs_review/invalid/eligible/queued/importing/imported/failed/expired`
- Cleanup job รันตาม schedule ลบ staging object เมื่อครบ 7 วันและ batch/file ไม่ active; DB metadata/Audit ไม่ลบ
- จำกัดหนึ่ง active processing job ต่อ MT; `HP_MH` ใช้ lock ระดับ source group เพื่อไม่ชน Automatic Import คู่เดิม

## Phased Implementation

### Phase 1 — Contracts, Detection And Migration

1. เพิ่ม failing tests สำหรับ role limits, 1/200/201 files, 25 MB, idempotency, mixed MT, unknown MT และ HP_MH exception
2. Extract detector interface โดยครอบ importer เดิม ไม่ทำ parser ใหม่
3. เพิ่ม batch/file models และ Alembic migration พร้อม indexes/constraints
4. เพิ่ม API types และ frontend fixtures โดย UI เดิมยังทำงานได้

### Phase 2 — Staging Upload And Background Worker

1. Implement streamed staging upload, checksum และ per-file idempotency
2. Implement upload queue concurrency contract, finalize, detection/validation jobs และ persisted progress
3. Implement confirm/processing/partial success/retry และ source-group lock
4. Implement 7-day cleanup พร้อม tests กันลบไฟล์ active

### Phase 3 — Compact Multi-MT Import UI

1. ลด Header/spacing และรวม Activity เป็น ledger ตาม Master Design System
2. เพิ่ม Overview/TWD/HP/MH dynamic tabs และ filters
3. เพิ่ม Admin Folder picker, 3-file upload queue, progress, reconnect/resume และ per-file status
4. รักษา single-file flow สำหรับ User พร้อม auto-detection และ preview/confirm

### Phase 4 — Import Issues And Monitoring Deep Links

1. ย้าย actionable issue lists/actions มา Import Workspace
2. Monitoring เก็บ summary counts/health และ deep-link context
3. เพิ่ม URL state, permission tests และ consistency tests ระหว่างสองหน้า

### Phase 5 — Verification, Performance And Deployment

1. Backend full suite/Ruff; Frontend full suite/ESLint/build
2. Browser QA: User/Admin, refresh/logout, keyboard/focus, errors announced, 375/768/1024/1440
3. Load test Folder 100 และ 200 ไฟล์, network interruption, retry, mixed folder rejection และ concurrent Automatic Import
4. ตรวจ TWD/HP/MH facts, counts, duplicate protection และ Audit ก่อน/หลังด้วย fixtures/real samples
5. Backup PostgreSQL, deploy migration/API/Worker/Web, smoke Background continuation และตรวจ cleanup dry-run ก่อนเปิดจริง

## Test And Acceptance Matrix

- Detection: valid TWD, HP_MH pair, malformed archive/workbook, misleading filename, variable SKU length/leading zero, unknown/conflict
- Folder: direct files only, nested ignored, empty, 100, 200, 201 files, mixed MT, HP_MH source-group exception
- Security: User blocked from folder/bulk/resolve-MT; Admin allowed; path traversal sanitized; stale/foreign batch access blocked
- Reliability: duplicate checksum/business date, interrupted upload, repeated complete/confirm, worker restart, browser closed, retry one file, active file not cleaned
- Data integrity: partial file failure does not rollback other valid files and never creates cross-MT Fact/Mapping
- UX: compact header, status text+icon, screen-reader announcements, stable progress, deep link and server-side pagination
- Performance targets: file selection feedback <200ms, progress remains responsive, list render bounded, API payload excludes full historical results

## Deployment And Rollback

- Migration is additive; existing manual and automatic import paths remain available during staged rollout
- Feature flag Admin Folder mode until 100-file test and real-data reconciliation pass
- Rollback application to prior revision while retaining additive tables/staging metadata; pause folder jobs before rollback
- Do not delete staging volume during rollback; cleanup only through verified job

## Confirmation Gate

- First release enables TWD, HP and MH only but components/contracts are configuration-driven
- User single-file and Admin folder permissions, 200-file limit, 3 concurrent uploads, 7-day retention, partial success, strict detection, HP_MH exception and Monitoring boundary follow the approved PRD
- Product Owner confirmed Phase 1 implementation on 10 September 2026

## Implementation Status — 10 September 2026

- Phase 1 complete locally: role/file/folder limits, direct-level rule, detector registry, TWD strict importer wrapper, HP/MH shared-source detection and strict pair wrapper
- Added additive manual_upload_batches and manual_upload_files models plus Alembic migration; existing Fact, Mapping, ImportBatch and SourceFile behavior remains unchanged
- Added frontend API contracts and limits only; Import page components, layout, styles and current interaction behavior were not changed
- Backend 147 tests, Frontend 87 tests, Ruff, ESLint, production build and offline PostgreSQL migration SQL generation passed
- Phase 2 staging upload, endpoints and background worker have not started
