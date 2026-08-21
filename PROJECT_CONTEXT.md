# MT Pulse — Project Context

อัปเดตล่าสุด: 20 สิงหาคม 2026

## สถานะการพัฒนา Phase 1 ณ วันที่ 20 สิงหาคม 2026

- Frontend React/TypeScript สำหรับหน้า Performance พร้อมใช้งานกับข้อมูลตัวอย่างแล้ว
- สร้าง Backend Foundation ด้วย FastAPI, PostgreSQL, SQLAlchemy, Alembic และ Docker Compose แล้ว
- สร้าง TWD Importer จากโครงสร้างไฟล์ `.xls` จริง โดยใช้ sheet `ReportSaleSubscription`
- Importer อ่าน `Period` ภายในไฟล์เป็นวันที่ข้อมูล ตัด footer และเก็บ Description ภาษาไทยตาม Source
- ใช้ SHA-256 checksum ป้องกันไฟล์ซ้ำ และใช้ `Decimal` คำนวณ Amount หาร 1.07
- สำเนาไฟล์จาก NAS ถูกอ่านผ่าน temporary directory และลบทิ้งอัตโนมัติเมื่อจบงานหรือเกิดข้อผิดพลาด
- Migration แรกสร้าง Import Batch, Sales/Inventory Fact, Item Mapping, Branch Mapping และ Audit Event แล้ว
- Frontend เชื่อม `/api/performance` และแสดงข้อมูลจริงจาก PostgreSQL แล้ว โดยแบ่งหน้าละ 100 SKU
- Search รองรับ SKU และ Description ภาษาไทยจาก TWD รวมถึง WA Item ที่มี Mapping
- Filter วันที่, Branch และ Mapping Status ทำงานที่ Backend พร้อม KPI summary ตามตัวกรอง
- เพิ่ม Loading state, debounce Search, ยกเลิก request เก่า และ Pagination ก่อนหน้า/ถัดไปแล้ว
- View ใช้ชื่อ Branch/Date และผู้ใช้ซ่อนหรือแสดง Description ทั้งสองฝั่งพร้อมกันได้
- ตรวจไฟล์ `KPI - TWD 2026.xlsx` ครบ 10 Sheet และสร้าง Mapping importer แบบ dry-run/apply แล้ว
- นำเข้า Item Mapping 108 รายการ และ Branch Mapping 90 รายการ โดยใช้ effective date `2026-08-16` พร้อม Audit Event 198 รายการ
- Item Mapping 108 SKU ครอบคลุม Amount 85.97% และ Qty 91.40% ของข้อมูล 16–17 สิงหาคม แม้ครอบคลุมจำนวน SKU 5.29%
- Item conflict `060288864` ซึ่งไม่อยู่ใน Fact ปัจจุบัน และ Branch dummy `30000-New3` ถูกกันออกโดยไม่เดา Mapping
- Branch ปัจจุบันที่ยังไม่มี Mapping 12 รหัส: `60001`, `60003`, `60005`, `60011`, `60014`, `60017`, `60080`, `60808`, `60830`, `60943`, `60949`, `60977`
- แก้คอขวด Matrix แล้ว: ต้นเหตุหลักคือ React สร้าง 100 × 102 cells และปุ่มกว่า 10,000 ตัวต่อหน้า ไม่ใช่ API ซึ่งหน้า 3 ใช้ประมาณ 82 ms
- เปลี่ยนเป็น Cell-budget pagination โดย All Branch ใช้ 25 SKU/หน้า ส่วน Date/Single Branch ใช้ 100 SKU/หน้า พร้อม cache NumberFormatter, ไม่สร้างปุ่มสำหรับ cell ศูนย์ และ memoize ตารางระหว่าง Loading
- Browser benchmark ของ All Branch ลดจาก 3.5–3.8 วินาทีเหลือประมาณ 0.55–0.92 วินาทีต่อหน้า และจำนวน DOM cells ลดจาก 10,800 เหลือ 2,700
- Keycloak และ On-Premise Upload Agent ยังคงพักไว้ตามขอบเขตที่ตกลงกัน

### ข้อค้นพบจากการตรวจไฟล์จริง

