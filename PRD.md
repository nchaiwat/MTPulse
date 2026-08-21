# เอกสารข้อกำหนดผลิตภัณฑ์ MT Pulse

## วัตถุประสงค์

MT Pulse เป็น Application ภายในสำหรับติดตามยอดขายและสินค้าคงคลังของ Modern Trade ในระดับ SKU, สาขา และวัน ระยะแรกมุ่งที่ข้อมูล Thai Watsadu (TWD) เดือนสิงหาคม 2026 โดยเปลี่ยนขั้นตอนทำงานจาก Excel ขนาดใหญ่ให้เป็นระบบที่ค้นหา กรอง เจาะรายละเอียด และตรวจสอบย้อนหลังได้ง่ายขึ้น โดยยังคงตัวเลขและมุมมองที่ผู้ใช้ต้องดูเป็นประจำ

## ปัญหาที่ต้องแก้

ปัจจุบันผู้ใช้ต้องอ่านตาราง Excel ที่กว้างมากเพื่อตอบคำถามว่า SKU ใดขายได้เท่าไร ที่สาขาใด ในวันใด ทั้งจำนวนชิ้นและยอดเงินรวม การค้นหา กรอง และตรวจสอบข้อมูลทำได้ยาก ขณะที่ Item/Branch Mapping ยังไม่มี Workflow และ Audit Trail ที่ถาวร นอกจากนี้ไฟล์ต้นทางต้องถูกส่งจาก NAS ภายในบริษัทไปยัง VPS อย่างปลอดภัยและตรวจสอบย้อนหลังได้

## ผู้ใช้และสิทธิ์

- **User:** ดูรายงาน Sales/Inventory และยืนยันหรือแก้ Item/Branch Mapping
- **Admin:** ตั้งค่าระบบ ตรวจ Import Batch และแก้ปัญหาคุณภาพข้อมูล
- **Management:** ดูภาพรวมระดับบริหารในระยะถัดไป
- Milestone แรกยังไม่ทำ Authentication และ Authorization แต่จะเตรียมขอบเขตสำหรับเชื่อม Keycloak ผ่าน OIDC ในภายหลัง โดย Keycloak จะเชื่อมกับ AD ของบริษัทแยกต่างหาก

## เป้าหมาย

- ผู้ใช้ดูค่า `SKU × Branch × Day` ได้ตลอด ทั้ง Sales Qty และ Amount
- มี Matrix สองมุมมองที่สลับได้ทันที: `Item × Branch` และ `Item × Day`
- เจาะรายละเอียดจาก Item หรือ Cell ได้โดยไม่ต้องออกจากหน้า Performance
- แสดงรหัสและชื่อ Item ทั้งฝั่ง MT และ Window Asia พร้อม Mapping Status
- ไม่ตัดยอดติดลบ Return หรือ Adjustment
- ตรวจยอดของไฟล์นำเข้ากับต้นทางและป้องกันการนำเข้าซ้ำ
- รันได้เหมือนกันทั้งเครื่อง Local และ Ubuntu VPS ด้วย Container

## สิ่งที่ไม่รวมในขอบเขต

- Production Authentication หรือการตั้งค่า Keycloak ใน Frontend Milestone แรก
- การเชื่อม NAS, Database, SAP หรือ Backend จริงใน Frontend Milestone แรก
- Modern Trade อื่นนอกเหนือจาก TWD ใน Phase 1
- Executive Dashboard สำหรับ Management ใน Phase 1
- การนำ Architecture หรือ Business Logic จาก ESIP เดิมมาใช้โดยอัตโนมัติ
- การจำลองหน้าตา Excel แบบ Pixel-for-pixel

## ขอบเขตงาน

### ต้องมี: Frontend UX Milestone

