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

- เพิ่ม Daily Summary ระดับ `Modern Trade × Data Date × SKU` สำหรับ Amount, Sales Qty, Stock On Hand และ Stock On Order
- ใช้ Daily Summary เฉพาะ `grain=day_total` ใน safe fast path ที่ไม่มี Date/Branch/SKU/Search/Mapping filter; กรณีอื่นใช้ Fact query เดิม
- ก่อนใช้ fast path ต้องยืนยันว่า Branch ที่มี Fact ทั้งหมดอยู่ใน Active Branch Mapping เมื่อ `show_unmatched_branches=false`; หากไม่ครบให้ fallback
- Import และ Corrective Replace ต้อง refresh Daily Summary ของวันที่นั้นใน transaction เดียวกับ Fact และ Monthly Summary
- Migration ต้อง backfill จาก Fact เดิมและมี downgrade ที่ลบเฉพาะ Daily Summary table
- เปิด Gzip สำหรับ JSON เป็น optimization เสริม แต่ห้ามใช้แทนการแก้ Query

### Measured Baseline และ Acceptance Criteria

- Baseline Test Server: 4,512,804 facts, API response 5,584,255 bytes, TTFB 7.96–8.71 วินาที
- Temporary benchmark: Daily aggregate 109,496 rows; main query 62.8 ms และ daily totals 20.4 ms
- Response ใหม่ต้องเท่ากับ legacy path สำหรับ `items`, `points`, `dates`, `columnTotals`, `summary`, `branches` และ `meta`
- Branch/SKU/Date/Search/Mapping filter และ Inventory/Month/Branch views ต้องยังใช้ผลลัพธ์เดิม
- Full backend/frontend regression, Ruff, ESLint และ production build ต้องผ่านก่อน deploy