ไฟล์ทั้งสองวันมีผลรวม `Stock On Hand` จากรายการไม่ตรงกับ `Total` ใน footer โดยต่างกัน 525 เท่ากัน:

| Period | ผลรวมจากรายการ | Total ใน Source | ส่วนต่าง |
|---|---:|---:|---:|
| 2026-08-16 | 77,790 | 77,265 | 525 |
| 2026-08-17 | 77,941 | 77,416 | 525 |

Amount, Qty, Stock On Order, จำนวนแถว, Store และ SKU ตรงกันทั้งหมด ผู้ใช้อนุมัติให้ใช้ผลรวมระดับรายการเป็นค่าหลักสำหรับรายงาน เก็บ Total จาก Source แยกไว้เพื่อ Audit และนำเข้าได้ด้วยสถานะ `imported_with_warnings`

นำเข้าข้อมูลจริงแล้ว 2 batch รวม 25,121 Fact rows และสร้าง `/api/performance` สำหรับส่งข้อมูลแบบแบ่งหน้า พร้อม Search/Filter, KPI summary ตามตัวกรอง, รายการ Branch, วันที่ข้อมูล และ Data Quality Warning ให้ frontend

เอกสารนี้ใช้ส่งต่องานจาก Task เดิมที่อยู่ใน `D:\Python\ESIP` ไปยังโปรเจกต์ใหม่ `D:\Python\MTPulse` เพื่อให้ Task ใหม่ทำงานต่อได้โดยไม่ต้องให้ผู้ใช้อธิบาย Requirement ซ้ำ

## 1. ภาพรวมโปรเจกต์

- ชื่อระบบใหม่: **MT Pulse**
- โฟลเดอร์โปรเจกต์ใหม่: `D:\Python\MTPulse`
- ESIP เดิมถูกประเมินว่าเดินผิดแนวทาง จึงไม่ควรนำโครงสร้าง ฐานข้อมูล หรือ business logic เดิมมาใช้ต่อโดยอัตโนมัติ
- เก็บ `D:\Python\ESIP` ไว้ชั่วคราวสำหรับอ้างอิงเท่านั้น ห้ามลบจนกว่าผู้ใช้จะสั่งชัดเจน
- MT Pulse จะเริ่มสร้างใหม่จากศูนย์ โดยระยะแรกเน้น KPI ราย SKU ของแต่ละ Modern Trade และอนาคตจะขยายได้มากกว่า SKU Performance

## 2. เป้าหมาย Phase 1

เริ่มจากข้อมูล **TWD (Thai Watsadu)** เฉพาะเดือนสิงหาคม 2026 ก่อน โดยทดลองนำเข้าจริง 1–2 วันแรก แล้วจึงขยายครบเดือน

ผลลัพธ์แรกที่ต้องได้:

1. นำเข้า Raw Data ของ TWD จาก NAS อย่างปลอดภัย
2. ตรวจสอบว่าวันใดมีไฟล์ วันใดขาดไฟล์ และไฟล์ถูกนำเข้าเมื่อใด
3. Mapping Item ของ TWD กับ Item ของ Window Asia
4. Mapping Branch ของ TWD กับ Branch ของ Window Asia
5. หน้ารายงานแบบ Application ที่ใช้แนวคิดจาก Excel เดิม แต่สะดวกกว่าในการค้นหา กรอง ดูรายละเอียด และแก้ Mapping
6. ดูข้อมูลราย Item × รายวัน × รายสาขาได้ ทั้ง Amount และ Qty
7. รองรับข้อมูล Inventory ที่มีอยู่ในไฟล์ตั้งแต่ต้น แม้หน้าแรกจะเน้น Sales

## 3. แหล่งข้อมูลและความปลอดภัยของ NAS

