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

## Requirement เพิ่มเติม: Manual Import และ Telegram Notification

### สถานะ

- Product Owner ยืนยันขอบเขต Functional เมื่อ 24 สิงหาคม 2026

### Objective

- ให้ User นำไฟล์ Raw Data ของ TWD วันอื่นเข้าระบบได้เองเพื่อ Reconcile รายงาน
- ใช้หน้า Upload กลางร่วมกันในอนาคต โดย Phase แรก Detect และ Import เฉพาะ TWD
- มี Log ที่อธิบายว่าใครหรือระบบทำอะไร กับไฟล์ใด เมื่อใด และผลเป็นอย่างไร

### Workflow: Manual Upload

1. User เปิด `สถานะข้อมูล > นำเข้าข้อมูล` และเลือกไฟล์ครั้งละหนึ่งไฟล์
2. ระบบ Detect MT จากโครงสร้างไฟล์และ Validate โดยยังไม่บันทึก Fact
3. ระบบแสดง Preview: MT, Period, Filename, checksum, Row, SKU, Branch, Amount, Qty และ Warning
4. User กดยืนยันก่อน Import ทุกครั้ง
5. Backend ตรวจไฟล์และ Duplicate ซ้ำอีกครั้ง แล้วใช้ Import Pipeline เดิมบันทึกแบบ Transaction
6. แสดงผลลัพธ์และ Activity Log ที่อ่านเข้าใจได้

### Business Rules

- checksum เดิมห้าม Import ซ้ำ
- checksum ต่างแต่ MT และ Period เดิมห้าม Import ซ้ำ; Workflow Replace ทำภายหลัง
- Manual Upload ต้องยืนยันก่อน ส่วน On-Premise Agent ในอนาคตนำเข้าอัตโนมัติเมื่อ Validation ผ่าน
- Raw File อยู่ชั่วคราวเฉพาะระหว่าง Preview/Import และต้องถูกลบทั้งกรณีสำเร็จและล้มเหลว
- Original File บน UNC เป็น Read-only และอยู่นอกขอบเขต Manual Upload รอบนี้
- ยังไม่ทำ User Level, On-Premise Agent, MT อื่น หรือ Daily Telegram Summary เชิงรายละเอียด

### Telegram และ System Setting

- ใช้ Telegram Bot หนึ่งตัวและ Group/Chat ID เดียวสำหรับทุก MT
- System Setting รองรับ Bot Token แบบปกปิด, Group/Chat ID และการทดสอบส่งข้อความ
- Manual Import สำเร็จหรือล้มเหลวต้องสร้าง Notification Event
- หาก Telegram ยังไม่ถูกตั้งค่าหรือส่งไม่สำเร็จ Import ต้องไม่ Rollback และ Log ต้องระบุผลการแจ้งเตือน
- Token ห้ามปรากฏใน Log, API Response หรือ Source Control

### Success Criteria

- Preview ไฟล์ TWD จริงได้โดยไม่สร้าง Import Batch หรือ Fact
- Confirm แล้วข้อมูล Period ใหม่ปรากฏในรายงานและยอด Reconcile กับ Preview
- Duplicate ทั้ง checksum และ MT+Period ถูกปฏิเสธโดยไม่สร้าง Fact เพิ่ม
- Log แสดง Preview, Import, Duplicate, Failed และผล Telegram ด้วยข้อความที่ผู้ใช้เข้าใจได้

## System Monitoring — Phase 1

### วัตถุประสงค์

- เพิ่ม `Monitoring` เป็น Main Menu สำหรับตรวจสุขภาพ Application, PostgreSQL และ Data Pipeline โดยไม่ต้องเข้าถึงเครื่อง Server โดยตรง
- โหลดสถานะเมื่อเปิดหน้าและเมื่อผู้ใช้กด `Refresh` เท่านั้น ไม่มี Auto Refresh
- เก็บ Monitoring Snapshot วันละหนึ่งชุดย้อนหลัง 365 วัน เพื่อดูแนวโน้มโดยไม่สร้างภาระระดับนาทีหรือชั่วโมง

### ขอบเขตที่ต้องมี

- Health Cards: API, PostgreSQL, วันที่ข้อมูลล่าสุด, Import ล่าสุด และจำนวน Warning
- Database Detail: จำนวน Fact Records, ขนาด Database/Table/Index, Dead Tuple, Last Vacuum/Analyze และ Connections เทียบกับค่าสูงสุด
- Top 10 Slow Queries จาก `pg_stat_statements`: Query แบบ Normalize และย่อ, Calls, Average Time, Total Time และ Rows
- บันทึก Snapshot หลัง Daily Import สำเร็จ และใช้การเปิด Monitoring ครั้งแรกของวันเป็น Fallback เมื่อวันนั้นไม่มี Import
- การกด Refresh คำนวณสถานะใหม่และ Upsert Snapshot ของวันปัจจุบัน โดยยังคงมีเพียงหนึ่ง Snapshot ต่อวัน
- แสดงประวัติรายวันย้อนหลังไม่เกิน 365 วัน

### กฎสถานะเริ่มต้น

- PostgreSQL ติดต่อไม่ได้เป็น Critical
- Data Date ล่าช้าเกิน Expected Lag สอง Calendar Days เป็น Warning
- Import ล่าสุดล้มเหลวหรือมี Warning ให้สะท้อนในภาพรวม
- Connection Usage ตั้งแต่ 80% เป็น Warning และตั้งแต่ 95% เป็น Critical
- Dead Tuple Ratio ตั้งแต่ 10% เป็น Warning
- `pg_stat_statements` ใช้งานไม่ได้เป็น Warning พร้อมข้อความอธิบาย

### ไม่รวมใน Phase นี้

- Clear Log, VACUUM, REINDEX, Optimize หรือคำสั่ง Maintenance ใด ๆ
- Backup/Restore และการตั้งค่า Retention ของ Backup
- Auto Refresh, Real-time Monitoring และ Snapshot ระดับชั่วโมง
- Physical Disk Free ของ VPS/Database Volume ซึ่งต้องเชื่อม Host Monitoring ตอน Production
- Authentication และสิทธิ์ Admin สำหรับ Monitoring

## Requirement เพิ่มเติม: สินค้าทดลองและตัวเลือกหลาย SKU

### Objective

- รองรับ Item ที่ผู้ใช้เพิ่มผ่าน Excel เพื่อใช้เป็นสินค้าทดลอง โดยแยกจากสถานะ Mapping อย่างชัดเจน
- ให้ผู้ใช้เลือก SKU หลายรายการเพื่อเปรียบเทียบในรายงานได้สะดวก โดยไม่เพิ่มช่องค้นหาซ้ำซ้อน

### Business Rules: สินค้าทดลอง

- `Mapping Status` ยังคงใช้ `confirmed`, `pending` และ `unmatched` ตาม Workflow เดิม
- เพิ่ม `Item Type` เป็น `normal` หรือ `trial` และ `Report Status` เป็น `active` หรือ `inactive`
- ไฟล์ Excel เก่าหรือช่องที่ไม่ระบุค่า ให้ถือเป็น `normal + active`
- Item ทุกประเภทที่เป็น `active` ต้องแสดงและรวมใน KPI, SUM และ Download Excel ตามปกติ
- `trial + active` แสดงพื้นสีเหลืองอ่อนที่ส่วน Item พร้อม Badge `สินค้าทดลอง` โดยไม่เปลี่ยนสี Cell ตัวเลขหรือ Heatmap
- `inactive` ต้องไม่แสดงและไม่รวมยอดทั้งข้อมูลปัจจุบันและย้อนหลัง แต่ห้ามลบ Fact, Mapping หรือ Audit History
- Item ที่ `inactive` ยังต้องอยู่ใน Mapping Export เพื่อให้เปลี่ยนกลับเป็น `active` ผ่าน Excel ได้
- การกำหนดและเปลี่ยน `Item Type`/`Report Status` ทำผ่าน Mapping Excel เท่านั้น และต้องมี Audit Log

### Workflow: เลือกหลาย SKU

- เปลี่ยนช่องค้นหา Item เดิมเป็นตัวเลือกหลาย SKUที่มีช่องค้นหาอยู่ภายใน Dropdown
- ค้นหาได้จาก TWD SKU, TWD Description, WA Item และ WA Description
- รองรับ Checkbox, เลือกทั้งหมดจากผลค้นหา, ล้างการเลือก และปุ่มแสดงผล
- เมื่อยังไม่เลือก ให้หมายถึง SKU ที่ Active ทั้งหมด; เมื่อเลือกแล้วให้แสดงจำนวน เช่น `เลือก 3 SKU`
- การค้นหาภายใน Dropdown ต้องไม่ Refresh รายงานจนกดแสดงผล
- KPI, SUM, Matrix, Pagination, Detail และ Download Excel ต้องใช้ SKU ชุดเดียวกัน
- Item ที่ `inactive` ต้องไม่ปรากฏในตัวเลือก SKU
- เก็บ SKU ที่เลือกไว้ใน Current View เช่นเดียวกับ Filter อื่น และใช้ Virtual Scroll/Server-side Query เพื่อรองรับ SKU จำนวนมาก

### Non-goals

- ไม่เพิ่มหน้าจอแก้ Item Type หรือ Report Status ทีละ Item ในหน้า Setting
- ไม่ใช้สี Cell ใน Excel เป็นข้อมูลสถานะ
- ไม่ลบข้อมูลย้อนหลังของ Item ที่ inactive
- ไม่แก้ Logic Branch, Date/Month, Heatmap หรือ Mapping Status เดิมนอกเหนือจากการใช้ Filter Item Active

## Requirement เพิ่มเติม: FileShare/UNC Connection — Phase 1

### สถานะ

- Discovery ได้ข้อสรุปแล้ว รออนุมัติ Implementation Plan ก่อนเริ่มเขียนโค้ด
- Requirement นี้แทนแนวคิด On-Premise Upload Agent เดิม เพราะ MT Pulse จะติดตั้ง On-Premise และเข้าถึง FileShare ได้โดยตรง

### Objective

- ให้ System Admin กำหนดและทดสอบการเชื่อมต่อ FileShare กลางจากหน้า System Settings
- เตรียม Source Profile ของแต่ละ Modern Trade โดยใช้ Base UNC และ Subfolder ของ MT
- Phase นี้ทำเฉพาะการบันทึกและทดสอบการเชื่อมต่อ ยังไม่ Scan หรือ Import ไฟล์จาก UNC

### Users และ Authorization Direction

