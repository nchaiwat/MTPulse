# MT Pulse

Frontend MVP สำหรับตรวจสอบยอดขายและสินค้าคงคลังของ Thai Watsadu (TWD) ในระดับ `SKU × Branch × Day`

## สิ่งที่ทำงานแล้ว

- สลับ Sales และ Inventory
- สลับ Amount, Qty, Stock On Hand และ Stock On Order
- สลับ View ระหว่าง Branch และ Date
- ซ่อนหรือแสดง TWD Description และ WA Description พร้อมกันได้
- ค้นหาและกรองตามวันที่ สาขา และ Mapping Status
- แบ่งผลลัพธ์เป็นหน้า พร้อมปุ่มหน้าแรก/ก่อนหน้า/ถัดไป/หน้าสุดท้าย ช่องระบุเลขหน้าโดยตรง และรีเซ็ตเป็นหน้าแรกเมื่อเปลี่ยนตัวกรอง
- ใช้ Cell-budget pagination: All Branch แสดง 25 SKU/หน้า ส่วน View Date หรือเลือก Branch เดียวแสดง 100 SKU/หน้า
- แสดงสถานะกำลังโหลดระหว่างเรียกข้อมูล และยกเลิก request เก่าเมื่อผู้ใช้เปลี่ยนตัวกรองต่อเนื่อง
- Heatmap พร้อมตัวเลขจริงและแสดงยอดติดลบ
- Detail Drawer แสดงรายละเอียดราย SKU, Branch และ Day
- Export Item ทุก SKU ในช่วงวันที่เลือกเป็น `.xlsx` สำหรับ VLOOKUP และ Import Mapping กลับเข้าระบบได้
- Responsive Layout และ Keyboard Focus

หน้าเว็บเชื่อม `/api/performance` และแสดงข้อมูลจริงจาก PostgreSQL แล้ว โดยยังไม่เชื่อม SAP หรือ Keycloak ชุดทดสอบ frontend ใช้ fixture แยกจาก runtime data

## Backend Phase 1

Backend อยู่ใน `backend` และใช้ FastAPI + PostgreSQL + Alembic โดยรัน local environment ให้ใกล้เคียง VPS ผ่าน Docker Compose

```powershell
docker compose up -d db
docker compose run --rm api python -m alembic upgrade head
docker compose up -d api
```

ตรวจ API ที่ `http://localhost:8000/health`

ตรวจไฟล์ TWD โดยยังไม่บันทึกฐานข้อมูล:

```powershell
docker compose run --rm -v D:\path\to\samples:/samples api python -m app.cli inspect-twd /samples/source.xls
```

Importer ใช้ `Period` ในไฟล์เป็นวันที่ข้อมูล ตรวจ checksum, reconciliation และ Branch × SKU ซ้ำก่อน Import ต้นฉบับบน NAS จะไม่ถูกแก้ไข กรณี Total ของ Source ต่างจากผลรวมรายการ ระบบใช้ผลรวมรายการเป็นค่ารายงานและบันทึกสถานะ `imported_with_warnings`

Performance API:

`GET /api/performance?date_from=2026-08-16&date_to=2026-08-17&page=1&page_size=100`

รองรับ `search`, `branch_id` และ `mapping_status` (`confirmed`, `pending`, `unmatched`) โดย Summary และจำนวนหน้าจะคำนวณตามตัวกรองเดียวกับตาราง

Item Mapping Excel API:

- `GET /api/item-mappings/export?date_from=2026-08-16&date_to=2026-08-17` — Export Item ครบทุก SKU ในช่วงวันที่เลือก
- `POST /api/item-mappings/import` — รับ `.xlsx` พร้อม `effective_from`; เพิ่มเฉพาะรายการใหม่เป็น `pending` และไม่แก้ทับ Mapping เดิม

ไฟล์ Export มี Sheet `Item Mapping`, `Branch Mapping` และ `วิธีใช้งาน` โดยเก็บรหัสทุกชนิดเป็นข้อความเพื่อรักษาเลขศูนย์นำหน้า รองรับการเติม Item/Branch ฝั่ง WA ด้วย VLOOKUP แล้ว Import กลับเป็น `pending` ได้ ระบบไม่แก้ทับรหัส Mapping เดิม แต่อนุญาตให้เติมหรืออัปเดตชื่อ WA Branch สำหรับรหัสเดิมได้

## นำเข้า Mapping จาก KPI Workbook

คำสั่งนี้อ่าน Sheet `BP 22.1.26`, `สาขา` และ `CTW` โดยไม่แก้ไขไฟล์ต้นฉบับ ค่าเริ่มต้นเป็น dry-run และจะบันทึกเมื่อใส่ `--apply` เท่านั้น:

```powershell
docker compose run --rm -v "D:\path\to\mapping:/mapping:ro" api python -m app.cli import-mappings "/mapping/KPI - TWD 2026.xlsx" --effective-from 2026-08-16
docker compose run --rm -v "D:\path\to\mapping:/mapping:ro" api python -m app.cli import-mappings "/mapping/KPI - TWD 2026.xlsx" --effective-from 2026-08-16 --apply
```

Importer เลือกเฉพาะรหัสที่มีอยู่ใน Fact ปัจจุบัน, รวมแถว Mapping ซ้ำจากหลาย BP, กัน Mapping ที่ขัดแย้งออก และสร้าง Audit Event สำหรับรายการที่นำเข้า

ตาราง Matrix cache ตัวจัดรูปแบบตัวเลข, ไม่สร้างปุ่มสำหรับ cell ศูนย์ และ memoize ตารางเดิมระหว่างรอ API เพื่อลดงาน render ซ้ำ เมื่อทดสอบ All Branch 102 สาขา เวลาสลับหน้าลดจากประมาณ 3.5–3.8 วินาทีเหลือประมาณ 0.55–0.92 วินาทีบน development build

## เริ่มใช้งานบนเครื่อง

ต้องมี Node.js รุ่นที่รองรับ Dependency ใน `package-lock.json`

```powershell
npm.cmd install
npm.cmd run dev
```

จากนั้นเปิด `http://localhost:5173`

## ตรวจคุณภาพ

```powershell
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

## เอกสาร

- `PROJECT_CONTEXT.md` — Requirement และข้อมูลส่งต่องาน
- `PRD.md` — ข้อกำหนดผลิตภัณฑ์
- `implementation_plan.md` — แผนดำเนินงานทั้งหมด
- `design-system/mt-pulse/MASTER.md` — กติกา UI และ Design Tokens