- NAS TWD เดิม: `\\wa-nas-it03\FileShare-2\SaleOut_RPT\TWD`
- ใช้ Path เดิมเป็นแหล่งอ้างอิงได้
- Phase 1 คาดหวังวันละ 1 ไฟล์
- ห้ามแก้ไข เปลี่ยนชื่อ ย้าย หรือลบ Original File บน NAS โดยเด็ดขาด
- ระบบต้อง Copy ไฟล์จาก NAS มายังพื้นที่ชั่วคราวบนเครื่องที่ Process
- เมื่อ Process สำเร็จหรือไม่สำเร็จ ให้ลบไฟล์ชั่วคราวทิ้ง
- Original File บน NAS เป็นแหล่งตรวจสอบย้อนหลัง
- ไม่จำเป็นต้องเก็บสำเนา Raw File ซ้ำใน Application

## 4. กติกาวันที่

- ใช้ค่า **Period ภายในไฟล์** เป็นวันที่ข้อมูลจริงเสมอ
- วันที่ของ Folder หรือวันที่พบไฟล์เป็นวันที่ระบบได้รับไฟล์ ไม่ใช่วันที่ยอดขาย
- ตัวอย่าง: Folder วันที่ 19 แต่ Period ในไฟล์เป็นวันที่ 17 ให้บันทึกข้อมูลเป็นวันที่ 17
- TWD มีลักษณะข้อมูลช้าประมาณ 2 วัน
- หลังรอบดึง NAS เวลา 08:00 เมื่อ Process เสร็จ ให้สรุปสถานะทันที ไม่ต้องมีช่วงผ่อนผัน
- ต้องนับทุกวัน รวมเสาร์–อาทิตย์ เพื่อให้เห็นชัดว่าวันใดไม่มีข้อมูล
- ค่าเวลา Schedule, NAS Path, Expected Lag และกติกาที่อาจเปลี่ยนในอนาคตควรเก็บใน System Settings แทนการเขียนตายตัวใน Code

## 5. VAT Rule

รายงานทุก MT ต้องใช้ยอด **Exclude VAT** เป็นมาตรฐานเดียวกัน

| MT | Raw Amount |
|---|---|
| HH | Exclude VAT |
| DH | Exclude VAT |
| TWD | Include VAT |
| GBH | Include VAT |
| TA | Include VAT |
| HP | Include VAT |
| MH | Include VAT |

สำหรับ TWD:

- เก็บ Source Amount ตามไฟล์ไว้เพื่อ Audit
- คำนวณ Amount Ex VAT = Source Amount / 1.07
- เก็บค่าคำนวณเต็ม precision ในฐานข้อมูล
- ปัดเศษเฉพาะตอนแสดงผล
- VAT rate และวิธีคำนวณควรเป็นค่าที่แก้ได้ใน System Settings และรองรับ effective date ในอนาคต

## 6. โครงสร้างไฟล์ TWD ที่ตรวจพบแล้ว

ไฟล์ตัวอย่าง:

- `\\wa-nas-it03\FileShare-2\SaleOut_RPT\TWD\2026-08-18\5256C64F-2B95-4EE7-8EEA-68F5C4F32CCC.xls`
- `\\wa-nas-it03\FileShare-2\SaleOut_RPT\TWD\2026-08-19\E70B927F-7529-494D-BDFB-BCBA14A84361.xls`

Sheet: `ReportSaleSubscription$`

คอลัมน์ที่พบ:

- Store
- Cat
- Sub Cat
- Brand
- SKU
- Barcode
- Description
- Product Type
- Sales Amount
- Sales Qty
- Stock OH
- Stock On Order
- Last Sold Date
- Last Receive Date

กติกา Description:

- Description ที่นำเข้าระบบเป็นภาษาไทยตาม Source
- ต้องเก็บและแสดงข้อความตาม Source โดยไม่แปลเป็นภาษาอังกฤษ

สรุปตัวอย่างวันที่รับไฟล์ 18 สิงหาคม 2026 ซึ่ง Period เป็น 16 สิงหาคม 2026:

- 12,560 rows
- 102 stores
- 2,043 SKUs
- Sales Amount Include VAT = 1,101,053.72
- Sales Amount Ex VAT = 1,029,022.17
- Sales Qty = 353
- Stock OH = 77,265
- Stock On Order = 5,902
- พบยอดติดลบ 4 rows ซึ่งต้องเก็บไว้เป็น Return/Adjustment ไม่ควรตัดทิ้ง
- ไม่พบ duplicate ในระดับ Branch × SKU