- `System Admin`: จัดการ User, AD Setting, FileShare Credential, Base UNC, Telegram, Schedule, Initial Import และ Corrective
- `Data Operator`: ดูรายงาน, Download, Manual Upload, Mapping, Import Log และ Corrective แต่เข้าถึง Secret/System Settings ไม่ได้
- `Viewer`: ดูรายงานและ Download เท่านั้น
- AD ใช้ตรวจ Username/Password เท่านั้น ส่วน User Profile, Active Status และ Role เก็บใน MT Pulse
- MT Pulse ห้ามเก็บ Password ของ AD
- Admin คนแรกจะ Bootstrap จาก `MTPULSE_BOOTSTRAP_ADMIN_USERNAME` ใน `.env.server`
- ระหว่าง Development ใช้ `MTPULSE_AUTH_MODE=development` เพื่อจำลอง System Admin; ห้าม Hard Code User/Password ลง Source Code
- ภายหลังเปลี่ยนเป็น `MTPULSE_AUTH_MODE=ad` โดยคง Authorization Boundary และ Admin APIs เดิม

### FileShare Configuration

- NAS ใช้ Username/Password ชุดเดียวสำหรับทุก MT
- System Admin เป็นผู้กำหนด Base UNC, Domain (ถ้ามี), Username และ Password เพียงจุดเดียว
- ตัวอย่าง Base UNC: `\\WA-NAS-IT03\FileShare-2\SaleOut_RPT`
- แต่ละ MT เก็บเฉพาะ Subfolder เช่น `TWD` หรือ `TA`; ระบบประกอบ Full UNC โดยไม่ให้ User กรอก Credential ซ้ำ
- Password ต้องเข้ารหัสในฐานข้อมูลด้วย Server Encryption Key และ API ห้ามส่ง Secret โดยไม่ผ่านสิทธิ์
- Test/Development เปิดเผย Secret ที่บันทึกแล้วได้เมื่อ Environment Flag อนุญาต; Production ต้องปิดความสามารถนี้
- ปุ่ม `ทดสอบการเชื่อมต่อ` ต้องตรวจ Server/Share, สิทธิ์อ่าน Base UNC และ Subfolder ของแต่ละ MT โดยไม่แก้ไขหรือลบ Source File
- ผลทดสอบต้องแสดงข้อความที่เข้าใจได้, เวลาทดสอบ, MT Folder ที่พบ/ไม่พบ และบันทึก Audit Log โดยไม่เปิดเผย Password

### Manual Upload และ Future Import

- User ทุก MT ใช้หน้า Manual Upload กลางร่วมกัน ไม่แยก User ประจำ MT
- ระบบ Detect MT, Preview และให้ User ยืนยันก่อน Import ทีละไฟล์ตาม Workflow เดิม
- Initial Import, Scheduled Import และการสั่งนำเข้าใหม่จาก UNC เป็นสิทธิ์ System Admin และอยู่นอก Phase 1
- ใน Phase ถัดไปใช้เวลา Schedule กลางหนึ่งเวลาและประมวลผลทุก MT; ป้องกันซ้ำด้วย MT, Data Date และ SHA-256

### Success Criteria

- Admin บันทึก Base UNC และ Credential ได้โดย Password ไม่ปรากฏใน API response ปกติ
- Admin ทดสอบ Base UNC และ TWD Subfolder จาก Ubuntu/Docker ได้ พร้อมผลสำเร็จหรือสาเหตุที่ล้มเหลว
- Data Operator และ Viewer เรียก Admin FileShare APIs หรืออ่าน Secret ไม่ได้เมื่อเปิด AD Authentication
- การ Save/Test สร้าง Audit Log และไม่กระทบ Report, Manual Upload, Import Pipeline หรือ Telegram เดิม
- Backend/Frontend regression tests เดิมผ่านทั้งหมด

### Out of Scope — Phase 1

- Initial Historical Scan/Import
- Daily Scheduled Import และ Retry Worker
- AD Login implementation และหน้าจัดการ User
- การเปลี่ยนหน้า Report, Mapping, Monitoring หรือ Manual Upload เดิม

## Requirement เพิ่มเติม: Existing Application Visual Refresh

### สถานะ

- Product Owner อนุมัติ UI Plan เมื่อ 1 กันยายน 2026
- รอบนี้เป็น Visual Refresh ของระบบเดิมเท่านั้น ยังไม่สร้าง Dashboard ภาพรวม, Dashboard ราย MT, Top SKU, Top Branch หรือ Chart ใหม่

### Objective

- ปรับภาพลักษณ์ MT Pulse ให้เป็น Modern, Clean และ Premium แบบ Internal SaaS/Data Tool
- คง React + Vite และเพิ่ม Tailwind CSS กับ Shadcn/UI foundation แบบ Incremental
- ใช้สีหลัก `#02abff`, Neutral Surface, Soft Shadow และมุมโค้งอย่างพอดี
- ทำให้ Sidebar, Top Bar, Forms, Panels, Tables และ Feedback States ใช้ภาษาภาพเดียวกัน

### Strict TWD Performance Constraint

- หน้า TWD Performance เป็น Operational Data Tool ไม่ใช่ Dashboard
- ห้ามเปลี่ยน Layout, JSX structure, Component hierarchy, Function, State, Event handler, API call, Query parameter, Business Logic และ Data Logic
- ห้ามเปลี่ยน Filter, Search, Branch/Date/Month, Amount/Qty, Inventory, KPI, SUM, Heatmap Logic, Pagination, Page Size, Drawer, Mapping, Import/Export และ Current View
- ห้ามแทน Control เดิมในหน้า TWD ด้วย Shadcn Component
- ปรับได้เฉพาะ Design Token, สี, Font, Border, Radius, Shadow และ Hover/Focus/Loading/Empty/Error presentation
- Matrix ต้องแสดงข้อมูลและคอลัมน์ครบ ใช้ Horizontal Scroll เดิม และห้ามซ่อนหรือยุบข้อมูลเพื่อ Mobile

### Responsive Scope

- รอบนี้ไม่เพิ่ม Responsive Behavior ใหม่และไม่ลบพฤติกรรมเดิมที่มีอยู่
- Dashboard ภาพรวมและ Dashboard ราย MT ที่จะสร้างในอนาคตจึงค่อยออกแบบ Responsive สำหรับ Mobile/Tablet/Desktop
- หน้า Operational อื่นยังคง Desktop-first เพื่อรักษาความชัดเจนของข้อมูลและ Workflow

### App Shell Navigation เพิ่มเติม

- Navigation ต้องอยู่ด้านซ้ายแบบ Vertical ทุกขนาดหน้าจอ และไม่เปลี่ยนเป็นเมนูแนวนอนด้านบน
- Sidebar เปิดแบบเต็มเป็นค่าเริ่มต้นและมีปุ่มย่อ/ขยายที่เห็นชัด
- เมื่อย่อ Sidebar ให้เหลือ Icon Rail กว้างประมาณ 72px เพื่อเพิ่มพื้นที่แสดงผล โดยยังเข้าถึงทุกเมนูได้ด้วย Mouse, Keyboard และ Screen Reader
- การเปลี่ยน Navigation Shell นี้ห้ามกระทบ Layout, Function หรือ Logic ภายในหน้า TWD Performance

### Success Criteria

- หน้าเดิมทุกหน้ามี Visual Language ที่สม่ำเสมอและใช้ Primary `#02abff`
- Function และผลลัพธ์ทั้งหมดก่อน/หลัง Visual Refresh เหมือนเดิม
- Git diff ของ `src/features/performance/*.ts` และ `*.tsx` ต้องว่าง
- Frontend/Backend regression tests, lint และ production build ผ่าน โดยแยกบันทึกปัญหา Baseline เดิมที่อยู่นอกขอบเขต

## TWD Numeric Excel Error Handling

- เซลล์ตัวเลขจากไฟล์ TWD ที่เป็น Excel Error เช่น `#VALUE!` ห้ามถูกตีความเป็น Error Code เชิงตัวเลข
- ระบบไม่นำเซลล์ Error มารวมยอด และต้องแสดงคำเตือนพร้อม Field, Error Type และจำนวนเซลล์
- การแก้ข้อมูลย้อนหลังต้องอ้างอิงไฟล์ต้นทางที่ Checksum และ Data Date ตรงกับ Batch เท่านั้น
- ก่อนแก้ต้องทำ Dry-run, ตรวจ Branch × SKU ครบถ้วน, สำรองฐานข้อมูล และบันทึก Audit Event

## Requirement เพิ่มเติม: Automatic FileShare Import — TWD Phase 1

### Objective

- ให้ System Admin ตั้งเวลา Import วันละ 1 เวลาแยกต่อ Modern Trade ตามเขตเวลา `Asia/Bangkok`
- เพิ่ม `Run ทันที` โดยใช้ Import Pipeline และกฎ Idempotency เดียวกับ Scheduled Run
- Phase แรกทำเฉพาะ TWD และห้ามเปลี่ยน Function/Logic ของหน้า TWD Performance

### Source และ File Discovery

- TWD ใช้โครงสร้าง `TWD\<date-folder>\<file>` และมีไม่เกิน 1 ไฟล์ต่อ Folder วันที่
- รองรับทั้ง `.xls` และ `.xlsx`; Format อื่นให้ข้ามพร้อมบันทึกเหตุผล
- วันที่ชื่อ Folder ไม่ใช่วันที่ข้อมูล ระบบต้องอ่าน Data Date จากเนื้อหาไฟล์เท่านั้น
- Initial Scan ครั้งแรกตรวจทุก Folder เพื่อสร้างทะเบียนไฟล์และเทียบกับ Batch เดิม หลังจากนั้นตรวจเฉพาะไฟล์ใหม่หรือไฟล์ที่ Metadata เปลี่ยน
- การ Scan หรือ Hash ไฟล์ย้อนหลังไม่ถือเป็นการ Import และห้ามสร้าง Fact ซ้ำ

### Idempotency และ Conflict Rules

- checksum เดิมของ MT เดิมให้ข้าม
- Data Date ใหม่และไฟล์ผ่าน Validation ครบจึง Import อัตโนมัติ
- Data Date เดิมแต่ checksum ต่างให้หยุดเฉพาะไฟล์นั้น สถานะ `รอตรวจสอบ`; งานยังประมวลผลไฟล์อื่นต่อและจบแบบมีคำเตือน
- ไฟล์ใหม่ที่มี Reconciliation/Validation Warning ให้หยุดเฉพาะไฟล์และรอ System Admin ตรวจ ห้าม Import พร้อม Warning อัตโนมัติ
- System Admin เลือก `เก็บข้อมูลเดิม` หรือ Preview/ยืนยัน `แทนที่ด้วยไฟล์ใหม่` ผ่าน Corrective Workflow พร้อมเหตุผลและ Audit Log
- หากไฟล์ต้นฉบับถูกย้ายหรือลบ ให้แจ้ง `ไม่พบไฟล์ต้นฉบับ` แต่ห้ามลบข้อมูลที่ Import แล้วออกจาก DB

### Schedule และ Concurrency

