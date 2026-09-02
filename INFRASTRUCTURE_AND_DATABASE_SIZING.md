# MT Pulse — Infrastructure, Database Sizing และแผน Production

อัปเดตล่าสุด: 30 สิงหาคม 2026 (Asia/Bangkok)

เอกสารนี้บันทึกข้อสรุปด้านขนาดระบบ โครงสร้างฐานข้อมูล และขั้นตอนเตรียม Production VM ที่ Product Owner ยืนยันแล้ว เอกสารนี้เป็นแผนงาน ยังไม่ได้อนุญาตให้ Format, Mount, ย้ายข้อมูล หรือแก้ Production Server จนกว่าจะได้รับ VM และตรวจสอบ Disk จริง

## 1. ข้อสรุป Production VM ระยะแรก

| Resource | ขนาดเริ่มต้น |
|---|---:|
| CPU | 4 vCPU (ขยายเป็น 6–8 vCPU ได้เมื่อ Historical Import หรือ Aggregation หนักขึ้น) |
| RAM | 32 GB |
| OS Disk | 80 GB |
| Database Disk | 250 GB SSD/NVMe แบบ Expandable |
| Database | PostgreSQL 17 |
| Application | Docker Engine และ Docker Compose บน Ubuntu LTS |
| Backup | เก็บแยกบน NAS ไม่เก็บสะสมใน Database Disk |

Product Owner ยืนยันให้เริ่ม Database Disk ที่ **250 GB** ไม่ใช้ 150 GB และยังไม่จัดสรร 500 GB ตั้งแต่แรก โดยให้ขยายตามการใช้งานจริง

RAM ช่วย Cache และความเร็ว Query แต่ไม่สามารถทดแทนพื้นที่ Disk ได้ CPU 4 vCPU เพียงพอสำหรับ User พร้อมกันประมาณ 1–2 คนเมื่อ Dashboard อ่านจาก Summary Table ส่วนการ Import ย้อนหลัง, Reindex และ Migration จะเร็วขึ้นหากขยายเป็น 6–8 vCPU

## 2. เหตุผลที่ Database Disk ต้องมากกว่าขนาดข้อมูลหลัก

ประมาณการข้อมูลสูงสุด:

```text
350,000 records/เดือน × 48 เดือน × 6 MT = 100,800,000 records
```

เผื่อ MT ที่มีจำนวนข้อมูลมากกว่า TWD และการเติบโต ใช้ขอบเขตออกแบบประมาณ **100–120 ล้าน records**

ผลวัดจริงบน Test Server เมื่อ 29 สิงหาคม 2026:

| ตาราง | Records | ขนาดรวม Table + Index |
|---|---:|---:|
| `sales_inventory_facts` | 376,420 | 278.6 MiB |
| `monthly_sales_summaries` | 25,132 | 7.2 MiB |

หากขยายความหนาแน่นของ Fact ปัจจุบันแบบเส้นตรง Raw Fact และ Index ที่ 120 ล้าน records จะอยู่ประมาณ 87 GiB แต่ Database Disk ยังต้องรองรับ:

- PostgreSQL WAL ระหว่าง Import และ Transaction
- พื้นที่ชั่วคราวสำหรับ Sort, Aggregate และ Export
- Index ใหม่ระหว่าง Reindex หรือ Migration
- Database bloat และ Autovacuum
- Docker volume metadata และ Log ที่เกี่ยวข้อง
- พื้นที่ว่างเพื่อป้องกัน Database หยุดเขียนเมื่อ Disk เต็ม

ดังนั้น 250 GB เป็นขนาดเริ่มต้นที่สมดุล โดย Backup ต้องอยู่บน NAS

## 3. เกณฑ์ขยาย Database Disk

ไม่รอให้ครบปี แต่ขยายตามพื้นที่ที่ใช้งานจริง:

| Disk usage | การดำเนินการ |
|---:|---|
| ต่ำกว่า 60% | สถานะปกติ |
| 60–70% | วางแผนและเตรียม Change ขยาย Disk |
| 70% | ขยาย Disk |
| 80% | ห้ามเริ่ม Historical Import, Reindex หรือ Migration ขนาดใหญ่ |
| 90% | Critical ต้องแก้ไขทันที |

แผนขยายโดยประมาณ:

```text
เริ่มต้น 250 GB
ขยายเป็น 400–500 GB เมื่อใช้งานถึงประมาณ 70%
ขยายต่อจากข้อมูลจริงและ Retention Policy
```

Monitoring ต้องแสดง Database size, Fact size, Index size, Disk free space, Dead tuples, Connections, Vacuum/Analyze และแจ้งเตือนพื้นที่ Disk