สรุปตัวอย่างวันที่รับไฟล์ 19 สิงหาคม 2026 ซึ่ง Period เป็น 17 สิงหาคม 2026:

- 12,561 rows
- 102 stores
- 2,043 SKUs
- Sales Amount Include VAT = 864,345.32
- Sales Amount Ex VAT = 807,799.36
- Sales Qty = 345
- Stock OH = 77,416
- Stock On Order = 6,338
- พบยอดติดลบ 2 rows
- ไม่พบ duplicate ในระดับ Branch × SKU

## 7. Item Mapping

- Source Mapping มาจาก SAP Business One ตาราง `OSCN`
- สำหรับ TWD ใช้ CardCode ที่ขึ้นต้นด้วย `CTW`
- ตารางนี้บอกความสัมพันธ์ระหว่าง SKU ของ TWD กับ ItemCode ของ Window Asia
- User ต้องยืนยัน Mapping เป็นราย Item ก่อนนำไปใช้
- เมื่อ User ยืนยันแล้ว Mapping มีผลใช้งานทันที ไม่ต้องรอ Admin อนุมัติ
- ต้องมี Audit Log ว่าใครแก้ จากค่าอะไรเป็นอะไร เมื่อใด และมีผลตั้งแต่วันใด
- User เลือก Effective Date เองได้
- Default Effective Date คือวันที่แก้
- ต้องมีทางเลือกให้แก้ย้อนหลังตั้งแต่ต้น หาก Mapping เดิมผิดมาตั้งแต่แรก
- กรณีหาไม่พบหรือมีหลาย Candidate ให้ User ค้นหาจาก WA Item Master แล้วเลือกเอง
- ในหน้ารายงานต้องแสดงทั้งรหัส/ชื่อสินค้าของ MT และรหัส/ชื่อสินค้าของ Window Asia อย่างชัดเจน เพราะ User สื่อสารกับ MT ด้วยรหัสของ MT

## 8. Branch Mapping

- ยังไม่มี Mapping Table สำเร็จรูป
- User จะนำข้อมูล Branch ของ CTW ทั้งหมดมาให้ภายหลัง
- ระบบนำ Branch Master เข้าระบบด้วย ไม่ใช่เพียงใช้ตรวจชั่วคราว
- ถ้าชื่อสาขาตรงกันหลัง Normalize อย่างปลอดภัย ให้ยืนยันอัตโนมัติได้
- ถ้าชื่อไม่ตรงหรือไม่มั่นใจ ให้ List ออกมาให้ User ยืนยัน
- ต้องมี Effective Date และ Audit Log เช่นเดียวกับ Item Mapping

## 9. Import และ Data Quality Log

ต้องมี Log ตรวจสอบย้อนหลังอย่างน้อยดังนี้:

- วันที่ข้อมูลจริงจาก Period
- วันที่และเวลาที่พบ/Copy ไฟล์
- Source path และชื่อไฟล์
- File checksum เพื่อกันนำเข้าไฟล์เดิมซ้ำ
- จำนวน row ที่อ่านได้
- จำนวน Store และ SKU
- ยอด Source Amount, Ex VAT Amount, Qty, Stock OH และ Stock On Order
- จำนวน Mapping ที่ครบ/รอยืนยัน/ไม่พบ
- จำนวน Error และ Warning
- สถานะ Process: discovered, copied, validating, imported, failed, duplicate, missing
- เวลาเริ่มและเวลาจบ
- Error message ที่อ่านเข้าใจได้

หน้าสถานะข้อมูลต้องแสดง Calendar/Timeline ว่า:

- วันใดมีข้อมูลครบ
- วันใดขาดข้อมูล
- วันใดไฟล์มาแล้วแต่ Process ไม่ผ่าน
- วันใดรอ Mapping
- วันใดข้อมูลมาช้ากว่า Expected Lag
- ต้องแสดงทุกวันรวมวันหยุดและเสาร์–อาทิตย์

## 10. แนวทางหน้ารายงาน TWD

อ้างอิงวิธีใช้งานจาก Excel ที่ผู้ใช้ส่งมา แต่ต้องออกแบบเป็น Application ไม่ใช่จำลองตาราง Excel ตรง ๆ

