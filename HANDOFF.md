# MTPulse — Handoff ก่อน Restart

อัปเดตล่าสุด: 26 สิงหาคม 2026 (Asia/Bangkok)

เอกสารนี้เป็นจุดเริ่มต้นสำหรับการทำงานต่อหลัง Restart เครื่อง ให้เปิดอ่านไฟล์นี้ก่อน แล้วจึงอ่าน `PROJECT_CONTEXT.md`, `PRD.md` และ `implementation_plan.md` เมื่อต้องการรายละเอียดเพิ่ม

## สถานะล่าสุด 26 สิงหาคม 2026 — Initial Import TWD

> ส่วนนี้มีผลเหนือข้อมูลเก่าด้านล่างที่กล่าวถึง VPS, Upload Agent, UNC เดิม หรือจำนวนข้อมูลเดิม

### ข้อกำหนดที่ยืนยันแล้ว

- ระบบจะติดตั้งแบบ On-Premise และเข้าถึง UNC โดยตรง จึงไม่ใช้ Upload Agent
- UNC หลัก: `\\WA-NAS-IT03\FileShare-2\SaleOut_RPT\`
- TWD: `\\WA-NAS-IT03\FileShare-2\SaleOut_RPT\TWD\`
- ตัวอย่าง MT อื่น: TA ใช้ `\\WA-NAS-IT03\FileShare-2\SaleOut_RPT\TA\`
- RPA สร้างโฟลเดอร์รายวันและวาง Excel ไว้ภายใน ระบบต้องค้นหา `.xls`/`.xlsx` แบบ recursive
- ห้ามแก้ไข ย้าย เปลี่ยนชื่อ หรือลบไฟล์ต้นฉบับ ให้คัดลอกไปพื้นที่ชั่วคราวก่อนอ่าน แล้วลบเฉพาะไฟล์ชั่วคราว
- ป้องกัน Import ซ้ำด้วย checksum และ import history โดยคงไฟล์ต้นฉบับไว้
- Initial historical import ทำครั้งเดียว ส่วน Daily import ใช้เวลา Schedule กลางเพียงเวลาเดียว แต่ตอนนี้ให้ Schedule เป็นค่าว่างไว้ก่อน
- ไม่ต้องออกแบบ retry/lookback สำหรับกรณี RPA มาช้า เพราะผู้ใช้จะจัด Gap ของ RPA และ Schedule เอง

### ผล Preview จาก UNC — ยังไม่ได้ Import จริง

- พบไฟล์ทั้งหมด 548 ไฟล์
- ข้อมูล TWD เดิมในฐานข้อมูล: 20 batches ช่วง `2026-07-14` ถึง `2026-08-23` รวม 250,856 fact rows
- พร้อม Import แบบไม่กำกวม: 455 ไฟล์ / 4,887,580 rows
- Candidate รวมกรณีเลือกไฟล์แรกของ period ที่ชนกัน: 458 ไฟล์ / 4,922,309 rows
- ช่วงวันที่ Candidate: `2025-01-02` ถึง `2026-08-24`
- ซ้ำกับ checksum ในฐานข้อมูล 27 ไฟล์ และ checksum ซ้ำภายในแหล่งข้อมูล 52 ไฟล์
- ไฟล์ไม่ถูกต้อง 8 ไฟล์: 7 ไฟล์ขนาด 0 byte และ `2025-06-26\AC6C7232-17B9-4895-A0B8-F5FCB31808E1.xls` มีโครงสร้างเสีย
- วันที่ข้อมูลชนกัน 3 periods จึงยังห้ามเลือกอัตโนมัติหรือ Import ทั้งคู่
- 457 จาก 458 candidate files มี reconciliation warning ซึ่งสอดคล้องกับพฤติกรรมไฟล์ต้นทาง ให้ใช้ผลรวมระดับแถวและเก็บ source totals ไว้ตรวจสอบตามกติกาที่ตกลงไว้
- ผล Preview เต็มอยู่ที่ `backend/.tmp_initial_twd_preview.json`

### Period ที่มีไฟล์ขัดแย้ง

1. `2026-01-07`
   - `2026-01-08`: 11,475 rows, 99 stores, 1,621 SKUs, Amount 1,386,002.85, Qty 440
   - `2026-01-09`: สรุปเท่ากันแต่ checksum ต่างกัน
2. `2026-01-22`
   - `2026-01-23`: 11,417 rows, 99 stores, 1,642 SKUs, Amount 0, Qty 0
   - `2026-01-24`: 9,346 rows, 92 stores, 1,543 SKUs, Amount 1,074,752.28, Qty 389
   - เป็นความขัดแย้งชัดเจน ห้ามเลือกอัตโนมัติ
3. `2026-05-24`
   - `2026-05-25`: 11,837 rows, 102 stores, 1,918 SKUs, Amount 1,126,720.24, Qty 379
   - `2026-05-26`: สรุปเท่ากันแต่ checksum ต่างกัน

### จุดเริ่มงานครั้งถัดไป

1. อ่านส่วนสถานะล่าสุดนี้ก่อน และอย่าเริ่ม Preview ใหม่โดยไม่จำเป็น
2. ขอคำยืนยันผู้ใช้ก่อน Import จริง ข้อเสนอปัจจุบันคือ Import 455 ไฟล์ที่ไม่กำกวมก่อน
3. ข้าม 79 ไฟล์ซ้ำและ 8 ไฟล์ไม่ถูกต้อง และพัก 3 periods ที่ขัดแย้งไว้ให้ผู้ใช้เลือกภายหลัง
4. ก่อน Import ประมาณ 4.89 ล้าน rows ให้พิจารณา bulk insert ที่ยังคง business rules และ audit เดิม เพราะ `session.add_all()` อาจช้าเกินไป
5. หลัง Import ตรวจ batch/fact count, min/max date, duplicate, warning, coverage และ performance ของหน้ารายงาน
6. ผู้ใช้ยังไม่ได้ยืนยัน Import และ ณ จุด Handoff นี้ยังไม่มี historical file ใดถูกเขียนเข้าฐานข้อมูล

### ไฟล์ชั่วคราวและหมายเหตุฐานข้อมูล

- `backend/.tmp_initial_twd_preview.json` — ผล Preview เต็ม 548 ไฟล์ มี business metadata ห้าม commit
- `backend/tmp_preview_initial_twd_concurrent.py` — Preview แบบ 4 workers ที่ใช้งานสำเร็จ
- `backend/.tmp_preview_initial_twd.py` — script แบบ single worker ที่เลิกใช้แล้ว
- `backend/tmp_preview_marker.txt` — test marker
- เมื่อจบงานให้ลบไฟล์ชั่วคราวข้างต้น แต่ห้ามลบก่อนนำข้อมูลที่จำเป็นไปใช้งานต่อ
- `localhost:5432` และ `127.0.0.1:5432` ชี้ไปยัง Windows PostgreSQL อีกตัวและเกิด SSPI failure
- Preview ครั้งล่าสุดเชื่อม Docker PostgreSQL ผ่าน host IP `192.168.10.140`; IP อาจเปลี่ยน จึงต้องตรวจสอบใหม่ครั้งหน้า
- ตรวจฐานข้อมูลใน container ได้ด้วย `docker compose exec -T db psql -U mtpulse -d mtpulse ...`
- ห้ามหยุดหรือแก้ไข Windows PostgreSQL ตัวอื่นโดยไม่ได้รับคำสั่งชัดเจน

## 1. สถานะปัจจุบัน

- Workspace: `D:\Python\MTPulse`
- GitHub: `https://github.com/nchaiwat/MTPulse.git`
- Branch: `main`
- Commit source ล่าสุดก่อน Handoff: `12ff92d Add date totals and optimize date matrix`
- Commit เริ่มต้น: `d767775 Initial MTPulse implementation`
- ก่อนสร้างเอกสารนี้ Working Tree สะอาดและ `main` ตรงกับ `origin/main`
- Local Git author ตั้งเฉพาะ repository เป็น `nchaiwat <nchaiwat@users.noreply.github.com>`
- PostgreSQL ใช้ Docker named volume `mtpulse-postgres` ข้อมูลจึงคงอยู่หลัง Restart/หยุด container ตราบใดที่ไม่ลบ volume
- Keycloak/AD และ On-Premise Upload Agent ยังพักไว้ตามคำสั่งของ Product Owner

