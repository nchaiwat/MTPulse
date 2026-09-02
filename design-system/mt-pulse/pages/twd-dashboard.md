# TWD Sales Dashboard

## Page anatomy

1. Context toolbar: ปี, ช่วงเวลา, Metric และปุ่มเปิดรายงานละเอียด
2. Comparison strip: Sales Ex.VAT, Sales YoY, Qty, Qty YoY และ Data completeness
3. Monthly trend: accessible line chart คู่กับตารางรายเดือน
4. YoY comparison: grouped bar chart และสรุปเปรียบเทียบรายเดือน
5. Top 10 Branch และ Top 15 SKU: horizontal comparison chart คู่กับ ranked table

## Visual rules

- Current year ใช้ `#02ABFF`; previous year ใช้ Navy/Slate
- Positive/negative ใช้ Soft green/red พร้อมเครื่องหมายและตัวเลข ห้ามสื่อด้วยสีอย่างเดียว
- ตัวเลขใช้ tabular figures; chart ทุกตัวมี table เป็นข้อมูลสำรอง
- Radius 12–16px และ soft shadow เฉพาะ panel; ไม่มี hero, gradient ขนาดใหญ่ หรือ decorative animation
- Dashboard responsive ที่ 375, 768, 1024 และ 1440px โดย table เลื่อนแนวนอนได้

## Protected boundary

หน้า Dashboard เป็น module ใหม่ ห้ามแก้ DOM, State, Handler, Query หรือ Layout ของ `src/features/performance`.