หน้าหลักควรมี:

- Sales / Inventory mode
- Metric toggle:
  - Sales: Amount Ex VAT / Qty
  - Inventory: Stock OH / Stock On Order
- KPI summary ของช่วงวันที่เลือก
- ตัวกรองวันที่ สาขา Item Mapping Status และคำค้นหา SKU/คำอธิบาย
- ตาราง Item × Branch พร้อม Heatmap
- ใช้ชื่อ View เป็น `Branch` และ `Date`
- ผู้ใช้เลือกซ่อน/แสดง TWD Description และ WA Description พร้อมกันได้ เพื่อลดความกว้างของตาราง
- คอลัมน์ด้านซ้ายแบบ Sticky:
  - MT SKU
  - MT Description
  - WA ItemCode
  - WA Description
  - Mapping Status
- คอลัมน์ถัดไปเป็น Total และรายสาขา
- คลิก Item แล้วเปิด Detail Drawer ไม่ต้องเปลี่ยนหน้า
- Detail Drawer แสดงข้อมูลรายวัน รายสาขา Sales/Inventory และประวัติ Mapping
- ต้องสามารถดูยอดติดลบ/Return ได้ ไม่ซ่อน
- ตารางต้องรองรับข้อมูลจำนวนมากด้วย virtualization หรือ server-side pagination เมื่อพัฒนา Application จริง

หลักการใช้งาน:

- เริ่มที่ภาพรวมว่าเกิดอะไรขึ้น
- User สามารถเจาะลง Item → Branch → Day ได้เร็ว
- Mapping ที่ยังไม่ครบต้องเห็นชัดและแก้ได้ในบริบทเดียวกัน
- Heatmap ใช้ช่วยหา High/Low/ผิดปกติ แต่ต้องยังอ่านค่าตัวเลขจริงได้
- Application ต้อง Responsive แต่ Phase 1 เน้น Desktop เพราะตารางมีความกว้างมาก

## 11. ต้นแบบหน้าจอที่ทำแล้ว

มี Interactive HTML prototype แล้วที่:

`D:\Python\MTPulse\mt-pulse-twd-workbench.html`

ต้นแบบมี:

- App shell และเมนู Performance, Data Status, Matching, System Settings
- Sales/Inventory toggle
- Amount/Qty และ Stock OH/Stock On Order toggle
- KPI cards จากข้อมูลตัวอย่างจริง
- Filter และ Search
- Item × Branch heatmap table
- Mapping status
- Item detail drawer

ข้อสำคัญ: ไฟล์นี้เป็นต้นแบบ UX เท่านั้น ยังไม่มี Backend, Database, NAS ingestion หรือ Authentication

## 12. Roles

วางโครงไว้ 3 Role:

- User
- Admin
- Management

Phase 1 ยังไม่ต้องใช้เวลามากกับ Role แต่โครงสร้างข้อมูลและ API ไม่ควรปิดทางการเพิ่มสิทธิ์ภายหลัง

แนวคิดเบื้องต้น:

- User: ดูรายงานและยืนยัน/แก้ Mapping
- Admin: ตั้งค่าระบบ ตรวจ Import Log และแก้ปัญหาข้อมูล
- Management: ดูภาพรวมและ Executive View ใน Phase ถัดไป

## 13. System Settings ที่ต้องเตรียมรองรับ

- MT Master และ Profile ของแต่ละ MT
- NAS path ของแต่ละ MT
- Filename/folder recognition rule
- Schedule เวลาเริ่มดึงข้อมูล
- Expected data lag
- Period extraction rule
- VAT mode และ VAT rate พร้อม effective date
- Temporary file retention policy (Phase 1 ลบทันทีหลัง Process)
- Mapping behavior และ effective-date default
- Data completeness rule
- Notification setting โดยไม่ต้องใช้ Email

## 14. ข้อมูล MT อื่นสำหรับ Phase ถัดไป