## 2. วิธีเปิดระบบหลัง Restart

1. เปิด Docker Desktop และรอให้ Docker Engine พร้อม
2. เปิด PowerShell ที่ workspace:

```powershell
Set-Location 'D:\Python\MTPulse'
```

3. เปิด PostgreSQL และ API:

```powershell
docker compose up -d db api
docker compose ps
```

4. เปิด Frontend development server ใน PowerShell อีกหน้าต่าง:

```powershell
Set-Location 'D:\Python\MTPulse'
npm.cmd run dev
```

5. ตรวจระบบ:

- Frontend: `http://localhost:5173`
- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

หาก clone ใหม่หรือ `node_modules` หาย ให้รัน `npm.cmd install` ก่อน `npm.cmd run dev`

หากฐานข้อมูลใหม่และยังไม่มี schema ให้รัน:

```powershell
docker compose run --rm api python -m alembic upgrade head
```

อย่ารันคำสั่งลบ Docker volume เพราะจะลบ PostgreSQL data ของ local environment

## 3. Technology Stack

- Frontend: React 19, TypeScript, Vite, CSS, Lucide icons
- Backend: FastAPI, SQLAlchemy, Alembic, Python 3.13
- Database: PostgreSQL 17
- Local integration: Docker Compose
- Tests: Vitest/Testing Library, Pytest, Ruff, ESLint
- Production เป้าหมาย: Hostinger Ubuntu VPS ผ่าน Docker/Reverse Proxy/TLS