- หน้าจอภาษาอังกฤษทั้งหมด
- Application Shell แบบ Desktop-first และ Responsive
- หน้า Performance โดยใช้ข้อมูลตัวอย่าง TWD ที่สอดคล้องกับบริบทธุรกิจจริง
- โหมด Sales และ Inventory
- Metric ฝั่ง Sales: Amount และ Qty โดย Amount ของระบบเป็นยอด Ex VAT เสมอ
- Metric ฝั่ง Inventory: Stock On Hand และ Stock On Order
- ตัวสลับ Matrix: By Branch และ By Day
- ชื่อ View ที่แสดงในหน้าจอคือ Branch และ Date
- Toggle ซ่อน/แสดง TWD Description และ WA Description พร้อมกัน เพื่อลดความกว้างของ Matrix
- Filter ตามช่วงวันที่ สาขา Mapping Status และคำค้น SKU/Description
- Sticky Columns: TWD SKU, TWD Description, WA Item, WA Description และ Mapping Status
- คอลัมน์ Total และคอลัมน์สาขาหรือวันตามมุมมองที่เลือก
- Heatmap ที่ยังอ่านตัวเลขจริงได้ และไม่ใช้สีเป็นสัญญาณเพียงอย่างเดียว
- Detail Drawer แสดง SKU ที่เลือก รายละเอียดรายสาขา/รายวัน ทั้งสี่ Metric และ Mapping Context
- แสดงค่าติดลบอย่างชัดเจน
- มี Loading, Empty และ No-result State

### ต้องมี: Backend ของ Phase 1 ในลำดับถัดไป

- On-Premise Upload Agent อ่าน NAS แบบ Read-only และส่งไฟล์ที่เลือกไป VPS ผ่าน Outbound HTTPS
- เก็บไฟล์ชั่วคราว ตรวจ Checksum ประมวลผล และลบทิ้งทั้งกรณีสำเร็จและล้มเหลว
- PostgreSQL สำหรับ Import Batch, Fact, Mapping, Settings และ Audit History
- Data Status และ Timeline ของวันที่ขาดข้อมูล รวมวันเสาร์–อาทิตย์
- Item/Branch Mapping แบบ Effective Date
- Strict Reconciliation และ Duplicate Protection

### ควรมี

- เก็บ Filter ใน URL เพื่อกลับมาดูหรือแชร์มุมมองเดิมภายในองค์กรได้
- ใช้งานตารางและ Drawer ด้วย Keyboard ได้
- ใช้ Virtualization หรือ Server-side Pagination เมื่อเชื่อมข้อมูลจริง
- แยกสถานะ Late File, Pending Mapping, Warning และ Failed Import ชัดเจน

### ทำภายหลัง

- Keycloak/AD Single Sign-on และ Role Enforcement
- Management View และ Modern Trade อื่น
- Notification ที่ไม่ใช่ Email
- Bulk Mapping หลังจากพิสูจน์ Single-item Workflow แล้ว

## Workflow หลัก

### ดู Performance

1. ผู้ใช้เปิดหน้า TWD Performance
2. เลือก Sales หรือ Inventory และ Metric ที่ต้องการ
3. เลือกช่วงวันที่และสลับระหว่าง By Branch กับ By Day
4. กรองหรือค้นหาด้วย SKU, Description, Branch หรือ Mapping Status
5. Matrix แสดง Total และ Dimension ที่เลือก โดยตัวเลขยังอ่านได้ชัดเจน
6. คลิก Item หรือ Cell เพื่อเปิด Detail Drawer และดูค่า `SKU × Branch × Day`

### ยืนยัน Item Mapping

1. รายการที่ยังไม่ยืนยัน Mapping ต้องเห็นได้ชัดใน Report และ Matching Workflow
2. ผู้ใช้ตรวจ Candidate จาก OSCN หรือค้นจาก WA Item Master
3. เลือก WA Item หนึ่งรายการและ Effective Date
4. Mapping มีผลทันที และ Audit Event บันทึกค่าเดิม ค่าใหม่ ผู้แก้ และเวลาที่แก้

### Upload และ Import ไฟล์ TWD

1. On-Premise Agent ตรวจ NAS Path แบบ Read-only ตาม Schedule
2. ระบุไฟล์ที่เข้าเงื่อนไข คำนวณ Checksum และ Upload ผ่าน HTTPS
3. VPS เก็บไฟล์ชั่วคราวและสร้าง Import Batch
4. Importer ตรวจ Column และ Period, นำเข้า Fact แบบ Transaction และ Reconcile ยอด
5. ลบ Temporary File ไม่ว่า Process จะสำเร็จหรือล้มเหลว
6. Batch บันทึกสถานะสุดท้าย Error และ Warning ที่ผู้ดูแลอ่านเข้าใจได้

## กฎธุรกิจ

