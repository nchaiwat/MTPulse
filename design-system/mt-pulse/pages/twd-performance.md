# TWD Performance Page Override

## Multi-range Date Selection

- ใช้ Date-range editor แบบรายการ เริ่มหนึ่งช่วงและเพิ่มได้สูงสุด 12 ช่วง
- Error อยู่ใต้ช่วงที่ผิดและประกาศด้วย `role="alert"`; สีแดงไม่ใช่สัญญาณเพียงอย่างเดียว
- ตรวจรูปแบบ, From/To และ Overlap ทันทีเมื่อแก้ค่า แต่โหลดข้อมูลเมื่อกด `แสดงผล` เท่านั้น
- Label ปิด Popover แสดงจำนวนช่วงและขอบเขตโดยย่อเมื่อมีมากกว่าหนึ่งช่วง

## Inventory Turnover Columns

- TWD Inventory แสดง `TOM` และ `TOD` หลัง WA Description หรือหลัง WA Item เมื่อซ่อน Description
- TOM/TOD เป็น Sticky identity metrics ใช้ tabular numerals และมี Divider หลัง TOD
- Summary row ใช้คำว่า `AVG` และแสดง `AVG TOM`/`AVG TOD`; ค่าไม่พร้อมแสดงเป็น em dash
- HP/MH และ Modern Trade อื่นยังไม่ใช้ Override นี้จนกว่า Product Owner อนุมัติ rollout

## Scroll Contract

- Top และ body horizontal tracks ต้องมี scroll range เท่ากันหลังชดเชยความกว้าง Vertical Scrollbar ที่วัดได้จริง
- Body ใช้ stable scrollbar gutter เพื่อไม่ให้คอลัมน์ขวาสุดหรือหลักสุดท้ายถูกบัง
- ห้าม hardcode ความกว้าง Scrollbar ตาม OS

## Inventory Month

- เปิด View `Month` เฉพาะ TWD Prototype ในรอบนี้
- ค่า Inventory ของแต่ละเดือนคือ Snapshot จากวันล่าสุดที่มีข้อมูลในเดือนนั้น ไม่ใช่ผลรวมของทุกวัน
- Month range, Branch และ SKU filter ต้องใช้เงื่อนไขเดียวกันทั้ง App และ Excel

## IRM-calibrated Visual Hierarchy

- ใช้ IRM เป็น Quality Reference โดยไม่คัดลอก Layout หรือเปลี่ยน Workflow ของ MT Pulse
- เพิ่มขนาด Control, KPI และข้อความรองใน TWD ให้อ่านง่ายขึ้น โดยยังรักษา Dense Matrix
- Matrix label header ใช้ Navy surface, Summary ใช้ Sky tint และ Primary blue เป็นเส้นแบ่งลำดับข้อมูล
- Visual override รอบนี้ Scope เฉพาะ `data-performance-source='TWD'`; HP/MH ไม่เปลี่ยนตาม

## Compact Operations Header

- Desktop ลดพื้นที่เหนือ Matrix โดยซ่อน Eyebrow และคำอธิบายที่ซ้ำกับชื่อหน้า แต่คงชื่อรายงาน วันที่ข้อมูลล่าสุด และระดับข้อมูลไว้
- Mode/View และ Filter ยังแยกสองแถวตาม Workflow เดิม เพียงลด Vertical padding และความสูง Control
- KPI Ledger คง Label และค่าหลักทั้งหมด แต่ซ่อน Helper text ที่ซ้ำบน Desktop
- Matrix heading อยู่แถวเดียวและ Matrix viewport ใช้พื้นที่แนวตั้งที่คืนมา; ไม่เปลี่ยน Filter, Query, KPI หรือ Export logic
- Scope เฉพาะ TWD Prototype และไม่เปลี่ยน Mobile layout

## Sho/Pro Attention Layer

- TWD Matrix ใช้ Sticky `Sho` และ `Pro` columns ก่อน Source SKU; แต่ละช่องมีพื้นที่กดเต็ม cell และ accessible label ระบุ MT/SKU
- Sho ใช้ Amber `#D97706`, Pro ใช้ Violet `#7C3AED`, Both ใช้ dual-tone overlay แบบโปร่ง โดยไม่ลบ Heatmap หรือสีค่าติดลบ
- Selected row ใช้ Primary Blue boundary อยู่เหนือ attention color และ pending save แสดง feedback เฉพาะ checkbox ที่กำลังบันทึก
- Filter อยู่ใน Filter bar ใช้ค่า ทั้งหมด/มีสถานะ Sho หรือ Pro/Sho/Pro/Sho + Pro/ยังไม่กำหนดสถานะ และ Scope เฉพาะ TWD Prototype
- Detail Drawer แสดง Sho/Pro เป็น read-only badges เพื่อรักษาบริบท ไม่เพิ่มจุดแก้ไขสถานะซ้ำ