## 4. สิ่งที่ทำเสร็จแล้ว

### Performance Matrix

- รองรับ Sales และ Inventory
- Sales รองรับ Amount และ Qty
- Inventory รองรับ Stock On Hand และ Stock On Order
- View มี Branch, Date และ Month โดย Month แสดงเฉพาะ Sales
- Sales Branch View ใช้ Month เป็นช่วงข้อมูล และเลือกเดือนล่าสุดอัตโนมัติ
- Month View เรียงด้วย key `YYYY-MM` ตามเวลา เช่น Jan 2025 → Feb 2025 → … → Aug 2026
- Matrix รองรับ Search, Branch filter, Mapping filter, Description, Unmap, Heatmap และ Pagination
- Amount ทั้งระบบเป็นยอด Ex VAT แต่ UI ใช้คำว่า `Amount` เท่านั้น
- Description จาก source ใช้ภาษาไทย ไม่แปลเป็นอังกฤษ
- เมนูหลักเป็นภาษาไทย โดยคงคำทับศัพท์ที่เหมาะสม เช่น Sales, Inventory, Amount, Qty, Branch, Date, Month, Mapping

### ความหมายของยอดรวม

- Cell ใน Sales Branch View = SKU × Branch × Month
- Cell ใน Sales Date View = SKU × Date รวมทุก Branch ที่ผ่าน filter
- Cell ใน Sales Month View = SKU × Month รวมทุก Branch ที่ผ่าน filter
- แถว `SUM` แสดงยอดรวมจากทุก SKU ที่ผ่าน filter ไม่ใช่เฉพาะ SKU ในหน้าปัจจุบัน
- `SUM` เหนือ Total = Grand Total
- `SUM` เหนือ Branch/Date/Month = ยอดรวมของคอลัมน์นั้นจากทุก SKU
- Amount และ Qty ใช้หลักเดียวกัน และไม่ตัด Return/Adjustment หรือค่าติดลบออก

### Mapping

- Export/Import Mapping เป็น `.xlsx`
- Workbook มี Sheet `Item Mapping`, `Branch Mapping` และ `วิธีใช้งาน`
- สามารถเพิ่ม TWD SKU ใหม่ต่อท้ายไฟล์ Export แล้ว Import กลับเป็น `pending` ได้ แม้ SKU ยังไม่เคยอยู่ใน Fact
- Import ไม่แก้ทับ Mapping เดิมเมื่อพบข้อมูลขัดแย้ง
- Branch Mapping เก็บรหัส/ชื่อทั้งฝั่ง TWD และ WA
- Matrix ไม่แสดงคอลัมน์ Mapping; SKU ที่ยังไม่ Mapping ใช้ตัวหนังสือสีแดง
- ปุ่ม Unmap: ตาเปิด/สีเขียว = แสดง Item ทั้งหมด, ตาปิด/สีขาว = ซ่อน Item ที่ยังไม่ Mapping