- ใช้ Period ภายในไฟล์เป็น Data Date เสมอ ส่วน Folder Date และเวลาพบไฟล์เป็น Receipt Metadata
- Source Amount ของ TWD รวม VAT และคำนวณ `Amount Ex VAT = Source Amount / 1.07`
- เก็บ Amount เต็ม Precision ในฐานข้อมูลและปัดเศษเฉพาะตอนแสดงผล
- เก็บแถว Sales ติดลบทั้งหมด
- Checksum เดิมต้องไม่สร้าง Fact ซ้ำ
- Phase 1 กำหนดให้ TWD SKU หนึ่งรหัส Mapping กับ WA Item ได้หนึ่งรายการต่อช่วง Effective Date และห้ามช่วงเวลาซ้อนกัน
- หาก OSCN มีหลาย Candidate ต้องให้ผู้ใช้เลือก และมี Active Mapping ได้ครั้งละหนึ่งรายการ
- Mapping ที่ User ยืนยันมีผลทันที ไม่ต้องรอ Admin
- Expected Lag เริ่มต้นสองวัน และนับความครบถ้วนทุก Calendar Day รวมวันหยุด
- Batch ผ่านเมื่อ Row Count, จำนวน Store/SKU, Source Amount, Ex VAT Amount, Qty, Stock OH และ Stock On Order ตรงกับ Source ทั้งหมด
- ยอมให้ต่างไม่เกิน 0.01 บาทเฉพาะตัวเลขที่ปัดเพื่อแสดงผล ไม่ใช่ค่าที่เก็บ
- MT Pulse ห้ามเปลี่ยนชื่อ ย้าย แก้ หรือลบ Original File บน NAS

## ความต้องการด้านข้อมูล

- Source Fields: Store, Cat, Sub Cat, Brand, SKU, Barcode, Description, Product Type, Sales Amount, Sales Qty, Stock OH, Stock On Order, Last Sold Date และ Last Receive Date
- Description จาก TWD และ Window Asia เป็นภาษาไทย ต้องเก็บและแสดงตาม Source โดยไม่แปลเป็นภาษาอังกฤษ
- Fact Grain คือ Data Date, Branch และ SKU ของ TWD หนึ่งชุด
- เก็บ Source Amount และ Amount Ex VAT แยกกัน
- เก็บ Source Path, File Name, Checksum, เวลา Upload/Process, Counts, Totals, Status, Warnings และ Errors ต่อ Batch
- เก็บประวัติ Item/Branch Mapping พร้อม Effective Date และ Audit Metadata
- Raw File เป็นข้อมูลชั่วคราวและลบหลัง Process ส่วน Structured Facts และ Audit Records ต้องเก็บไว้
- ใช้ยอดวันที่ 16–17 สิงหาคม 2026 ใน `PROJECT_CONTEXT.md` เป็น Reconciliation Fixtures ชุดแรก

## ระบบที่ต้องเชื่อมต่อ

- **On-Premise NAS:** อ่านโดย Upload Agent เท่านั้นและเป็น Read-only
- **VPS Upload API:** Outbound HTTPS พร้อม Machine Credential, Checksum, Idempotency Key, Retry และ Acknowledgement
- **SAP Business One:** OSCN ที่ CardCode ขึ้นต้น `CTW` เป็น Item Mapping Candidate โดยวิธีเชื่อมต่อจริงยังรอตัดสินใจ
- **Branch Master:** ผู้ใช้จะส่งให้ภายหลังและต้องเก็บใน MT Pulse
- **Keycloak:** เชื่อมผ่าน OIDC ภายหลัง ไม่รวม Frontend Milestone แรก

## แนวทาง Architecture

- Frontend: React และ TypeScript สร้างเป็น Static Web Application
- API: Python FastAPI แยกขอบเขต Report, Mapping, Import และ Settings
- Database: PostgreSQL ใช้ Decimal สำหรับยอดเงิน รองรับ Effective Date และ Transactional Import
- Import Processing: Python Worker แยก Process และ Claim งานจากตาราง Queue ใน PostgreSQL โดย Phase 1 ยังไม่ต้องใช้ Distributed Queue
- On-Premise Transfer: Python Agent ทำงานตาม OS Scheduler และเชื่อมออกผ่าน HTTPS เท่านั้น
- Deployment: Docker Images และ Docker Compose เพื่อให้ Local/VPS ใกล้เคียงกัน พร้อม TLS Reverse Proxy บน Ubuntu VPS

## ความเสี่ยงและแนวทางลดความเสี่ยง