- แต่ละ MT มี Schedule Enabled และ Schedule Time ของตนเอง; ปิด Schedule แล้วต้องเก็บเวลาเดิมไว้
- `Run ทันที` ใช้งานได้แม้ Schedule ปิด และต้องมี Confirmation แสดง MT, Path และกฎว่า Import เฉพาะไฟล์ใหม่
- MT เดียวกันห้าม Run ซ้อนกัน; หากกำลังทำงานให้ปฏิเสธ Trigger ซ้ำ แต่ MT อื่นทำงานได้อย่างอิสระ
- หากพลาดเวลาเพราะระบบหยุดและกลับมาภายในวันเดียวกัน ให้ Catch-up 1 ครั้งโดยไม่สร้างงานซ้ำ

### Authorization, Monitoring และ Notification

- เฉพาะ System Admin ตั้งเวลา เปิด/ปิด Schedule, Run ทันที และยืนยัน Replace
- ทุก Run และทุกการตัดสินใจต้องมี Audit Log พร้อม Trigger Type, Actor, เวลา และผลลัพธ์
- Monitoring แสดง Running/Success/Success with warnings/Failed, Last Run, Next Run และจำนวน Found/Imported/Skipped/Pending Review
- Telegram ส่งหนึ่งข้อความสรุปต่อ Run และแจ้ง Error หรือ Pending Review ทันที โดยรายละเอียดเต็มอยู่ใน Monitoring/Audit Log

### Success Criteria

- Initial Scan เทียบข้อมูล TWD เดิม 33 Batch ได้โดยไม่ Import ซ้ำหรือลบข้อมูลเดิม
- Scheduled Run และ Run ทันทีใช้ Pipeline เดียวกันและให้ผล Idempotent
- รองรับ `.xls`/`.xlsx` และใช้ Data Date ภายในไฟล์ ไม่ใช้ชื่อ Folder
- Conflict หรือ Warning ไม่เปลี่ยน Fact เดิมจนกว่า System Admin ยืนยัน
- Restart หรือ Refresh ไม่ทำให้ Schedule, File Registry หรือ Run History สูญหาย
# TWD Sales Dashboard — 1 กันยายน 2026

## เป้าหมาย

- เพิ่มหน้า `แดชบอร์ด > ไทวัสดุ` สำหรับอ่านภาพรวมยอดขาย Ex.VAT และ Qty โดยไม่เปลี่ยนหน้า `รายงาน > ไทวัสดุ` เดิม
- รองรับการเปรียบเทียบปีปัจจุบันกับปีก่อนในช่วง YTD, H1, H2 และปีเต็ม
- แสดง Monthly trend, ตารางรายเดือน, Top 10 Branch และ Top 15 SKU พร้อมตัวเลขจริงและ YoY
- ใช้ Monthly Sales Summary เป็นแหล่งข้อมูลหลักเพื่อรองรับฐานข้อมูลขนาดใหญ่

## ข้อกำหนด UI/UX

- ใช้ Operations Dashboard ที่อ่านง่าย สีหลัก `#02ABFF`, Navy/Slate และ Soft semantic colors
- Desktop แสดง Chart และ Table เป็นคู่; Tablet/Mobile เรียงลงด้านล่างและ Table เลื่อนแนวนอนได้
- มี Loading, Empty, Error/Retry, Hover, Focus และข้อความระบุวันที่ข้อมูลล่าสุด/ความครบถ้วน
- มีปุ่มเปิดรายงานไทวัสดุเดิม โดยไม่เปลี่ยน Filter, Matrix, Function หรือ Logic ของรายงานเดิม

## Non-goals

- ไม่แก้ Component, Layout, Function, Logic หรือ API contract ของหน้า TWD Performance เดิม
- ไม่รวม Inventory ใน Dashboard ยอดขายรอบแรก และไม่สร้าง Dashboard ของ MT อื่นในรอบนี้


## Requirement เพิ่มเติม: TWD Import Progress และนำเข้าจาก FileShare โดยตรง — 3 กันยายน 2026

### Objective และปัญหา

- ลดเวลารอและความไม่แน่ใจหลังผู้ใช้เลือกไฟล์ โดยแสดงว่าเวลาถูกใช้กับการ Upload, อ่าน Excel หรือการตรวจฐานข้อมูล
- ให้ผู้ใช้เลือกไฟล์ TWD ที่ Initial Scan ระบุว่า `พร้อมนำเข้า` แล้วนำเข้าจาก FileShare โดยตรง โดยไม่ต้อง Download ผ่านเครื่องผู้ใช้แล้ว Upload กลับเข้า Server
- ใช้ Importer, Reconciliation, Duplicate Protection, SKU Interest และ Audit/Notification rules ชุดเดิมทุกประการ

### Users และสิทธิ์

- `System Admin` และ `Data Operator` ใช้ Manual Upload และ FileShare Import ได้
- `Viewer` ดูรายงานและ Download ได้เท่านั้น
- Browser ห้ามได้รับ FileShare Username, Password หรือ Full UNC Path
- ระหว่างที่ `MTPULSE_AUTH_MODE=development` ยังไม่มี Role Enforcement จริง แต่ API ต้องวางขอบเขตไว้ให้บังคับ Role เดิมได้เมื่อเปิด AD Authentication

### Workflow: Manual Upload

1. ผู้ใช้เลือกไฟล์ TWD `.xls` หรือ `.xlsx` จากเครื่อง
2. ระบบเริ่ม Preview อัตโนมัติและแสดง Upload Percentage ตามจำนวน Byte จริง
3. เมื่อ Upload ครบ เปลี่ยนสถานะเป็น `กำลังอ่านและตรวจสอบไฟล์`
4. Backend อ่าน Excel, Reconcile และตรวจข้อมูลซ้ำ แล้วคืน Preview พร้อมเวลาที่ใช้แต่ละช่วง
5. ผู้ใช้ตรวจ Summary/Warning แล้วกด `ยืนยันนำเข้าข้อมูล`
6. ขั้น Confirm ต้อง Upload และตรวจ Checksum ซ้ำตามกฎเดิม พร้อมแสดง Progress เช่นเดียวกัน

### Workflow: FileShare Import

1. ผู้ใช้สลับแหล่งข้อมูลเป็น `จาก FileShare`
2. ระบบอ่านเฉพาะทะเบียน `source_files` ของ TWD ที่มีสถานะ `ready` โดยไม่ Scan NAS ซ้ำ และเรียง Data Date ล่าสุดก่อน
3. รายการแสดง Data Date, Filename, Size และเวลาที่พบ โดยไม่เปิดเผย Full UNC Path
4. ผู้ใช้เลือกหนึ่งไฟล์ ระบบ Download จาก NAS บน Server, Parse และแสดง Preview ชุดเดียวกับ Manual Upload
5. ผู้ใช้กดยืนยัน ระบบ Download ไฟล์ซ้ำ ตรวจ Expected Checksum และนำเข้าด้วย Transaction/Business Rules ชุดเดิม
6. เมื่อสำเร็จ `source_files.status` เปลี่ยนเป็น `imported` และเชื่อม `imported_batch_id`; รายการพร้อมนำเข้าถูก Refresh

### Business Rules และข้อจำกัด

- ใช้ Data Date ภายในไฟล์เสมอ ไม่ใช้วันที่ Folder หรือเวลาพบไฟล์
- Original File บน NAS เป็น Read-only ห้ามแก้ชื่อ ย้าย เขียน หรือลบ
- FileShare Import เลือกได้เฉพาะ Source File ของ TWD ที่สถานะ `ready`; ไฟล์ Warning/Conflict ต้องใช้ Corrective Workflow เดิม
- Preview เป็น Read-only และห้ามสร้าง Fact
- Confirm ต้องอ่านไฟล์ใหม่และตรวจ Checksum เทียบ Preview; หากไฟล์เปลี่ยนหรือหาย ให้หยุดโดยไม่แก้ข้อมูลเดิมและบอกให้ Run Scan ใหม่
- Manual Upload และ FileShare Import ต้องป้องกัน Checksum/Data Date ซ้ำเหมือนกัน
- UI แสดง Upload Percentage จริงเฉพาะการส่งไฟล์จาก Browser; ระหว่าง Server Parse แสดงสถานะกำลังประมวลผลและแสดง Timing Breakdown เมื่อ Backend ตอบกลับ
- ห้ามเปลี่ยน Component, Layout, Function, Query หรือ Business Logic ของหน้า TWD Performance

### UI Direction

- ภายในหน้า `นำเข้าข้อมูล` ใช้ Source Switch สองค่า: `จากเครื่อง` และ `จาก FileShare`
- ใช้ Compact Pipeline Strip เป็นจุดจดจำ: `ส่ง/อ่านไฟล์ → ตรวจสอบ → ยืนยัน` สีหลัก `#02ABFF` และ Soft semantic states
- FileShare Ready List เป็น Operations Ledger ขนาดกะทัดรัด ไม่เพิ่ม Card Grid และรองรับ Loading, Empty, Error/Retry, Hover, Focus และ Keyboard
- Preview Summary เดิมใช้ร่วมกันทั้งสองแหล่งข้อมูล เพื่อให้ผู้ใช้ตรวจตัวเลขแบบเดียวกัน

### Success Criteria

- ไฟล์จำลองขนาด 5–6 MB จาก Local Disk แสดง Upload Percentage และเปลี่ยน Phase ถูกต้อง
- Preview response แสดงเวลาที่ใช้ Upload read, FileShare download, Excel parse และ Duplicate check ตามแหล่งข้อมูล
- Ready List ไม่ทำ SMB Scan และไม่คืน Credential/Full UNC
- Preview จาก FileShare ไม่สร้าง Batch/Fact; Confirm สำเร็จสร้างเพียงหนึ่ง Batch และอัปเดต Source File เดิม
- ไฟล์เปลี่ยน, หาย, ซ้ำ, Warning หรือ Conflict ไม่ทำให้ข้อมูลเดิมเปลี่ยน
- Manual Upload เดิม, Automatic Import, Corrective, Telegram และ TWD Performance regression tests ผ่าน


## Requirement เพิ่มเติม: TWD View Date Performance — 3 กันยายน 2026

### Objective

- ลดเวลาโหลด `รายงาน > TWD` สำหรับ `Mode Sales / Metric Amount / View Date` ช่วงข้อมูลทั้งหมด จาก baseline 8.09–8.71 วินาที ให้เหลือไม่เกิน 2 วินาทีบน Test Server เมื่อไม่มี Branch/SKU/Search filter
- คง Layout, Interaction, API response contract, ตัวเลข Summary/Column Total/Point และกฎ Mapping เดิมทุกประการ
- ไม่แก้หรือลบ `sales_inventory_facts`; ตาราง Fact ยังคงเป็น Source of Truth

### Business Rules