## 4. การแยก OS Disk และ Database Disk

Product Owner ไม่ต้องดำเนินการแบ่งหรือ Mount Disk เอง เมื่อ Production VM พร้อม Codex จะช่วยตรวจสอบและจัดการตามขั้นตอน โดยต้องให้ VM เห็น Disk สองลูก:

```text
Disk 1: 80 GB สำหรับ Ubuntu, Docker และ Source Code
Disk 2: 250 GB เป็น Disk ว่างสำหรับ PostgreSQL
```

ก่อนดำเนินการต้องขอผลคำสั่ง:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
```

ข้อควรระวัง:

- ห้าม Format จากการเดาชื่อ Device
- ต้องยืนยัน Disk 250 GB ที่ไม่มีข้อมูลสำคัญก่อนทุกครั้ง
- ห้ามใช้ OS Disk หรือ Root filesystem เป็นเป้าหมายของคำสั่ง Format
- บันทึก UUID ใน `/etc/fstab` ไม่อ้างชื่อ `/dev/sdX` เพียงอย่างเดียว
- Backup ก่อนย้าย PostgreSQL volume หรือแก้ Filesystem

### แนวทาง Filesystem ที่แนะนำ

ใช้ LVM บน Database Disk และใช้ `ext4` เพื่อให้ขยายใน VM ได้ง่าย:

```text
250 GB Virtual Disk
  └─ GPT Partition
      └─ LVM Physical Volume
          └─ Volume Group: vg_mtpulse
              └─ Logical Volume: lv_postgres
                  └─ ext4 mounted at /srv/mtpulse/postgres
```

ชื่อ Device จริงจะกำหนดหลังตรวจ `lsblk` เท่านั้น

### Checklist ที่ Codex ต้องดำเนินการเมื่อ VM พร้อม

1. ตรวจ Ubuntu version, CPU, RAM, Disk และ Network
2. ตรวจชื่อและ Serial/ขนาด Disk ให้แน่ชัด
3. ยืนยันกับ Product Owner ว่า Disk 250 GB เป็น Disk ว่างที่อนุญาตให้ Format
4. สร้าง Partition/LVM/Filesystem
5. Mount ที่ `/srv/mtpulse/postgres`
6. บันทึก UUID ใน `/etc/fstab`
7. ทดสอบ `mount -a` และ Restart VM
8. ตั้ง Owner/Permission สำหรับ PostgreSQL container
9. กำหนด Docker Compose ให้ PostgreSQL ใช้ Database Disk จริง
10. Restore Database หรือย้ายข้อมูลด้วยขั้นตอนที่ตรวจสอบย้อนกลับได้
11. ตรวจ `pgdata`, Database size และ Mount point ว่าอยู่บน Disk 250 GB
12. ทดสอบ Restart และยืนยันว่า PostgreSQL/API/Web เริ่มอัตโนมัติ
13. ตั้ง Log rotation และ Disk monitoring
14. บันทึกผลตรวจและ Recovery procedure

## 5. PostgreSQL และโครงสร้างรองรับ 120M Records

PostgreSQL 17 ยังเหมาะสม ไม่ต้องเปลี่ยนเป็น ClickHouse หรือ Database อื่น หากใช้ Raw Fact สำหรับ Audit/รายละเอียด และใช้ Monthly Summary สำหรับ Dashboard

### โครงสร้างเป้าหมาย

```text
Excel ของแต่ละ MT
       │
       ▼
Import Batch / Data Coverage
       │
       ▼
Raw Daily Fact — Partition ตามเดือน
       │
       ▼
Monthly Sales Summary
MT × Month × Source Item × Source Branch
       │
       ├─ Dashboard ต่อ MT
       ├─ Dashboard รวมทุก MT
       ├─ MoM / QoQ / YoY
       ├─ Top Branch
       └─ Top SKU