### Importer และ Backend

- Importer อ่านไฟล์ `.xls` จาก Sheet `ReportSaleSubscription`
- ใช้ `Period` ภายในไฟล์เป็น data date
- เก็บ Description ภาษาไทยตาม source
- ใช้ SHA-256 ป้องกันไฟล์ซ้ำ
- Amount คำนวณด้วย `Decimal` และหาร 1.07
- มี Import Batch, Sales/Inventory Fact, Item Mapping, Branch Mapping และ Audit Event
- Temporary file ถูกลบหลังประมวลผล

## 5. งานล่าสุด: By Date SUM และ Performance

อาการเดิม:

- Sales By Date ไม่มีแถว `SUM`
- API ส่งข้อมูลระดับ SKU × Date × Branch ให้ Browser รวมเอง
- ตัวอย่างหน้าแรก 100 SKU มี response ประมาณ 1.16 MB
- เวลาตั้งแต่กด Branch → Date จนพร้อมใช้งานประมาณ 958 ms บน development environment

สิ่งที่แก้ใน commit `12ff92d`:

- `PerformanceMatrix.tsx` แสดงแถว `SUM` ใน Sales Date View
- Frontend ใช้ API `grain=day_total` เมื่อเลือก Date
- Backend aggregate เป็น SKU × Date ก่อนส่ง Browser
- Backend สร้าง `columnTotals` รายวันจากทุก SKU ที่ผ่าน filter แยกจาก pagination

ผลตรวจจริง:

- Response ลดจากประมาณ 1.16 MB เหลือ 52 KB (ลดประมาณ 95%)
- API warm response ประมาณ 0.11–0.20 วินาที
- UI Branch → Date ประมาณ 662 ms จากเดิมประมาณ 958 ms
- Amount รวม `1,836,821.53`
- Qty รวม `698`
- Amount รายวัน: 16 ส.ค. 2026 = `1,029,022.17`, 17 ส.ค. 2026 = `807,799.36`
- Qty รายวัน: 16 ส.ค. 2026 = `353`, 17 ส.ค. 2026 = `345`
- ผลรวมรายวันตรงกับ KPI และไม่เปลี่ยนเมื่อเปลี่ยนหน้า
- Browser console ไม่มี error

หมายเหตุ: Date View ส่งจุดรวมรายวันเพื่อความเร็ว ส่วนการดูรายละเอียดตาม Branch ยังทำผ่าน Branch View ได้ หากภายหลังต้องการ Drawer ของ Date แสดงรายการทุก Branch ให้ทำ lazy-load item detail endpoint แยก ไม่ควรส่งข้อมูลทุก Branch กลับมาใน matrix response เหมือนเดิม

## 6. ข้อมูล Local ปัจจุบัน

- ข้อมูลตัวอย่างอยู่ช่วง 16–17 สิงหาคม 2026
- TWD SKU ใน source ประมาณ 2,043 SKU
- Branch 102 สาขา
- ข้อมูลประวัติ Jan 2025–Aug 2026 ตาม Excel ต้นฉบับยังไม่ได้นำเข้าครบใน PostgreSQL
- จึงยังตรวจตัวเลขตัวอย่าง Jan 2025 เช่น SKU `60406627`, Branch `60923` กับ Excel จริงไม่ได้จนกว่าจะนำเข้าข้อมูลย้อนหลัง

## 7. Business Decisions ที่ต้องรักษา