- เพิ่ม Daily Summary ระดับ `Modern Trade × Data Date × SKU` สำหรับ Amount, Sales Qty, Stock On Hand และ Stock On Order โดยรวมเฉพาะสาขาที่อยู่ใน Active Branch Mapping ณ วันที่ข้อมูลล่าสุด
- ใช้ Daily Summary เฉพาะ `grain=day_total` ใน safe fast path ที่ไม่มี Date/Branch/SKU/Search/Mapping filter; กรณีอื่นใช้ Fact query เดิม
- ใช้ fast path เมื่อ `show_unmatched_branches=false`; หากผู้ใช้เปิดแสดงสาขาที่ยังไม่ Mapping ให้ fallback ไป Fact query เดิม
- Import และ Corrective Replace ต้อง refresh Daily Summary ของวันที่นั้นใน transaction เดียวกับ Fact และ Monthly Summary
- เมื่อ Branch Mapping ถูกเพิ่มหรือแก้ ระบบต้อง rebuild Daily Summary ใน transaction เดียวกันเพื่อไม่ให้ข้อมูล stale
- Migration ต้อง backfill จาก Fact เดิมและมี downgrade ที่ลบเฉพาะ Daily Summary table
- เปิด Gzip สำหรับ JSON เป็น optimization เสริม แต่ห้ามใช้แทนการแก้ Query

### Measured Baseline และ Acceptance Criteria

- Baseline Test Server: 4,512,804 facts, API response 5,584,255 bytes, TTFB 7.96–8.71 วินาที
- Temporary benchmark: Daily aggregate 109,496 rows; main query 62.8 ms และ daily totals 20.4 ms
- Response ใหม่ต้องเท่ากับ legacy path สำหรับ `items`, `points`, `dates`, `columnTotals`, `summary`, `branches` และ `meta`
- Branch/SKU/Date/Search/Mapping filter และ Inventory/Month/Branch views ต้องยังใช้ผลลัพธ์เดิม
- Full backend/frontend regression, Ruff, ESLint และ production build ต้องผ่านก่อน deploy

## Requirement เพิ่มเติม: Event-scoped Import Notification และ Daily Technical Health — 5 กันยายน 2026

### Objective

- ให้ Telegram ของ Automatic Import สรุปเฉพาะเหตุการณ์ที่เกิดขึ้นใหม่ใน Run นั้น ไม่ส่ง Warning/Failed เก่าซ้ำจาก File Registry ทั้งหมด
- ส่ง Technical Health Report ทุกวันตามเวลาที่ System Admin กำหนด ค่าเริ่มต้น `07:00` เขตเวลา `Asia/Bangkok` แม้ระบบอยู่ในสถานะปกติ
- แจ้ง Critical ระหว่างวันทันที ป้องกันข้อความซ้ำด้วย Cooldown 60 นาทีต่อเหตุ และส่ง Recovery ทันทีเมื่อสถานะกลับสู่ปกติ
- ไม่ทำ External Watchdog; หาก Daily Health Report ไม่มาตามเวลา System Admin จะตรวจสอบ Server ด้วยตนเอง

### Import Notification Rules

- Run History และ Monitoring ยังคงเก็บ Found/Imported/Skipped/Pending/Failed ของการสแกนทั้งหมดเพื่อ Audit และวิเคราะห์ย้อนหลัง
- Telegram ต่อ Run ต้องนับเฉพาะไฟล์ที่ใหม่ เปลี่ยนแปลง หาย หรือได้รับการประมวลผลใหม่ใน Run ปัจจุบัน
- ไฟล์ที่ไม่เปลี่ยนแปลงต้องไม่ทำให้ Warning/Failed เก่าถูกแจ้งซ้ำ และไม่ทำให้หัวข้อรอบใหม่เป็น `สำเร็จพร้อมคำเตือน`
- หากไม่มี Event ใหม่ ให้ส่งสรุปสั้นว่า `ไม่พบไฟล์ใหม่หรือการเปลี่ยนแปลง` พร้อม MT, Trigger, Mode และเวลาที่จบ
- Pending Review หรือ Failed ที่เกิดใหม่ต้องแสดงเฉพาะจำนวนและรายการสำคัญของ Run นั้น รายละเอียดเต็มยังอยู่ใน Monitoring/Audit Log

### Daily Technical Health Scope

- Host/Container: CPU load, RAM used/free, Disk used/free, Uptime และสถานะ API/Worker ที่ระบบตรวจได้จาก Runtime
- PostgreSQL: Database/Table/Index size, Connections, Dead tuples, Vacuum/Analyze และ Slow queries
- Data Pipeline: Worker heartbeat, Queue/Running Run, Run ล่าสุด, วันที่ข้อมูลล่าสุด และ Warning ที่ยังไม่ Resolve
- Daily Report แสดงค่าปัจจุบัน สถานะ `ปกติ/เฝ้าระวัง/วิกฤต` และคำแนะนำเชิงปฏิบัติ เช่น เตรียมเพิ่ม Disk/RAM หรือตรวจ Query
- ข้อจำกัดต้องสื่อชัดเจน: Server ที่ดับหรือ Network ขาดไม่สามารถส่ง Telegram จากตัวเองได้; การไม่พบข้อความประจำวันคือสัญญาณให้ Admin ตรวจสอบเอง

### Default Policy และ Admin Controls

- ค่าเริ่มต้น: Daily Report `07:00`, evaluation ทุก 5 นาที, Cooldown Critical 60 นาที และ Recovery enabled
- ค่าเริ่มต้น Threshold: CPU Warning/Critical `80%/95%`, RAM `80%/90%`, Disk `80%/90%`, PostgreSQL Connections `80%/95%`, Dead tuples `10%/20%`
- System Admin ปรับ Daily time, เปิด/ปิด Daily/Critical/Recovery, Cooldown และ Threshold แต่ละ Metric ได้จาก System Settings
- Validation ต้องบังคับ `Warning < Critical`, ค่าเปอร์เซ็นต์อยู่ในช่วงที่ถูกต้อง และห้ามค่าที่ไม่สมเหตุผลถูกบันทึก
- ใช้ปุ่ม `บันทึกการตั้งค่าระบบ` ปุ่มเดียว โดยบันทึกเฉพาะส่วนที่เปลี่ยนและสร้าง Audit Event โดยไม่เปิดเผย Secret

### Protected Boundaries

- ห้ามเปลี่ยน Parser, Reconciliation, Duplicate Protection, Import transaction, Fact/Batch data และ Function/Logic ของหน้า TWD Performance
- การแยก Event Notification ห้ามลบหรือแก้สถานะเก่าใน Source File Registry; เปลี่ยนเฉพาะวิธีจำแนก Event ของ Run และข้อความแจ้งเตือน
- งาน Visual redesign เต็มระบบด้วย Antigravity แยกเป็น Phase ภายหลังใน branch/worktree เฉพาะ และต้องผ่าน Protected File Rules, diff review, regression tests และ Browser QA ก่อน merge

### Success Criteria

- Run ที่ไม่มีไฟล์เปลี่ยนส่งข้อความ `ไม่พบไฟล์ใหม่หรือการเปลี่ยนแปลง` และไม่ยก Warning/Failed เก่ามาเป็น Event ใหม่
- Run ที่มีไฟล์ใหม่หนึ่งไฟล์สรุปเฉพาะผลของไฟล์นั้น ขณะที่ Run History ยังตรวจสอบยอดสแกนทั้งหมดได้
- Daily Report ถูกส่งหนึ่งครั้งต่อวันตามเวลาที่ตั้งแม้ Healthy และไม่ส่งซ้ำหลัง Worker restart ในวันเดียวกัน
- Critical เหตุเดิมแจ้งไม่เกินหนึ่งครั้งต่อ 60 นาที และ Recovery ถูกส่งหนึ่งครั้งเมื่อกลับสู่ปกติ
- System Settings โหลดค่าที่บันทึกไว้หลัง Refresh/Restart และแสดง Loading, Empty, Error, Validation และ Save feedback ชัดเจน
- Full backend/frontend regression, Ruff, ESLint, production build และ Migration rehearsal ผ่านก่อน deploy

## Requirement เพิ่มเติม: Manual Health Check และ Single-SKU Historical Backfill — 7 กันยายน 2026

### Objective

- ให้ System Admin กดตรวจ Technical Health และส่ง Telegram ได้ทันทีโดยไม่ต้องรอ Daily Schedule
- ให้ User เพิ่ม/Map SKU ที่สนใจภายหลัง แล้วเติมข้อมูลย้อนหลังเฉพาะ SKU นั้นตั้งแต่วันที่เลือกหรือไฟล์แรกที่พบ โดยไม่ Import SKU อื่นซ้ำและไม่แก้ Fact ที่มีอยู่แล้ว
- แยกงาน Functional Phase นี้ออกจาก Antigravity Visual-only Phase เพื่อรักษา Import, Mapping และ TWD Performance logic เดิม

### Manual Technical Health Check

- หน้า `การตั้งค่า > การตั้งค่าระบบ > Technical Health` มีปุ่ม `ตรวจสอบและส่งทันที`
- เมื่อกด ระบบต้องเก็บ CPU, RAM, Disk, PostgreSQL และ Worker heartbeat ใหม่ ณ เวลานั้น แล้วส่ง Telegram สรุปหนึ่งข้อความทั้งกรณี Healthy, Warning และ Critical
- การตรวจ Manual ต้องไม่เปลี่ยน `last daily sent`, Daily Schedule, Critical alert state หรือ Critical cooldown
- UI ต้องมี loading/disabled ระหว่างทำงาน และแสดงเวลาตรวจ, สถานะส่ง และข้อความผิดพลาดโดยไม่เปิดเผย Secret
- ทุกครั้งที่กดต้องสร้าง Audit Event แยกจาก Daily/Critical/Recovery event
- ใช้ Telegram Bot/Token เดิมตามการตั้งค่าปัจจุบัน; Phase นี้ไม่รวมการ Rotate Token หรือเปลี่ยน HTTP logging ตามคำสั่ง Product Owner

### Single-SKU Backfill Eligibility

- Phase แรกทำ Backfill ได้ครั้งละหนึ่ง SKU และเฉพาะ TWD
- SKU ต้องมี Item Mapping สถานะ `confirmed` และ `report_status=active` ก่อนเริ่ม Backfill
- เมื่อ Import Mapping แบบ `confirmed + active` สำหรับ SKU ที่ Pending/Ignored ให้ถือเป็นการ Accept โดยอัตโนมัติ เปลี่ยน SKU Interest เป็น `active` และสร้าง Audit Event
- Mapping ต้องมีผลย้อนหลังตั้งแต่วันเริ่ม Backfill เพื่อให้ข้อมูลแสดงในรายงานตั้งแต่วันนั้น
- หาก Mapping effective date ปัจจุบันอยู่หลังวันเริ่ม Backfill ระบบต้อง Preview การเปลี่ยน effective date และให้ User ยืนยันพร้อม Backfill