- GBH: ใช้เฉพาะไฟล์ที่ขึ้นต้นด้วย `Piyawat`
- TA: ใช้ไฟล์ที่ขึ้นต้นด้วย `Runglawan` และปัจจุบันแยก Folder ออกจาก GBH แล้ว
- HP และ MH มีไฟล์ทุกวันและใช้ Folder ร่วม `HP_MH`; ภายหลังต้องแยกประเภทจากข้อมูลภายในไฟล์อย่างถูกต้อง
- ข้อมูลที่ Excel ระบุ `Not Focus` ให้ตัดออกจากการคำนวณ
- อย่างไรก็ตาม Phase 1 นี้ให้ทำ TWD ให้ถูกต้องก่อน แล้วจึงนำ Template เดียวกันไปใช้กับ MT อื่น

## 15. สิ่งที่ยังรอคำตอบ/ข้อมูลจาก User

- Branch Master ของ CTW/TWD
- หลักเกณฑ์ business เพิ่มเติมบางรายการที่ User ขอไปสอบถามผู้ใช้งานก่อน
- การกำหนดว่า 1 SKU สามารถ Mapping หลาย WA Item หรือไม่ หาก OSCN มีกรณีพิเศษ
- เกณฑ์ Reconciliation ที่จะถือว่าไฟล์ผ่านสมบูรณ์
- Technology stack และ Database สามารถเสนอได้ แต่ควรเน้นให้รัน Local แบบ VPS-like ก่อนนำขึ้น Hostinger Ubuntu VPS

## 16. ลำดับงานแนะนำถัดไป

1. สร้างหน้า Data Status ให้เห็นวันครบ/ขาด, Batch, Warning และรายละเอียด reconciliation
2. สร้าง Mapping workflow สำหรับ TWD SKU ↔ WA Item พร้อม effective date และ audit log
3. เพิ่ม Branch Mapping workflow เมื่อได้รับ Branch Master ที่ยืนยันแล้ว
4. เพิ่ม Scheduled On-Premise Upload Agent หลัง workflow การใช้งานหลักนิ่งแล้ว
5. ขยายการนำเข้าข้อมูล TWD ให้ครบเดือนสิงหาคม 2026 และทดสอบปริมาณข้อมูล
6. เตรียม Docker production, reverse proxy, backup และ monitoring สำหรับ Hostinger Ubuntu VPS
7. เชื่อม Keycloak/AD ภายหลัง โดยไม่เปลี่ยน business workflow ที่ทดสอบแล้ว

## 17. Definition of Success สำหรับงานแรก

งานนำเข้า TWD 1–2 วันถือว่าผ่านเมื่อ:

- ไม่มีการแก้ไข Original File บน NAS
- ใช้ Period ในไฟล์เป็น data date ถูกต้อง
- นำเข้าไฟล์เดิมซ้ำแล้วไม่เกิดข้อมูลซ้ำ
- Row count, Store count, SKU count, Amount, Qty และ Stock reconcile กับ Source
- Amount คำนวณหลังหัก VAT 7% ถูกต้อง
- ยอดติดลบไม่ถูกตัดทิ้ง
- Temporary file ถูกลบหลัง Process
- Import Log บอกได้ว่าไฟล์ใดเข้าเมื่อใด ผ่านหรือไม่ผ่าน และผิดตรงไหน
- วันที่ขาดข้อมูลแสดงชัด รวมเสาร์–อาทิตย์
- User เห็นรหัส Item และ Branch ฝั่ง MT พร้อม Mapping ฝั่ง Window Asia

## 18. ความสามารถล่าสุดของหน้า Performance

