# HomeHub (HH) Dashboard and Performance

## Template contract

- HH ใช้ shared Dashboard และ Performance components ชุดเดียวกับ TWD เพื่อให้ Layout, Typography, Density, Loading, Filter, Matrix, Sho/Pro, Drawer และ Excel Export สอดคล้องกัน
- ห้ามเรียกข้อมูล TWD เป็น fallback; ทุก Query ต้องส่ง `mt_code=HH` และแยก Mapping/Sho/Pro ตาม Modern Trade
- Inventory ของ HH ใช้ `Stock on hand` และ `Stock value` ตาม Source จริง ไม่สร้าง Stock on order ที่ไม่มีในไฟล์
- Inventory ทุก View แสดง TOM/TOD ด้วยสูตรกลางที่ตกลงแล้ว: ยอดขาย Qty บวกเท่านั้นของ 3 เดือนก่อนหน้า, หาร 3 และปัด 2 ตำแหน่งก่อนนำ Stock OH ไปหาร; TOD = TOM × 30

## Source contract

- หนึ่งวันใช้คู่ไฟล์ `StockReport.xlsx` และ `SaleReport.xlsx`; วันที่ภายใน Header ต้องตรงกัน
- Fact grain คือ `Data Date × HH Branch × HH SKU`
- SKU เป็น opaque text: ห้าม validate, pad, truncate หรือ classify ด้วยจำนวนหลัก/เลขศูนย์นำหน้า
- Source amount ของ HH เป็น Exclude VAT จึงเก็บ Amount เท่ากับ Source amount โดยไม่หาร 1.07
- Branch ปัจจุบัน 5 แห่ง: อุบลราชธานี, ชยางกูร, วารินฯ, ขอนแก่น และอำนาจ

## Mapping and attention

- นำเข้าและแสดง SKU ทั้งหมด แม้ยังไม่มี Item Mapping
- SKU ที่ยังไม่ Mapping แสดง WA Item เป็น em dash และสถานะ `ยังไม่ Mapping`; ห้ามตัดจาก Report
- Sho/Pro เป็นสถานะส่วนกลางของ HH SKU นั้น เห็นเหมือนกันทุก User และคงอยู่ทุก Filter/View/Export เช่นเดียวกับ TWD
- Mapping, Sho/Pro และข้อมูล HH ห้ามปะปนกับ TWD, HP หรือ MH แม้รหัส SKU จะเหมือนกัน