### Backfill Source และ Date Rules

- ใช้ Source File Registry เป็นรายการไฟล์อ้างอิงเพื่อไม่ Recursive Scan FileShare ใหม่ทุกครั้ง และแสดงเวลาที่ Registry อัปเดตล่าสุด
- มี action `อัปเดตรายการไฟล์` ให้ User สั่ง Refresh Registry ก่อน Preview ได้เมื่อจำเป็น โดยยังไม่ Import Fact
- User เลือกวันเริ่มได้สองแบบ: `ตั้งแต่ไฟล์แรกที่ระบบพบ` หรือ `เลือกวันที่เริ่มเอง`; วันสิ้นสุดใช้วันที่ข้อมูลล่าสุดอัตโนมัติ
- ยึดวันที่ภายในไฟล์เป็น Data Date ตาม TWD rule เดิม ไม่ใช้ชื่อ Folder เป็นวันที่ข้อมูล
- Backfill เติมเฉพาะ Data Date ที่มี Import Batch ปกติอยู่แล้ว; วันที่มีไฟล์แต่ยังไม่มี Batch ต้องข้ามเป็น `รอ Import ข้อมูลของวันนั้นก่อน` เพื่อไม่สร้าง Partial Batch ที่ขวาง Normal Import
- วันที่ไม่พบไฟล์, อ่านไม่ได้, ไฟล์ขัดแย้ง หรือไม่มี Batch ให้ข้ามเฉพาะวันนั้นและประมวลผลวันอื่นต่อ

### Data Integrity และ Idempotency

- สำหรับ SKU เป้าหมายและแต่ละ Data Date ให้ตรวจ Fact ที่มีอยู่ก่อน; หากมี Fact อย่างน้อยหนึ่ง Branch อยู่แล้ว ให้ถือว่าวันนั้นมีข้อมูลและข้ามทั้งวัน ห้ามเติมบาง Branch โดยอัตโนมัติ
- Backfill ห้ามลบ แก้ไข หรือแทนที่ Fact เดิม และห้ามเปลี่ยน Batch summary/checksum/source metadata
- อ่านไฟล์ผ่าน temporary copy ตามกติกาเดิมและเลือกเฉพาะแถว SKU เป้าหมายก่อน Insert
- Fact ใหม่ต้องผูกกับ Import Batch เดิมของ Data Date นั้น และยังอยู่ภายใต้ unique constraint เดิม
- หลังแต่ละวันที่ Insert สำเร็จ ให้ Refresh Daily SKU Summary และ Monthly Sales Summary เฉพาะ MT/SKU/วันที่หรือเดือนที่ได้รับผลกระทบ
- การ Retry/Resume ต้องตรวจข้อมูลซ้ำอีกครั้ง ทำให้ Run ปลอดภัยแบบ idempotent

### Backfill Workflow และ Status

1. User เลือก SKU ที่ Map แล้วใน `การตั้งค่า > ไทวัสดุ > Item Mapping`
2. เลือกช่วงเริ่มและกด Preview
3. Preview แสดง Registry freshness, ช่วงวันที่, จำนวนวันที่พร้อมเพิ่ม, มีข้อมูลแล้ว, ไม่มี Batch, ไม่พบไฟล์, อ่านไม่ได้ และขัดแย้ง
4. User ยืนยันก่อนสร้าง Backfill Run
5. Worker ทำงานทีละไฟล์และแสดง Progress/Current date/Counts ชัดเจน
6. User กด `หยุดหลังจบไฟล์ปัจจุบัน` ได้ ข้อมูลที่ commit สำเร็จแล้วคงอยู่ และ Run สามารถ Resume เฉพาะวันที่เหลือ
7. เมื่อจบ ส่ง Telegram หนึ่งข้อความเฉพาะผลของ Run นั้น รายละเอียดรายวันอยู่ใน Monitoring/Audit

### Concurrency และ Failure Safety

- TWD มี Automatic Import หรือ SKU Backfill ทำงานได้ครั้งละหนึ่ง Run; งานใหม่เข้าคิวและห้ามประมวลผลซ้อนกัน
- Commit แยกต่อ Data Date เพื่อให้หยุด/ล้มเหลวแล้วไม่สูญเสียวันที่ที่ทำสำเร็จ
- Failure ของไฟล์หนึ่งวันไม่ rollback วันที่ก่อนหน้าและไม่หยุดวันอื่น
- Preview เป็น read-only และยังไม่สร้าง Run; หลังยืนยัน Status ขั้นต่ำคือ `queued`, `running`, `stop_requested`, `stopped`, `completed`, `completed_with_warnings`, `failed`
- Full result ต้องเก็บ Run ID, SKU, requested range, effective range, actor, timestamps, counts และ per-date outcome โดยไม่เก็บ Credential/UNC Secret ในข้อความ User-facing

### UI Plan

- Technical Health: เพิ่มปุ่ม Secondary action ที่ header ของ section เดิม พร้อม last manual check result แบบ inline ไม่เพิ่มหน้าใหม่
- Item Mapping: เพิ่ม section `ดึงข้อมูลย้อนหลังเฉพาะ SKU` ใต้ Mapping exchange ใช้ Search/Select SKU, segmented start option, date input, Preview summary และ Confirm dialog
- Progress ใช้ Operations Ledger แบบ compact พร้อม progress bar, current file/date, counts และปุ่มหยุดที่ไม่ทำลายข้อมูล
- Monitoring เพิ่มตาราง Backfill Run ล่าสุดและรายการวันที่ต้องตรวจสอบ โดยไม่เปลี่ยน Layout/Logic ของ TWD Performance report
- Loading, Empty, Error, Disabled, Confirmation และ Resume states ต้องครบ; สีหลัก `#02abff` และ semantic soft tones ตาม Design System เดิม

### Antigravity Visual-only Phase

- ทำหลัง Functional Phase นี้ Deploy และผ่าน Regression แล้วเท่านั้น
- ใช้ isolated Git worktree/branch และ Workspace Rules แบบ Always On ใน `.agents/rules`
- Antigravity ต้องส่ง Implementation Plan และ Mockup/Screenshot ให้ User อนุมัติก่อนแก้ Code
- File allowlist จำกัดเฉพาะ frontend presentation/CSS/design tokens ที่อนุมัติ; ห้ามแก้ `backend/**`, migrations, API clients/contracts, types, state, handlers, tests เชิง behavior และ `src/features/performance/**`
- ก่อน merge ต้องตรวจ diff, interaction parity, browser walkthrough, responsive widths, keyboard/focus และ full regression; protected file เปลี่ยนให้ Reject change set

### Success Criteria

- Manual Check ส่งค่าที่ตรวจใหม่ทันทีและไม่ทำให้ Daily message หายหรือ Critical cooldown เปลี่ยน
- Backfill หนึ่ง SKU เติมเฉพาะวันที่ไม่มี Fact และมี Import Batch เดิม ข้อมูลเดิมทุก SKU/Branch/Batch ไม่เปลี่ยน
- วันมีปัญหาถูกข้ามพร้อมเหตุผล งานวันอื่นเดินต่อ และ Resume ไม่สร้างข้อมูลซ้ำ
- Mapping ใหม่แบบ confirmed/active เปิด SKU Interest และมีผลย้อนหลังจากวันเริ่มที่ User ยืนยัน
- Telegram Backfill มีหนึ่งข้อความต่อ Run และไม่รวม Event เก่า
- Full backend/frontend regression, Ruff, ESLint, production build, migration rehearsal และ Server smoke test ผ่านก่อนปิดงาน

## Requirement เพิ่มเติม: Shared HP/MH FileShare Import และ Dashboard — 7 กันยายน 2026

### Objective และ Source Contract

- เพิ่ม Modern Trade `HP` (HomePro) และ `MH` (MegaHome) เป็นคนละ MT และมี Dashboard แยก โดยอิง Layout, Metric, Mapping และ Interaction ของ TWD
- HP/MH ใช้ Shared Source Profile เดียว (`HP_MH`) ซึ่งมี Base UNC/Subfolder/Schedule/Run เดียว และประมวลผลพร้อมกัน
- ในแต่ละ Data Date ต้องพบ ZIP คู่กันหนึ่งชุด: `InventoryData` และ `SalesData`; อ่าน CSV ภายใน ZIP และยึดวันที่ภายในไฟล์เป็น Data Date ไม่ใช้วันที่ Folder/ชื่อไฟล์
- แยกข้อมูล HP ด้วย Branch prefix `S` และ MH ด้วย prefix `M`; Branch อื่นเก็บเป็น source diagnostic แต่ไม่ Import เข้า HP/MH
- Inventory และ Sales ภายในคู่ต้องมี Data Date เดียวกัน หากขาด เสีย หรือวันที่ไม่ตรง ให้วันนั้นล้มเหลวทั้งคู่

### Atomicity, Duplicate และ Corrected Files

- หนึ่ง Data Date เป็น transaction ร่วมของ HP/MH: สำเร็จทั้งคู่จึง Commit; หากฝั่งใดผิดพลาดให้ Rollback ทั้งคู่และแสดง diagnostic แยก MT
- Initial Scan เดินหน้าทีละวัน วันที่เสียถูก Skip/Failed โดยไม่ Rollback วันที่สำเร็จ และสามารถ Retry เฉพาะวันที่ได้
- หากมีหลายไฟล์ชนิดเดียวกันในวันเดียว ให้เลือกไฟล์ timestamp ล่าสุดตามชื่อและทำเครื่องหมายชุดเก่า `superseded`
- ใช้ Business Fingerprint ที่ไม่รวมชื่อไฟล์เพื่อตรวจซ้ำ: เนื้อหาสำคัญเหมือนเดิมให้ Skip; เนื้อหาเปลี่ยนให้ Replace ข้อมูลวันนั้นของทั้ง HP/MH แบบ Atomic พร้อม Audit/Reimport history
- Schedule และ Run ทันทีเป็น Incremental โดยตรวจวันใหม่ วันล้มเหลว และไฟล์ที่เปลี่ยนใน 7 วันล่าสุด; Initial Scan อ่านทั้งหมด และ Re-scan ระบุช่วงวันที่ได้

### SKU, Mapping และ Metrics