- Sales Branch View ใช้เดือนเป็นช่วงข้อมูล โดยเลือกเดือนล่าสุดอัตโนมัติและให้ User เลือกเดือนอื่นจากข้อมูลที่นำเข้าได้
- Cell ใน Branch View คือ `SKU × Branch × Month`; Cell ใน Month View คือ `SKU × Month` ซึ่งรวมทุก Branch
- Matrix มีแถว `SUM` เหนือหัวคอลัมน์: ยอด Branch/Month รวมทุก SKU ที่ผ่าน Filter และยอดเหนือ `Total` คือ Grand Total โดยไม่เปลี่ยนตาม Pagination
- แถว `SUM` รองรับทั้ง Amount และ Qty รวม Return/Adjustment ตามเครื่องหมายเดิม และคำนวณฝั่ง PostgreSQL
- Sales รองรับ View `Month` ต่อจาก `Branch` และ `Date`; ปุ่มนี้ไม่แสดงใน Inventory
- เมื่อกด `Month` ระบบเลือกข้อมูลทุกวันที่นำเข้าอัตโนมัติและแสดงทุกเดือนที่มีข้อมูลทันที โดยเรียงจากเก่าไปใหม่ด้วย key `YYYY-MM` และแสดงหัวคอลัมน์รูปแบบ `Jan 2025`
- Monthly Sales รองรับทั้ง `Amount` และ `Qty`, รวม Return/Adjustment ตามเครื่องหมายเดิม และยังใช้ Search, Branch, Mapping, Description, Unmap, Heatmap และ Pagination ชุดเดิม
- API `/api/performance` รองรับ `grain=month` และรวมยอดรายเดือนที่ PostgreSQL ก่อนส่งให้ Browser เพื่อลดปริมาณข้อมูลเมื่อมีประวัติหลายปี

- Pagination มีปุ่มหน้าแรก/ก่อนหน้า/ถัดไป/หน้าสุดท้าย และช่องระบุเลขหน้าโดยตรง
- Export Item ทุก SKU ในช่วงวันที่เลือกเป็น `.xlsx` สำหรับ VLOOKUP โดยเก็บรหัสเป็นข้อความเพื่อรักษาเลขศูนย์นำหน้า
- Import Mapping จากไฟล์ Export กลับเข้าระบบได้ โดยเพิ่มเฉพาะ SKU ที่ยังไม่มี Mapping เป็นสถานะ `pending`
- เพิ่ม TWD SKU/TWD Description ต่อท้าย Excel ได้แม้ SKU ยังไม่เคยปรากฏใน Fact; Mapping จะถูกเก็บล่วงหน้าและ Export ออกมาในรอบถัดไป
- Import จะไม่แก้ทับ Mapping เดิม รายการขัดแย้งจะแสดงในผลการนำเข้า และรายการใหม่มี Audit Event
- หน้า Performance มีปุ่ม `Unmap`: ตาเปิดและพื้นสีเขียวหมายถึงกำลังแสดงทุก Item; กดแล้วเป็นตาปิดและพื้นสีขาวเหมือน Description ที่ปิดอยู่ โดยจะแสดงเฉพาะ Item ที่มี Mapping (`confirmed`/`pending`)
- Matrix ไม่แสดงคอลัมน์ Mapping; TWD SKU ที่ `unmatched` ใช้สีแดง, ไม่มีลูกศรต่อท้าย และใช้คอลัมน์แบบกระชับสำหรับ SKU, Description, WA Item, Total และ Branch/Date
- ตารางมีแถบเลื่อนแนวนอนทั้งด้านบนและด้านล่าง โดยเลื่อนสัมพันธ์กันสองทาง เพื่อไม่ต้องเลื่อนลงไปท้ายตารางก่อนเปลี่ยน Branch/Date ที่กำลังดู
- พื้นที่ควบคุม, Filter, KPI และหัวข้อเหนือ Matrix ใช้รูปแบบ Compact บน Desktop เพื่อเพิ่มความสูงของพื้นที่ข้อมูลตาราง โดย Mobile ยังใช้ปุ่มขนาดใหญ่สำหรับการสัมผัส
- Matrix ใช้ความกว้างคอลัมน์คงที่เหมือนกันใน View Branch และ Date; กรณี Date มีคอลัมน์น้อยจะไม่ยืด SKU, WA Item, Total หรือวันที่เพื่อให้เต็มหน้าจอ
- ไฟล์ Export เดียวมี Sheet `Item Mapping`, `Branch Mapping` และ `วิธีใช้งาน`
- Branch Mapping เก็บรหัส/ชื่อ TWD และรหัส/ชื่อ WA; Matrix ใช้ชื่อ WA เมื่อ Mapping แล้ว และอนุญาตให้อัปเดตเฉพาะชื่อโดยไม่เปลี่ยนรหัสเดิม