- **Matrix กว้างมาก:** ใช้ Sticky Identity Columns, Horizontal Scroll, Virtualization และ Detail Drawer
- **ตีความสีผิด:** แสดงตัวเลขและ Status ที่ไม่พึ่งสีเพียงอย่างเดียว
- **VPS เข้า NAS ไม่ได้:** ใช้ Outbound On-Premise Agent และไม่เปิด Inbound Port เข้าบริษัท
- **Import ซ้ำหรือไม่ครบ:** ใช้ Checksum Idempotency และ Transaction เดียวต่อ Batch
- **ยังไม่มี Branch Master/วิธีเชื่อม SAP:** แยก Adapter และใช้ Fixture จนกว่าจะยืนยัน Source
- **Authentication ยังไม่พร้อม:** เตรียม OIDC Boundary และ Mock Identity โดยไม่ทำ Authorization ก่อนเวลา

## คำถามที่ยังเปิดอยู่

- Operating System, Scheduler และ Service Account ของ On-Premise Agent
- วิธีเข้าถึง OSCN และ WA Item Master ใน Production: Database, API หรือ Scheduled Export
- Branch Master ของ CTW/TWD และ Safe Normalization Rules
- มีกรณีจริงที่ TWD SKU หนึ่งรหัสต้อง Mapping หลาย WA Item พร้อมกันหรือไม่
- VPS Sizing, Domain, TLS, Backup Policy และผู้รับผิดชอบ Operations

## สถานะและลำดับความสำคัญ

Discovery สำหรับ Frontend UX Milestone ได้รับอนุมัติแล้ว ลำดับงานคือ (1) สร้างและตรวจ Frontend MVP ภาษาอังกฤษ (2) ทำ Database และ Import Foundation (3) ทำ On-Premise Upload, Data Status และ Mapping Workflow และ (4) เชื่อม Keycloak ก่อน Production

## Requirement เพิ่มเติม: Sales Monthly Matrix

### Objective และปัญหา

- ให้ User ดูยอดขายราย SKU สรุปเป็นเดือนในรูปแบบเดียวกับ Excel โดยไม่ต้องรวมข้อมูลรายวันด้วยตนเอง
- รองรับข้อมูลหลายปี เช่น `Jan 2025` ถึง `Aug 2026` และต้องเรียงตามปีและเดือนจริงเสมอ

### ผู้ใช้และผลลัพธ์ที่ต้องการ

- User และ Management ใช้มุมมองนี้เพื่อติดตามแนวโน้ม Sales Amount และ Sales Qty ราย SKU
- เมื่อกด `Month` ต้องเห็นทุกเดือนที่มีข้อมูลทันที ไม่ต้องเลือกช่วงเดือนก่อน

### ขอบเขต

- เพิ่ม View `Month` ต่อจาก `Branch` และ `Date` เฉพาะ Mode `Sales`
- Metric ที่รองรับคือ `Amount` และ `Qty`
- `Amount` ของแต่ละเดือนคือผลรวม Amount ของทุกวันที่อยู่ในเดือนนั้นตามกติกา Amount ของระบบ
- `Qty` ของแต่ละเดือนคือผลรวม Sales Qty ของทุกวันที่อยู่ในเดือนนั้น รวม Return และ Adjustment
- ใช้ Search, Branch, Mapping, Description, Unmap, Heatmap และ Pagination ชุดเดิม
- ถ้าเลือก Branch เดียว ให้ยอดรายเดือนรวมเฉพาะ Branch นั้น; ถ้าเลือกทุก Branch ให้รวมทุก Branch
- แสดงคอลัมน์เดือนจากเก่าสุดไปล่าสุด โดยใช้ key `YYYY-MM` สำหรับเรียงและแสดง Label เช่น `Jan 2025`
- แสดงเฉพาะเดือนที่มีข้อมูลนำเข้า และใช้ Horizontal Scroll ด้านบน/ล่างชุดเดิม

### นอกขอบเขต

- Monthly Inventory, Stock On Hand และ Stock On Order
- การเลือกเดือนเริ่มต้นและเดือนสิ้นสุดสำหรับรอบแรก
- Forecast, Comparison, Growth Percentage และกราฟรายเดือน

### Data และ Architecture Direction