- เริ่มต้นด้วย Interest SKU 77 รายการต่อ MT จาก KPI Manual แต่สถานะ Accept/Ignore แยก HP และ MH
- แจ้ง SKU ใหม่จาก Sale Out เท่านั้น; Inventory-only SKU นอก Interest ให้ตรวจพบแต่ไม่แจ้งซ้ำทุกวัน
- เมื่อ Accept SKU ใหม่ ให้ติดตามทั้ง Sales และ Inventory ของ MT นั้น และรองรับ Historical Backfill ภายหลัง
- Branch ใหม่ไม่ Block Import; ใช้ source branch code/name และสถานะ `รอ Mapping`
- Sales เก็บ Gross และ Ex.VAT โดยใช้กติกา VAT เดียวกับ TWD และรักษา Return/ค่าติดลบ
- Inventory รองรับ Stock On Hand Qty และ `Stock Value (Source)` โดยไม่หาร VAT; ไม่แสดง Stock On Order เพราะ Source ไม่มี Metric นี้
- Inventory เก็บแบบ Sparse เฉพาะ Qty หรือ Amount ที่ไม่เป็นศูนย์ พร้อม Coverage Metadata เพื่อแยกศูนย์จริงออกจากไม่มีข้อมูล

### UI, Status และ Notification

- Navigation มี Dashboard `HomePro (HP)` และ `MegaHome (MH)` แยกจาก TWD
- Navigation ส่วน `รายงาน` ต้องมี `HomePro (HP)` และ `MegaHome (MH)` แยกกันก่อนเริ่มสร้าง Dashboard ภาพรวมทุก MT
- หน้ารายงาน HP/MH ใช้โครงสร้าง Filter, Sales/Inventory Mode, Branch/Date View, Matrix, Export และ Interaction เดียวกับรายงาน TWD โดยรับ Modern Trade เป็น parameter และไม่เปลี่ยน Logic ของ TWD
- Mapping Metric ต้องแยกชื่อกลางของระบบออกจากชื่อคอลัมน์ต้นทาง เพื่อรองรับการเปลี่ยนหรือเพิ่ม Source field ภายหลังโดยไม่ต้องเปลี่ยนข้อมูล Fact เดิม
- สำหรับ Source ปัจจุบันของ HP/MH: Sales `QTY` = Sales Qty, Sales `VALUE` = Gross Sales และคำนวณ Ex.VAT ตาม VAT policy; Inventory `QTY` = Stock On Hand และ Inventory `AMT` = `Stock Value (Source)`
- Inventory ของ HP/MH แสดง `Stock On Hand` และ `Stock Value (Source)`; ไม่แสดงหรือสร้างค่า `Stock On Order` เป็นศูนย์ เพราะ Source ปัจจุบันไม่มีข้อมูลนี้ หากได้คำจำกัดความ/คอลัมน์เพิ่มภายหลังให้เพิ่มผ่าน Metric Mapping โดยไม่กระทบ Metric เดิม
- System Setting แสดงกลุ่ม `HomePro Group — Shared Source` หนึ่งกรอบ พร้อม Shared Path/Schedule/Run และ child status cards HP/MH ที่แยกสี/ตัวเลขชัดเจน
- Progress และผลลัพธ์แสดงขั้นตอน Discover, Pair, Download, Parse, Split, Validate, Import, Summary พร้อม current date/file และ counts แยก HP/MH
- Record summary แยก source rows, accepted rows, interest SKU, new SKU, returns, new branch, mapping pending, imported/skipped/failed ของแต่ละ MT
- Telegram ส่งหนึ่งข้อความต่อ Shared Run ด้วย Bot เดิม โดยแยก section HP/MH และนับเฉพาะ Event ของรอบนั้น

### Success Criteria

- Parser อ่าน ZIP ตัวอย่าง Inventory/Sales ได้ครบและ reconcile source totals; S/M split ถูกต้องและคงค่าติดลบ
- วันใด HP หรือ MH fail ต้องไม่มี Fact/Batch ของทั้งคู่จากวันนั้น; วันอื่นใน Initial Scan เดินหน้าต่อได้
- Rename ไฟล์ข้อมูลเดิมไม่ Import ซ้ำ; corrected content replace วันเดิมแบบ Atomic และ trace ได้
- Schedule เดียวไม่สร้าง Run ซ้ำต่อ MT และ Incremental scan ไม่ไล่ประวัติทั้งหมดทุกวัน
- Dashboard/Settings/API แยก HP/MH ถูกต้อง ขณะที่ TWD behavior และ regression tests เดิมผ่านทั้งหมด
- รายงาน HP/MH เปิดได้จากเมนูรายงาน แยกข้อมูลด้วย MT และ Branch prefix ถูกต้อง; Sales/Inventory totals ตรงกับ Source และไม่มี Stock On Order ที่ระบบสร้างขึ้นเอง
# Settings Control Plane Standard — 8 กันยายน 2026

## Objective

- ปรับเฉพาะหน้า `Settings` ให้เป็น Control Plane ที่เป็นมืออาชีพ อ่าน Scope ของค่าได้ทันที และใช้ Template เดียวกันสำหรับทุก Modern Trade
- แยกค่าที่มีผลกับทุก MT ออกจากค่าที่มีผลเฉพาะ MT โดยไม่เปลี่ยน Import, Mapping, Schedule, Notification หรือ Report business logic เดิม
- วางมาตรฐาน Component/คำศัพท์ของ Settings ให้ใช้ซ้ำได้เมื่อเพิ่ม MT หรือ Function ใหม่ โดยรอบนี้ยังไม่เปลี่ยนหน้าส่วนอื่นของ Application

## Scope Model และคำศัพท์มาตรฐาน

- ใช้คำว่า `Global Settings` สำหรับค่าที่ทุก MT ใช้ร่วมกันเท่านั้น
- ใช้คำว่า `MT Settings` สำหรับค่าที่มีผลเฉพาะ TWD, HP, MH, GH, SCG, HH หรือ TA
- หน้า Settings เป็นหน้าเดียว มี Scope tabs: `Global`, `TWD`, `HP`, `MH`, `GH`, `SCG`, `HH`, `TA`
- รอบนี้ไม่เพิ่ม `Window Asia`; จะเพิ่มเป็น Scope ใหม่ภายหลังโดยใช้ Template เดียวกัน
- Base UNC และ AD Account เป็น Global Data Connection; Subfolder, Automation, Mapping, Historical Data และ Report Configuration เป็น MT scope
- `HP` และ `MH` มี Tab แยก แต่ใช้ Source Folder และ Schedule ร่วมกัน การแก้ Schedule จาก Tab ใดต้องสะท้อนไปอีก Tab และแสดงป้าย `Shared schedule · HP + MH`
- HP/MH ประมวลผลพร้อมกันหนึ่ง Run แต่แสดงผลลัพธ์ Record, Warning, Approval และ Status แยกตาม MT

## Settings Information Architecture

### Global

1. `Data Connection` — Base UNC, Domain/AD account, User, Password และ Test connection
2. `Notifications` — Telegram destination, Bot credential และ Event policy ส่วนกลาง
3. `System Health & Alerting` — Daily health schedule, Critical/Recovery policy, Threshold และ Check now

### ทุก MT Tab

1. `Data Source & Automation` — Subfolder, Source identity, Schedule, Run now และสถานะล่าสุด
2. `Data Mapping & Governance` — Item/Branch Mapping, Mapping attention และ Unmatched policy
3. `Historical Data & Coverage` — Registry, Historical backfill และ Data coverage
4. `Report Configuration` — จำนวนแถวและพฤติกรรมการแสดงผลที่มีผลเฉพาะ MT

## Consistent Settings Template

- ทุก Scope ใช้ Header, Tab, Section header, Control grid, Status badge, Action placement, Validation, Loading, Error และ Empty state ชุดเดียวกัน
- Tab ที่ยังไม่มี Function ต้องคง Section ไว้ในตำแหน่งเดียวกัน แสดง Disabled state พร้อมข้อความ `Not available for this MT` และคำอธิบายสั้น ห้ามซ่อนจนผู้ใช้เข้าใจว่าโครงสร้างไม่เหมือนกัน
- Active tab ใช้ Primary Blue, ส่วน Status ใช้ semantic tokens เดิม และห้ามสร้าง Theme สีคนละชุดต่อ MT
- ใช้ Lucide icons, Aptos/Segoe UI และ Cascadia Mono สำหรับรหัส/ตัวเลขตาม Design System ปัจจุบัน
- Action ที่ทำงานทันที เช่น Test connection, Run now, Import/Export, Download และ Check now ต้องแยกจากการบันทึกค่าอย่างชัดเจน
- ใช้ปุ่ม `Save changes` หนึ่งปุ่มสำหรับค่าที่แก้ไขทั้งหมด โดยบันทึกเฉพาะ Scope/Field ที่เปลี่ยน; ค่าไม่เปลี่ยนต้องไม่ถูกเขียนซ้ำ
- เมื่อสลับ Tab ต้องรักษาค่าที่แก้แต่ยังไม่บันทึกและแสดง Dirty indicator; ห้ามทำข้อมูลที่กรอกหายโดยไม่มีคำเตือน

## Protected Boundaries และ Non-scope

- ห้ามเปลี่ยน parser, reconciliation, duplicate protection, transaction, fact data, mapping semantics, schedule execution หรือ report calculation
- ห้ามสร้าง configuration ปลอมให้ MT ที่ backend ยังไม่รองรับ; UI ต้องแสดงสถานะไม่พร้อมอย่างตรงไปตรงมา
- ไม่ redesign Dashboard, Report, Import หรือ Monitoring ใน Phase นี้
- ไม่เพิ่ม Window Asia และไม่เปิด Function ใหม่ของ GH, SCG, HH หรือ TA

## Success Criteria

- ผู้ใช้ระบุได้ทันทีว่าค่าใดเป็น Global และค่าใดมีผลเฉพาะ MT
- ทุก MT Tab มีโครงสร้างและลำดับ Section เหมือนกัน รวมถึง Disabled/Empty/Error/Loading states
- HP/MH แยกบริบทชัดเจน แต่ Source/Schedule ที่ใช้ร่วมกันไม่สร้างค่าซ้ำหรือขัดแย้งกัน
- ทุกค่าที่มีอยู่เดิมโหลด บันทึก และทำงานเหมือนเดิมหลังย้ายตำแหน่ง UI
- Keyboard สามารถเปลี่ยน Tab และเข้าถึง Control ได้, Focus ชัดเจน, ข้อความไม่ใช้สีเป็นตัวสื่อความหมายเพียงอย่างเดียว
- Existing backend/frontend regression, ESLint, Ruff และ production build ผ่านก่อน deploy

## Amendment: TWD Settings Parity for HP/MH — 8 กันยายน 2026

### Product Decision

- ใช้หน้าและลำดับการทำงานของ `TWD Settings` เป็น Master Template สำหรับ Modern Trade ทุกเจ้า โดยรอบนี้เปิดใช้งานจริงเฉพาะ `TWD`, `HP` และ `MH`
- Logic ปัจจุบันของ TWD เป็น protected reference ห้ามเปลี่ยน business behavior, calculation, workflow หรือผลลัพธ์เดิมโดยไม่ได้รับคำสั่งจาก Product Owner
- HP และ MH เป็นคนละ Modern Trade: Mapping workbook, Mapping counts, Unmatched visibility, Report page size, Data Coverage, SKU Backfill, Run status และ Audit ต้องแยกตาม `mtCode` เสมอ
- HP/MH ใช้ร่วมกันเฉพาะ FileShare source, Schedule และการอ่าน source pair ของ Automatic Import; Shared source ห้ามทำให้ configuration หรือข้อมูลผลลัพธ์เฉพาะ MT ปะปนกัน