- Production ต้องย้ายไปรันบน VPS
- On-Premise ควรมี Agent/Script ส่งไฟล์ขึ้น VPS ตาม Schedule ใน Phase ถัดไป
- Keycloak จะเป็น Authentication กลางและใช้ User/Password เดียวกับ AD แต่ให้ Skip ก่อนจนกว่า workflow หลักนิ่ง
- ผู้ใช้สนใจยอดแต่ละ Branch, SKU และ Month มากกว่าวันสำหรับมุมมอง Branch
- Sales ต้องดู Amount และ Qty ได้ด้วยโครงสร้างเดียวกัน
- Branch Master/รูปแบบชื่อ Branch จะมีคำอธิบายเพิ่มเติมจาก Product Owner ภายหลัง อย่าเปลี่ยน normalization เองก่อนรับข้อมูล
- ห้ามแก้ Original File บน NAS
- ห้าม commit `.env`, Excel/CSV ธุรกิจ, database file, uploads, `node_modules`, `dist`, virtual environment หรือ cache

## 8. Performance Notes

- All Branch มี 102 คอลัมน์ จึงจำกัดเป็น 25 SKU ต่อหน้า
- Date/Month/Single Branch ใช้ 100 SKU ต่อหน้า
- Matrix cache number formatter, ไม่สร้างปุ่มสำหรับ cell ศูนย์ และ memoize table ระหว่าง loading
- All Branch เคยลดจากประมาณ 3.5–3.8 วินาทีเหลือประมาณ 0.55–0.92 วินาทีด้วย cell-budget pagination
- หาก Branch View ยังช้าเมื่อข้อมูลเพิ่ม จุดถัดไปคือ column virtualization/windowing และตรวจ PostgreSQL query plan/index จากข้อมูล Production-like
- ห้ามเพิ่ม index จากการคาดเดา ควรใช้ `EXPLAIN ANALYZE` กับข้อมูลปริมาณจริงก่อน

## 9. คำสั่งตรวจคุณภาพ

```powershell
npm.cmd test -- --reporter=dot
npm.cmd run lint
npm.cmd run build
backend\.venv\Scripts\pytest.exe backend\tests -q
backend\.venv\Scripts\ruff.exe check backend
```

ผลล่าสุดก่อน handoff:

- Frontend: 14 tests ผ่าน
- Backend: 13 tests ผ่าน
- ESLint ผ่าน
- Ruff ผ่าน
- Production build ผ่าน

## 10. Git Workflow หลังกลับมา

ตรวจสถานะก่อนทำงาน:

```powershell
git status --short --branch
git log -3 --oneline --decorate
```

ใน Codex sandbox อาจพบ `dubious ownership` เพราะ account ของ sandbox คนละตัวกับเจ้าของโฟลเดอร์ ให้ใช้เฉพาะรูปแบบนี้โดยไม่แก้ global config:

```powershell
git -c safe.directory=D:/Python/MTPulse status --short --branch
```

ก่อน commit ทุกครั้ง:

1. ตรวจ `git diff`
2. ตรวจว่าไม่มี `.env` หรือไฟล์ข้อมูลธุรกิจถูก stage
3. รัน tests/lint/build ตามความเสี่ยงของการเปลี่ยนแปลง
4. Commit เป็นงานย่อยที่ย้อนกลับได้
5. Push ไป `origin/main` เมื่อได้รับอนุญาต

## 11. ไฟล์สำคัญ

- `PROJECT_CONTEXT.md` — ข้อเท็จจริงและ business rules หลัก
- `PRD.md` — Product requirements
- `implementation_plan.md` — Architecture และแผนดำเนินงาน
- `README.md` — วิธีรันและคำสั่งใช้งานทั่วไป
- `src/features/performance/PerformancePage.tsx` — state, filters, data loading และ page orchestration
- `src/features/performance/PerformanceMatrix.tsx` — matrix, SUM, heatmap, scroll และ pagination
- `src/features/performance/performanceApi.ts` — API query/grain selection
- `backend/app/api/performance.py` — report queries, aggregation, totals และ pagination
- `backend/app/services/twd_import.py` — import workflow
- `backend/app/services/item_mapping_exchange.py` — Mapping Excel export/import
- `compose.yaml` — local PostgreSQL/API services

## 12. ลำดับงานที่ควรทำต่อ

ลำดับที่แนะนำตามบริบทปัจจุบัน:

1. เปิดระบบตามหัวข้อ 2 และ smoke test Branch/Date/Month ทั้ง Amount/Qty
2. รับคำอธิบายเพิ่มเติมจาก Product Owner เรื่อง Branch Mapping/ชื่อ Branch ก่อนปรับโครงสร้าง
3. นำเข้าข้อมูล TWD ย้อนหลังให้ครบช่วงที่ต้องเทียบกับ Excel แล้ว reconcile ระดับ SKU × Branch × Month
4. สร้างหน้า Data Status เพื่อดูวันที่ขาด, Batch, Warning และ reconciliation
5. ทำ Mapping workflow ที่มี effective date และ audit log ให้ครบ
6. ออกแบบ On-Premise scheduled upload agent
7. เตรียม production Docker, reverse proxy, TLS, backup และ monitoring สำหรับ Hostinger Ubuntu VPS
8. เชื่อม Keycloak/AD หลัง workflow หลักผ่านการยืนยัน

## 13. Checklist หลัง Restart

- [ ] Docker Desktop พร้อม
- [ ] `docker compose ps` แสดง db healthy และ api up
- [ ] `http://localhost:8000/health` ตอบสำเร็จ
- [ ] `npm.cmd run dev` ทำงาน
- [ ] เปิด `http://localhost:5173`
- [ ] Branch View แสดงเดือนล่าสุดและ SUM
- [ ] Date View แสดง SUM รายวัน
- [ ] Month View เรียงเดือนตามเวลา
- [ ] Amount/Qty สลับได้
- [ ] Git status สะอาดก่อนเริ่มงานใหม่

## 14. Ubuntu Test Server และข้อมูลทดสอบ (29/08/2026)

- Test Server: `wa-mtpluse-test` (`192.168.68.129`), Ubuntu 24.04.4 LTS, i7-1255U, RAM 15 GiB
- URL: `http://192.168.68.129`; Source: `/opt/mtpulse`; ใช้ `compose.server.yaml`
- Docker Engine 29.7.2 / Compose 5.5.0; PostgreSQL 17, API และ Web healthy
- Deployment commit เริ่มต้น: `271beb2 Add Ubuntu server Docker deployment`
- ย้าย PostgreSQL จาก Local สำเร็จ พร้อม Settings encryption key; ตรวจ Bot Token decrypt ได้โดยไม่แสดงค่าจริง
- Backup ก่อน Restore: `/opt/mtpulse/backups/server-before-local-20260829.dump`
- Backup environment: `/opt/mtpulse/backups/.env.server.before-local-restore-20260829`
- ลบ dump/key ชั่วคราวหลังย้ายแล้ว; Local database ต้นทางและ Server backup ยังอยู่

## 15. Performance รายวันทุกสาขา

เมื่อ Test Server มี 376,420 fact records และตั้ง 100 SKU ต่อหน้า:

- Algorithm เดิม `grain=day` ส่ง 244,499 points / 23.9 MB / 4.20–4.29 วินาที สำหรับหน้าแรก
- 1 Branch ใช้ 0.15 วินาที และ 1 วันทุก Branch ใช้ 0.23 วินาที จึงยืนยันว่าคอขวดคือ payload ระดับ SKU × Branch × Day ไม่ใช่กำลังเครื่อง
- Query รวมเป็น SKU × Branch ให้ 5,765 แถว และใช้ประมาณ 243 ms จาก `EXPLAIN (ANALYZE, BUFFERS)`
- เปลี่ยน Matrix รายวันตาม Branch ไปใช้ `grain=branch_range` ซึ่งรวมข้อมูลบน PostgreSQL ก่อนส่ง
- Raw daily points ยังโหลดแบบ lazy เฉพาะเมื่อเปิด Item Detail จึงไม่ตัดความสามารถดูรายละเอียดเดิม
- เพิ่ม Loading overlay พร้อม spinner เหนือตารางทั้งตอนเปิดครั้งแรกและตอนเปลี่ยน Filter/Page
- Regression: Backend ทั้งหมด 46 tests ผ่าน, Frontend ทั้งหมด 34 tests ผ่าน, Ruff files ที่แก้ผ่าน, ESLint `src` ผ่าน และ production build ผ่าน

หลัง Deploy ให้เปรียบเทียบ `/api/performance?grain=branch_range&page=1` กับ baseline ข้างต้น และ smoke test Sales Amount/Qty รายวันทุก Branch, Item Detail และ Download Excel