```

### สิ่งที่ควรปรับก่อนนำข้อมูลครบทุก MT

1. ทำ Import/API ให้รับ `modern_trade_id` แทนการ Hardcode TWD
2. เพิ่ม `mt_source_items` ระดับ `MT × Source SKU`
3. เพิ่ม `mt_source_branches` ระดับ `MT × Source Branch`
4. ย้าย Description, Category, Brand, Barcode และชื่อ Branch ออกจาก Fact ไป Dimension เพื่อลดข้อความซ้ำ
5. Partition `sales_inventory_facts` ตาม `data_date` แบบรายเดือน
6. ปรับ `monthly_sales_summaries` ให้ใช้ Dimension ID
7. เพิ่ม `calendar_dates` สำหรับ Month, Quarter, Year, Weekend และ Data Completeness
8. เพิ่ม `dataset_type` ใน Import Batch เพื่อรองรับ MT ที่ Sales/Inventory อาจแยกไฟล์
9. Benchmark จากข้อมูลจริงก่อนเพิ่ม Dashboard Rollup Table อื่น

ไม่สร้างตารางแยกสำหรับกราฟแต่ละภาพ เพราะ Monthly Summary เดียวสามารถสร้าง Monthly trend, MoM, QoQ, YoY, Top Branch และ Top SKU ได้

### กฎ Comparison

- ไม่เก็บค่า MoM/QoQ/YoY เป็นเปอร์เซ็นต์ใน Database ให้คำนวณจาก Amount/Qty Summary
- ค่า Previous Period เป็นศูนย์ให้แสดง `N/A`
- ต้องแยก Completed Period กับ Same Elapsed Days เพื่อไม่ให้เดือนปัจจุบันดูติดลบเพราะข้อมูลยังไม่ครบ
- Mapping SKU ใช้ Effective Date
- Item/Branch ที่ตั้งไม่ให้แสดงต้องไม่รวมในยอด Summary/KPI ที่ User เห็น
- ภาพรวมทุก MT รวม SKU ด้วย WA Item หลัง Mapping ไม่รวม Source SKU ต่าง MT โดยตรง
- Branch ภาพรวมต้องระบุคู่ `Modern Trade + Source Branch`

### Inventory

Sales สามารถ SUM รายเดือนได้ แต่ Stock ห้าม SUM ข้ามวัน หากทำ Inventory Dashboard ต้องใช้ Month-end/Latest Snapshot หรือ Average Stock และสร้าง `monthly_inventory_snapshot` เมื่อมี Requirement ชัดเจน

## 6. Backup และ Recovery

Backup เป็นแผน Production ยังไม่ได้ Implement ในช่วง Development

หลักการที่ยืนยันแล้ว:

- Backup เก็บบน NAS แยกจาก Database Disk
- Git ใช้กู้ Source Code แต่ไม่สามารถใช้กู้ Database Data
- Database ต้องกู้ด้วย PostgreSQL backup/restore
- ต้องทดสอบ Restore จริง ไม่ถือว่า Backup สำเร็จจากการมีไฟล์เพียงอย่างเดียว
- ก่อน Disk expansion, Migration ขนาดใหญ่ หรือ PostgreSQL upgrade ต้องมี Backup ที่ตรวจสอบแล้ว

รายละเอียด Schedule, Retention, Encryption และ Telegram notification จะกำหนดเมื่อเข้าสู่ Production preparation

## 7. Test Server ปัจจุบัน

- Hostname: `wa-mtpluse-test`
- IP: `192.168.68.129`
- Ubuntu 24.04.4 LTS
- CPU: Intel Core i7-1255U
- RAM: ประมาณ 15 GiB
- Source: `/opt/mtpulse`
- URL: `http://192.168.68.129`
- Docker Engine/PostgreSQL 17/API/Web ทำงานอยู่
- ใช้ `compose.server.yaml`

Test Server ใช้สำหรับ Development/Performance test ไม่ใช่ Production sizing สุดท้าย

## 8. FileShare Phase 1

พัฒนาและ Deploy แล้วใน commit `bfbfcc7 Add admin FileShare connection settings`

- System Settings มี Base UNC, Domain, Username/Password NAS ชุดกลาง
- Profile TWD ใช้ Subfolder `TWD`
- Password เข้ารหัสใน Database
- มีปุ่ม Read-only Connection Test
- ยังไม่มี Scan/Import/Schedule อัตโนมัติ
- Base UNC และ Account จริงยังต้องกรอกจากหน้า System Settings

UNC ที่ยืนยัน:

```text
Base UNC: \\WA-NAS-IT03\FileShare-2\SaleOut_RPT
TWD:      \\WA-NAS-IT03\FileShare-2\SaleOut_RPT\TWD\
TA:       \\WA-NAS-IT03\FileShare-2\SaleOut_RPT\TA\
```

## 9. สิ่งที่ยังไม่ได้อนุญาตให้ดำเนินการ

- ยังไม่สร้างหรือ Format Production Disk
- ยังไม่ย้าย PostgreSQL ไป Production VM
- ยังไม่ Implement Production Backup
- ยังไม่ Implement Scheduled UNC Scan/Import
- ยังไม่ Refactor Fact/Dimension/Partition ตามหัวข้อ 5
- ยังไม่สร้าง Dashboard ภาพรวมทุก MT

ทุกการเปลี่ยนแปลงต้องแก้เฉพาะขอบเขตที่ Product Owner ระบุ และต้องตรวจ Diff ก่อนส่งมอบตาม `MEMORY.md`