### Required Settings Sections

แท็บ TWD, HP และ MH ต้องแสดง Template เดียวกันตามลำดับ:

1. Data Source & Automation
2. Item and Branch Mapping
3. Historical Backfill by SKU
4. Report Display
5. Data Coverage
6. Unmatched Data

### Data and Empty-state Rules

- ทุก API และ action ของ Section ข้างต้นต้องระบุ `mtCode` และอ่าน/เขียนเฉพาะ Modern Trade ที่เลือก
- Export/Import Mapping ของ HP และ MH ต้องเป็นคนละชุดและมีผลเฉพาะ Tab ที่สั่งงาน
- Historical Backfill ของ HP/MH ต้องเติมเฉพาะ SKU และ Modern Trade ที่เลือก แม้ source ZIP จะเป็นไฟล์คู่ที่ใช้ร่วมกัน และต้องไม่แก้ Fact/Mapping ของอีก MT
- ถ้า Modern Trade หรือ entity นั้นยังไม่มีข้อมูล ห้ามยืมจำนวนจาก MT อื่นและห้ามแสดงเลข `0` แทนการไม่มีข้อมูล ให้แสดง `ยังไม่มีข้อมูล` เพื่อแยกจาก Loading และ Error
- ถ้ามีข้อมูลจริงและผลนับเป็นศูนย์ สามารถแสดง `0` ได้; Backend ต้องส่ง availability metadata เพื่อแยกสองกรณีนี้อย่างชัดเจน
- GH, SCG, HH และ TA ยังไม่เปิด Function จริงในรอบนี้ และต้องไม่เรียก API ของ TWD เป็น fallback

### Acceptance Criteria

- TWD ให้ผลเหมือนก่อน refactor ทุก action และ regression test เดิมผ่าน
- เปิดแท็บ HP หรือ MH แล้วเห็น Section และ Interaction ชุดเดียวกับ TWD โดยข้อความอ้างชื่อ MT ปัจจุบัน
- Export, Import, Toggle, Page size, Coverage และ Backfill ไม่อ่านหรือแก้ข้อมูลข้าม MT
- HP Backfill ไม่เพิ่ม/ลบ/แก้ Fact หรือ Mapping ของ MH และ MH Backfill ไม่กระทบ HP
- ไม่มีข้อมูลแสดง `ยังไม่มีข้อมูล`; Loading และ Error มีสถานะแยกและไม่ถูกนำเสนอเป็น Empty state
# TWD Performance Multi-Range and Inventory Turnover Prototype — PRD (8 September 2026)

## Objective

ยกระดับหน้า Matrix Performance ของ TWD ให้เลือกช่วงวันที่แบบไม่ต่อเนื่องได้สูงสุด 12 ช่วง แสดงคอลัมน์สุดท้ายได้ครบแม้มี Scrollbar และเพิ่มตัวชี้วัด Inventory Turnover ราย SKU (`TOM`/`TOD`) โดยรักษา Logic, Filter, Pagination, Mapping และผลลัพธ์เดิมนอกขอบเขตนี้ เพื่อใช้ TWD เป็น Prototype ก่อนขยายไป Modern Trade อื่นในภายหลัง

## Problem

- ตัวเลือกวันที่ปัจจุบันรองรับเพียงช่วงเดียว จึงไม่เหมาะกับการรวมเฉพาะหลายช่วงที่ไม่ต่อเนื่อง
- Vertical Scrollbar ทับพื้นที่คอลัมน์ขวาสุด ทำให้ตัวเลขอ่านได้ไม่ครบและอาจตีความผิด
- Inventory Matrix ยังไม่มีตัวชี้วัดว่า Stock ล่าสุดรองรับยอดขายได้อีกกี่เดือนหรือกี่วัน
- Excel ที่ Download ต้องตรงกับ Filter และข้อมูลที่ผู้ใช้เห็นบนหน้า App เพื่อใช้ทำงานต่อได้โดยไม่ต้องกรองซ้ำ

## Users And Roles

- Business user: เลือกช่วงวันที่, SKU และ Branch; อ่าน Matrix/TOM/TOD; Download Excel ตามผลที่เห็น
- Admin/Product Owner: ตรวจสอบความถูกต้องของสูตรและใช้ TWD เป็นมาตรฐานสำหรับ MT อื่นในอนาคต
- รอบนี้ไม่มีการเพิ่มหรือเปลี่ยน Permission

## Goals And Success Criteria

- เพิ่ม/ลบช่วงวันที่ได้ตั้งแต่ 1 ถึง 12 ช่วง และแจ้ง Conflict ทันทีเมื่อช่วงใดทับกัน
- หน้า App, KPI Summary, Matrix และ Excel ใช้ชุด Filter เดียวกันและไม่รวมวันที่ในช่องว่างระหว่างช่วง
- ตัวเลขคอลัมน์ขวาสุดมองเห็นครบทุกหลักที่ตำแหน่ง Scroll ขวาสุด
- Inventory ทุก View แสดง TOM/TOD แบบ Sticky และค่าเฉลี่ยรวมของ SKU ทั้งหมดที่ผ่าน Filter
- สูตร TOM/TOD และการปัดทศนิยมให้ผลเหมือนกันใน API, UI และ Excel
- Regression tests ยืนยันว่า Single range และ Logic เดิมยังให้ผลเหมือนก่อนเปลี่ยน

## Scope

### Must Have

1. Multi-range date selector สูงสุด 12 ช่วงในตำแหน่งที่ใช้ `ช่วงวันที่` เดิม
2. Inline validation ทันทีเมื่อกรอกช่วงครบ ทั้งรูปแบบวันที่, from/to และการทับกัน
3. Matrix/API/Export รองรับ Union ของช่วงวันที่ และเรียงวันที่จริงโดยไม่สร้างคอลัมน์ใน Gap
4. Right-side scrollbar gutter หรือพื้นที่ท้ายตารางที่ทำให้คอลัมน์สุดท้ายเห็นครบ
5. Inventory-only sticky columns `TOM` และ `TOD` ต่อจาก WA Description; เมื่อซ่อน Description ให้ต่อจาก WA Item
6. Inventory Header แสดง `AVG TOM` และ `AVG TOD` ของ SKU ทั้งหมดที่ผ่าน Filter ไม่จำกัดเฉพาะหน้าปัจจุบัน
7. Excel ตรงกับ Mode, Metric, View, SKU, Branch และ Date ranges บน App และมี TOM/TOD ใน Inventory

### Non-Scope

- ยังไม่ขยาย Feature นี้ไป HP, MH หรือ MT อื่น
- ไม่เปลี่ยน Sales Basis, Metric, Mapping, Pagination, Detail Drawer หรือ Business Logic เดิมอื่น
- ไม่เปลี่ยนตัวเลือกเดือนของ Sales View Branch/Month และ View Month
- ไม่ใช้ข้อมูล Stock เก่ามาทดแทนเมื่อ SKU ไม่มี Stock ในวันอ้างอิง

## Core Workflows

### Multi-range Selection

1. เปิดตัวเลือกช่วงวันที่ ซึ่งเริ่มต้นอย่างน้อยหนึ่งแถว
2. เพิ่มช่วงได้สูงสุด 12 ช่วงและลบช่วงที่ไม่ต้องการได้
3. เมื่อกรอก From/To ของแต่ละช่วงครบ ระบบตรวจทันทีและชี้ช่วงที่ Conflict โดยตรง
4. ปุ่ม Apply ใช้งานได้เมื่อทุกช่วงถูกต้องเท่านั้น
5. เมื่อ Apply ระบบโหลดเฉพาะ Union ของวันที่ในทุกช่วง เรียงจากเก่าไปใหม่ และไม่รวม Gap

### Inventory Turnover

1. หา Reference Date จากวันที่ข้อมูลล่าสุดใน Union ของช่วงที่เลือก
2. รวม Stock On Hand ของ SKU ใน Reference Date ตาม Branch filter ปัจจุบัน
3. รวม Positive Sales Qty ของสามเดือนปฏิทินเต็มก่อนเดือน Reference Date โดยใช้ Branch/SKU filter เดียวกัน
4. คำนวณ TOM/TOD ตามกฎด้านล่างและแสดงใน Sticky columns
5. Header แสดงค่าเฉลี่ยของทุก SKU ที่ผ่าน Filter และคำนวณค่าได้

### Excel Export

1. ผู้ใช้จัด Filter และ View จนพอใจกับผลบน App
2. Download Excel ส่ง Filter contract เดียวกับ Matrix
3. Workbook มีเฉพาะข้อมูลที่ตรงกับ App รวมถึง Union date ranges, TOM และ TOD

## Business Rules And Constraints

- รองรับสูงสุด 12 ช่วง แต่ละช่วงรวมทั้งวันเริ่มต้นและวันสิ้นสุด
- ช่วงที่ใช้วันเดียวกันแม้เพียงหนึ่งวันถือว่าทับกัน เช่น `1–10` กับ `10–15` ไม่ผ่าน; `1–10` กับ `11–15` ผ่าน
- Validation ต้องเกิดทันทีหลัง From/To ของช่วงนั้นครบ และต้องระบุคู่ช่วงที่ Conflict
- ปุ่ม Apply ต้อง Disabled ขณะมีช่วงไม่ครบ, วันที่ไม่ถูกต้อง, From มากกว่า To หรือช่วงทับกัน
- Reference Date คือวันที่ล่าสุดที่มีข้อมูลจากทุกช่วงรวมกัน
- Sales lookback คือสามเดือนปฏิทินเต็มก่อนเดือนของ Reference Date; เดือนที่ไม่มียอดนับเป็นศูนย์และยังหารด้วย 3
- ใช้เฉพาะ Sales Qty ที่มากกว่า 0; ไม่รวม Return และ Adjustment ติดลบ
- `Average Monthly Sales = ROUND_HALF_UP(Positive Sales Qty 3 เดือน / 3, 2)`
- `TOM = ROUND_HALF_UP(Stock On Hand / Average Monthly Sales, 2)`
- `TOD = ROUND_HALF_UP(TOM × 30, 2)`
- ปัดสองตำแหน่งทุกขั้น ไม่ใช้ค่าทศนิยมเต็มจากขั้นก่อนหน้า
- ถ้า Average Monthly Sales เป็นศูนย์, ไม่มี Stock row ใน Reference Date หรือ Stock On Hand ติดลบ ให้ TOM/TOD เป็น `—`
- Stock On Hand เท่ากับศูนย์และ Average Monthly Salesมากกว่าศูนย์ให้ TOM/TOD เท่ากับ `0.00`
- `AVG TOM` และ `AVG TOD` เป็น Simple arithmetic mean ของ SKU ทั้งหมดที่ผ่าน Filter และมีค่าคำนวณได้; SKU ที่เป็น `—` ไม่นับทั้งเศษและจำนวนตัวหาร
- TOM/TOD ใช้ Branch filter เดียวกับ Matrix; ทุก Branch หมายถึงรวมทุก Branch ที่อยู่ใน Scope ของรายงาน
- TOM/TOD แสดงใน Inventory Mode ทุก View และยังแสดงเมื่อปิด Description

