# TWD Sales Dashboard

## Page anatomy

1. Compact page header: ชื่อหน้า, วันข้อมูลล่าสุด, Download Excel และปุ่มเปิดรายงานละเอียดอยู่ในแถวเดียวบน Desktop โดยไม่มี Global header ซ้ำ
2. Context toolbar: ปี, ช่วงเวลา และ Metric
3. Comparison strip: Sales Ex.VAT, Sales YoY, Qty, Qty YoY และ Data completeness
4. Monthly trend: accessible line chart คู่กับตารางรายเดือน
5. YoY comparison: grouped bar chart และสรุปเปรียบเทียบรายเดือน
6. Top 10 Branch และ Top 15 SKU: horizontal comparison chart คู่กับ ranked table

## Visual rules

- Page identity ใช้ชื่อเดียวกับ Report เสมอ: `TWD`, `HomePro (HP)` และ `MegaHome (MH)`; ห้ามใช้ชื่อย่อ/ชื่อภาษาไทยคนละรูปแบบใน Page title
- Current year ใช้ `#02ABFF`; previous year ใช้ Navy/Slate
- Positive/negative ใช้ Soft green/red พร้อมเครื่องหมายและตัวเลข ห้ามสื่อด้วยสีอย่างเดียว
- ตัวเลขใช้ tabular figures; chart ทุกตัวมี table เป็นข้อมูลสำรอง
- Radius 12–16px และ soft shadow เฉพาะ panel; ไม่มี hero, gradient ขนาดใหญ่ หรือ decorative animation
- Dashboard responsive ที่ 375, 768, 1024 และ 1440px โดย table เลื่อนแนวนอนได้
- ใช้ Typography hierarchy เดียวกับ TWD Report: Page 24/700, Section 16/700, KPI 20/700, Body/Control/Data 12px และ Label 10px
- Dashboard ใช้ Standard density เพื่ออ่านภาพรวมสบายกว่า Compact report; Active segmented control ใช้ `--primary-700` และตัวอักษรสีขาวเหมือนกันทั้งระบบ
- Desktop ซ่อน Eyebrow และคำอธิบายรองใน Header พร้อมใช้ Control สูง 34px เพื่อลดพื้นที่ก่อนถึงกราฟ
- Dashboard Excel ต้องใช้ Year, Period, Metric และ Modern Trade เดียวกับหน้าจอ พร้อม Summary, Monthly, Top Branch และ Top SKU จาก Dashboard response ชุดเดียวกัน

## Protected boundary

หน้า Dashboard เป็น module ใหม่ ห้ามแก้ DOM, State, Handler, Query หรือ Layout ของ `src/features/performance`.

## Multi-MT template contract

- Dashboard ของ `TWD`, `HomePro (HP)` และ `MegaHome (MH)` ใช้ Page component, chart treatment, toolbar, KPI strip, loading/error/empty state และ responsive pattern ชุดเดียวกัน
- Report ของทั้งสาม MT ใช้ TWD เป็น Visual Template ชุดเดียวกัน โดยความต่างที่เกิดจาก capability หรือข้อมูลของแต่ละ MT ต้องไม่ทำให้ Typography, spacing, header, control, KPI และ matrix treatment หลุดจากมาตรฐาน
- การปรับ Template ห้ามเปลี่ยน API parameters, Query, KPI calculation, Metric capability, Export behavior หรือ Business Logic เฉพาะ MT

## Ranking chart treatment

- Top Branch และ Top SKU ใช้ Ranked comparison row: อันดับ, รหัส, ชื่อ, แท่งปีปัจจุบัน/ปีก่อน, ค่าที่ปลายแท่ง และ YoY chip
- ปีปัจจุบันใช้ Strong Sky `#02ABFF`; ปีก่อนใช้ Navy `#102A43` ให้เป็นคู่สี High contrast เดียวกับกราฟ YoY
- แสดงค่าแบบย่อบนกราฟเสมอ และเมื่อ Hover, Click หรือ Keyboard focus ให้แสดงค่าจริงใน Comparison inspector ที่มีพื้นที่เฉพาะเหนือกราฟ ห้ามใช้ Tooltip ที่ลอยทับแท่งกราฟ ตัวเลข หรือ YoY chip
- YoY ใช้ Soft green/red พร้อมเครื่องหมายบวก/ลบ ไม่สื่อความหมายด้วยสีเพียงอย่างเดียว
- กราฟ 10–15 แถวต้องเริ่มจากด้านบนและใช้พื้นที่ตามข้อมูล ไม่จัดกึ่งกลางจนเกิดพื้นที่ว่างขนาดใหญ่