- PostgreSQL เป็น Source of Truth และ API ต้องรวมยอดรายเดือนฝั่ง Server เพื่อไม่ส่ง Fact รายวันจำนวนมากมายัง Browser
- API ต้องรองรับการขอข้อมูลแบบ `month` และคืน month key ที่เรียงได้ พร้อม Amount/Qty ที่รวมแล้วต่อ SKU
- เมื่อเลือกทุกวันที่นำเข้าใน Month View ต้องใช้ขอบเขตข้อมูลจริงในฐานข้อมูล ไม่ใช้วันที่ตัวอย่างแบบ hard-code
- ต้องคงพฤติกรรม Branch และ Date เดิมโดยไม่เปลี่ยนผลรวม

### Success Criteria

- ข้อมูล `Jan 2025` ถึง `Aug 2026` แสดงเรียงซ้ายไปขวาถูกต้องครบ 20 เดือนเมื่อมีข้อมูลครบทุกเดือน
- ผลรวมราย SKU/เดือนและ Total ตรงกับ Excel ทั้ง Amount และ Qty รวมถึงค่าติดลบ
- สลับ `Amount`/`Qty`, Filter Branch และเปลี่ยนหน้าได้โดยไม่โหลด Fact รายวันทั้งหมดเข้า Browser
- Automated Tests ครอบคลุมการเรียงเดือนข้ามปี การรวมยอด และการไม่แสดง Month ใน Inventory

### สถานะ

- Requirement ได้รับคำตอบครบแล้ว รออนุมัติแผน Implementation ก่อนเริ่มแก้ Code

## Requirement เพิ่มเติม: Branch by Month และยอดรวมบนหัวตาราง

### Objective

- ทำให้ Matrix ตรงกับวิธีอ่านรายงาน Excel เดิม โดย Branch View สนใจ “เดือน” ไม่ใช่วัน
- แสดงยอดรวมสองระดับทั้ง Amount และ Qty เพื่อให้ตรวจสอบยอดราย SKU, ราย Branch และยอดรวมทั้งเดือนได้ในหน้าจอเดียว

### Core Workflow

- เมื่อเปิด Sales View `Branch` ระบบเลือกเดือนล่าสุดที่มีข้อมูลให้อัตโนมัติ
- User เลือกเดือน เช่น `Jan 2025` แล้วคอลัมน์เป็นแต่ละ Branch
- Cell ของตารางคือยอด `SKU × Branch × Month`
- ยอดบนหัว Branch คือยอด `ทุก SKU × Branch × Month`
- View `Month` รวมทุก Branch; Cell คือยอด `SKU × Month`
- ยอดบนหัว Month คือยอด `ทุก SKU × ทุก Branch × Month`
- คอลัมน์ `Total` ของแต่ละแถวเป็นผลรวมทุกคอลัมน์ที่แสดง และยอดบนหัว `Total` เป็น Grand Total ของข้อมูลตาม Filter

### Business Rules

- กติกาข้างต้นใช้เหมือนกันทั้ง `Amount` และ `Qty` รวม Return/Adjustment ตามเครื่องหมายเดิม
- ยอดบนหัวตารางต้องรวมทุก SKU ที่ตรงกับ Filter ไม่ใช่เฉพาะ SKU ในหน้าปัจจุบันของ Pagination
- Search, Branch, Mapping, Unmap และ Filter อื่นต้องมีผลกับยอดรวมบนหัวตารางด้วย
- Month View แสดงทุกเดือนที่มีข้อมูลเรียงจากเก่าไปใหม่; Branch View แสดงเดือนเดียวที่เลือก
- การปรับชื่อ/โครงสร้าง Branch รอ Requirement เพิ่มเติม และยังใช้ Branch ปัจจุบันไปก่อน

### Success Criteria

- ตัวอย่างอ้างอิง `60406627 × 60923 × Jan 2025` แสดง Amount `25,234` เมื่อข้อมูล Source ตรงกับ Excel
- หัว Branch `60923 × Jan 2025` แสดง Amount `793,913` เมื่อข้อมูล Source ตรงกับ Excel
- `60406627 × Jan 2025` ใน Month View แสดง Amount `430,998` และหัว `Jan 2025` แสดง Grand Total `38,537,785` เมื่อข้อมูล Source ตรงกับ Excel
- ค่า Qty ให้ผลลัพธ์ในโครงสร้างเดียวกัน และผลรวมทุกระดับ Reconcile กับ Excel

### สถานะ

- ดำเนินการแล้วเมื่อ 21 สิงหาคม 2026 และผ่านการตรวจ Backend, Frontend และ Browser QA