## Data And Integration Requirements

- PostgreSQL Fact/Summary เป็น Source of Truth เดิม ไม่เพิ่ม External integration
- API ต้องรับ Date range collection แบบมีโครงสร้างและ validate จำนวน/รูปแบบ/Overlap ฝั่ง Server ซ้ำ
- ทุก Query ที่มีผลต่อ rows, dates, totals, pagination และ export ต้องใช้ Date union predicate เดียวกัน
- Turnover summary ต้องคำนวณจาก SKU scope ทั้งหมดก่อน Pagination เพื่อให้ Header ไม่เปลี่ยนเมื่อเปลี่ยนหน้า
- ต้องหลีกเลี่ยงการดึงข้อมูล Bounding range แล้วกรอง Gap เฉพาะ Frontend เพราะจะทำให้ Summary/Pagination/Export ผิด

## Architecture Direction

- เพิ่ม shared date-range contract และ normalization/validation utilities ให้ Frontend และ Backend มีพฤติกรรมสอดคล้องกัน
- Backend สร้าง reusable SQL predicate แบบ OR ของช่วงวันที่ที่ normalize แล้ว และใช้กับ Performance/Detail/Export paths ที่เกี่ยวข้อง
- เพิ่ม turnover projection ใน Performance response ระดับ Item และ Summary โดยคำนวณเฉพาะ Inventory requests
- Frontend ขยาย DateRangePicker เป็น multi-row editor ที่มี inline feedback และคง Apply workflow เดิม
- PerformanceMatrix เพิ่ม Sticky TOM/TOD ด้วย CSS offsets ที่รองรับ Description on/off และแก้ scroll end clearance โดยไม่เพิ่มข้อมูลปลอมใน Matrix

## Risks And Mitigations

- Query ช้าจาก 12 OR ranges: normalize/sort ranges, จำกัด 12 ช่วง, ใช้ date/index predicate และวัด query time กับข้อมูลจริง
- Summary กับ page rows ไม่ตรงกัน: ใช้ filter builder และ turnover service เดียวกันทุก endpoint
- Floating-point ต่างกันระหว่าง API/UI/Excel: คำนวณและปัดด้วย Decimal ROUND_HALF_UP ฝั่ง Serverแล้วส่งค่าที่พร้อมแสดง
- Sticky offsets ผิดเมื่อซ่อน Description: ใช้ explicit column layout variants และ regression tests ทั้งสองสถานะ
- Scrollbar ต่างกันตาม OS: ทดสอบ overlay/classic scrollbar และเพิ่ม end gutter ที่ไม่ขึ้นกับความกว้าง scrollbarแบบ hardcode เพียงค่าเดียว

## Open Questions

- ไม่มี Business Rule ค้าง ณ วันที่ 8 กันยายน 2026

## Status And Priority

- Status: Phase 2 backend state/filtering complete locally; awaiting Product Owner approval for Phase 3 TWD Matrix and filter UI
- Priority: (1) contract/tests, (2) multi-range query correctness, (3) TOM/TOD correctness, (4) Matrix scroll/sticky UI, (5) Excel parity, (6) full regression

# TWD Sho/Pro SKU Attention Flags — 9 September 2026

## Objective

เพิ่มสถานะความสนใจพิเศษระดับ SKU ในรายงาน TWD เพื่อให้ผู้ใช้งานทุกคนเห็นตรงกันว่า SKU ใดเป็นสินค้าตัวโชว์ (`Sho`) หรือสินค้าทำ Promotion (`Pro`) โดยไม่เปลี่ยน Sales, Inventory, TOM/TOD หรือ Business Logic เดิม

## Users And Ownership

- User ทุกคนที่ใช้งานหน้า Report สามารถ Check/Uncheck Sho และ Pro ได้
- สถานะเป็น Shared Application Data ใน PostgreSQL ไม่ใช่ User preference และไม่เก็บใน Browser Local Storage
- Ownership แยกด้วย `Modern Trade + Source SKU`; SKU รหัสเดียวกันต่าง MT มีสถานะอิสระต่อกัน
- Phase แรกทำเฉพาะ TWD Prototype; HP/MH และ MT อื่น rollout ภายหลังด้วย Template เดียวกัน

## Functional Requirements

1. Matrix เพิ่ม Sticky checkbox columns ขนาดเล็ก `Sho` และ `Pro` ก่อนคอลัมน์ Source SKU
2. Sho และ Pro เลือกแยกกันได้ และ SKU หนึ่งรายการเลือกทั้งสองสถานะได้
3. Check/Uncheck บันทึก Database ทันทีโดยไม่มีปุ่ม Save แยก
4. หากบันทึกไม่สำเร็จ Frontend คืนค่า Checkbox เดิมและแสดง Error ที่บอกให้ User ลองใหม่
5. สถานะแสดงในทุก Mode และ View ที่ SKU อยู่ในผลลัพธ์: Sales, Inventory, Branch, Date และ Month
6. Import ใหม่, เปลี่ยน Mapping, Inactive/Reactivate SKU ต้องไม่ล้างสถานะเดิม
7. Filter มีค่า `ทั้งหมด`, `Sho`, `Pro`, `Sho + Pro` และ `ยังไม่กำหนดสถานะ`
8. `Sho` รวมรายการที่เลือก Sho ไม่ว่าจะมี Pro ร่วมด้วยหรือไม่; `Pro` ใช้หลักเดียวกัน; `Sho + Pro` ต้องเป็น true ทั้งคู่; `ยังไม่กำหนดสถานะ` ต้องเป็น false ทั้งคู่
9. Filter ต้องทำฝั่ง Server ก่อน Summary และ Pagination; KPI, SUM, AVG TOM/TOD, SKU count, Branch count และ Excel คำนวณจาก Scope ที่ผ่าน Filter
10. Filter `ทั้งหมด` รักษาลำดับ SKU เดิม การเปลี่ยน Flag ไม่ดัน Row ขึ้นด้านบน
11. Checkbox ไม่มีผลต่อค่าหรือสูตรของ Amount, Qty, Stock, TOM และ TOD
12. Audit เก็บค่าเดิม/ค่าใหม่, MT, Source SKU, เวลาและ Actor ตามกลไก Audit เดิม โดยไม่เพิ่ม Admin-only permission

## Visual And Interaction Rules

- Sho only: Amber accent `#D97706` กับ translucent row overlay
- Pro only: Violet accent `#7C3AED` กับ translucent row overlay
- Sho + Pro: Dual-tone Amber/Violet accent และ overlay ผสมที่แยกจากสองสถานะแรกได้ชัดเจน
- Checkbox และ Header text ต้องคงอยู่เพื่อไม่สื่อความหมายด้วยสีเพียงอย่างเดียว
- Row overlay ต้องซ้อนบน Heatmap แบบโปร่งใส ไม่ลบระดับสีข้อมูลเดิม
- Selected Row ใช้ Blue outline เหนือ Flag styling; Return/negative typography คงสีเตือนเดิม
- Checkbox แสดง pending feedback ระหว่างบันทึก และมี accessible label ที่ระบุ MT, SKU และสถานะ

## Excel Parity

- Excel เพิ่มคอลัมน์ `Sho` และ `Pro` ก่อน Source SKU
- ใช้ข้อความ `SHO`/`PRO` ใน Cell ที่เลือกและเว้นว่างเมื่อไม่เลือก เพื่ออ่านได้ชัดและไม่พึ่งสัญลักษณ์ Checkbox
- Fill/row accent สอดคล้องกับสถานะใน App โดยไม่ทับ Conditional Formatting ของ Heatmap และค่าติดลบ
- Export ใช้ Filter contract เดียวกับ App และส่งออกทุก Row ที่ผ่าน Filterโดยไม่ขึ้นกับ Pagination
- Title/metadata ของ Workbook ระบุ Sho/Pro filter ที่ใช้

## Data And Architecture Direction

- เพิ่มตาราง Metadata แยกจาก Fact/Import/Mapping เช่น `sku_analysis_flags`
- Unique key: `(modern_trade_id, source_sku)` พร้อม Boolean `is_showroom`, `is_promotion`, `updated_at` และ actor reference ตามรูปแบบเดิม
- Performance response เพิ่ม Sho/Pro ใน Item projection และ SKU options ตามที่จำเป็น
- เพิ่ม partial update endpoint ที่เปลี่ยนเฉพาะ Field ที่ User กด เพื่อลดโอกาส concurrent update ทับอีก Flag
- Performance และ Export ใช้ predicate เดียวกันสำหรับ Flag filter; ห้ามกรองเฉพาะ Frontend
- ไม่แก้หรือลบ Sales/Inventory Fact, ImportBatch, ItemMapping หรือ SkuInterest

## Success Criteria

- User ทุกคนเห็น Sho/Pro ชุดเดียวกันหลัง refresh หรือ login จาก Browser/Profile อื่น
- Toggle บันทึกทันทีและ Failure ไม่ทำให้ UI แสดงค่าที่ไม่ได้บันทึก
- ทุก Mode/View แสดง Flag เดิมของ SKU อย่างสม่ำเสมอ
- KPI/SUM/AVG/Pagination/Excel ตรงกับ Flag filter ที่เลือก
- Heatmap, Selected state, Return และ Existing filters ยังอ่านได้ชัดและทำงานเหมือนเดิม
- Query latency ไม่ถดถอยอย่างมีนัยสำคัญจาก TWD performance baseline

## Non-Scope

- ไม่มีผลต่อสูตรหรือยอดข้อมูล
- ไม่มี Auto-tag จากยอดขายหรือ Promotion date
- ไม่มี Admin approval, Bulk edit หรือ Flag priority sorting ใน Phase แรก
- ยังไม่ rollout ไป HP/MH ใน Phase แรก

## Open Questions

- ไม่มี Business Rule ค้าง ณ วันที่ 9 กันยายน 2026

## Status And Priority

- Status: Phase 3 TWD Matrix and filter UI complete locally; Phase 4 Excel parity not started
- Priority: (1) DB/API contract, (2) server-side filter/summary parity, (3) Matrix interaction/visual states, (4) Excel parity, (5) performance/regression validation
