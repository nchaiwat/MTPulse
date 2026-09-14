# MT Pulse — Rules of Development

เอกสารนี้เป็นกฎบังคับสำหรับ AI Agent และ Developer ทุกคนที่ทำงานใน repository นี้ ต้องอ่านก่อนวิเคราะห์ แก้ไข ทดสอบ หรือ Deploy

## 1. Core principles

1. `main` คือ Production baseline และต้องอยู่ในสถานะใช้งานได้เสมอ
2. ห้ามพัฒนางานใหม่บน `main` โดยตรง ให้ใช้ feature branch และ worktree แยก
3. แก้เฉพาะขอบเขตที่ผู้ใช้สั่ง ห้าม refactor, redesign, rename หรือเปลี่ยน Logic ส่วนอื่นโดยพลการ
4. ทุกบรรทัดที่เปลี่ยนต้องอธิบายได้ว่าเกี่ยวข้องกับ requirement ใด
5. เมื่อ requirement กำกวมหรือกระทบ Business Logic, Database หรือ MT อื่น ต้องหยุดและถามก่อน
6. ห้าม Deploy Production, Push เข้า `main`, Import ข้อมูลจริง หรือรัน Database migration โดยไม่มีคำสั่งอนุญาตที่ชัดเจน

## 2. Sources of truth

ให้อ่านเอกสารที่เกี่ยวข้องก่อนลงมือ:

- `AGENTS.md` — กฎการพัฒนาและการส่งมอบ
- `design-system/mt-pulse/MASTER.md` — Design System และ UX/UI invariants
- `design-system/mt-pulse/pages/*.md` — กฎเฉพาะหน้า
- `PROJECT_CONTEXT.md`, `PRD.md`, `implementation_plan.md` — บริบทและ requirement
- `HANDOFF.md` — ประวัติและ operational notes; ข้อมูลเก่าอาจถูกแทนที่ด้วยส่วนที่ใหม่กว่า

ลำดับความสำคัญคือคำสั่งล่าสุดของ Product Owner > กฎในไฟล์นี้ > Design System/page rules > เอกสารเก่า

## 3. Modern Trade package rules

TWD เป็น Master Pattern ด้านโครงสร้างและ interaction แต่ไม่ใช่แหล่ง Business Logic สำหรับทุก MT

เมื่อเพิ่มหรือแก้ MT ต้องพิจารณา package ให้ครบ:

- Dashboard
- Report/Performance
- Data Import
- Monitoring
- Settings, Mapping, Coverage และ Backfill ที่เกี่ยวข้อง

กฎสำคัญ:

- ใช้ Pattern, component และ UX concept เดียวกับ TWD เมื่อ requirement ระบุให้ยึด TWD
- Parser, filename rule, data date, accounting basis, source columns และ reconciliation ต้องอ่านจากไฟล์/เงื่อนไขจริงของ MT นั้น ห้ามเดาหรือ copy Logic TWD
- Item Mapping และ Branch Mapping ต้องแยกตาม MT เว้นแต่ Product Owner ยืนยันว่าใช้ร่วมกัน
- ห้ามแก้ Logic หรือ UX/UI ของ MT อื่นเพื่อทำให้ MT ใหม่ทำงาน
- MT ใหม่ต้องเพิ่มผ่าน shared registry/capability ที่มีอยู่ ไม่ hardcode เฉพาะหน้าโดยไม่จำเป็น
- การตรวจจับ MT, checksum/idempotency และการป้องกัน Upload ผิด MT เป็น data-safety invariant ห้ามลดหรือ bypass
- ห้ามแก้ไข ย้าย เปลี่ยนชื่อ หรือลบไฟล์ต้นฉบับบน NAS/UNC
- TWD คือหน้าเริ่มต้นของระบบ และใช้ชื่อที่แสดงว่า `Thai Watsadu`

## 4. UX/UI invariants

- ห้ามเปลี่ยน layout, workflow, filter, matrix columns, pagination, sticky columns หรือ navigation ที่อยู่นอกขอบเขตงาน
- ใช้ Design System และ shared components เดิมก่อนสร้าง component/CSS ใหม่
- ตารางต้องคง semantic table structure; ห้ามเปลี่ยน `tr` หรือ `td` เป็น grid/flex โดยตรง ให้จัด layout ผ่าน wrapper ภายใน cell
- Matrix รองรับ horizontal scroll ภายใน container โดย App Shell ต้องไม่ล้น viewport
- สถานะต้องสื่อด้วยข้อความ/ตัวเลขร่วมกับสี ไม่ใช้สีอย่างเดียว
- ทุก control ต้องใช้ keyboard ได้ มี accessible name และ visible focus
- ตรวจอย่างน้อยที่ 375, 768, 1024 และ 1440 px เมื่อมีการแก้ layout

## 5. Git workflow

### Protected branches

- `main`: Production เท่านั้น ห้าม Agent push ตรง
- `develop`: Integration/Staging เมื่อทีมเริ่มใช้งานหลาย branch
- Feature branch: งานหนึ่งเรื่องต่อหนึ่ง branch

รูปแบบชื่อที่แนะนำ:

- Codex: `codex/<short-task-name>`
- Antigravity: `antigravity/<short-task-name>`
- Developer: `feature/<short-task-name>` หรือ `fix/<short-task-name>`

เริ่ม branch จาก `origin/main` หรือ integration base ที่ Product Owner ระบุ ห้ามเดา base เอง

### Separate worktree

Agent แต่ละตัวต้องใช้ worktree คนละ directory เพื่อป้องกันไฟล์และ uncommitted changes ชนกัน:

```powershell
git fetch origin
git worktree add ..\MTPulse-antigravity -b antigravity/<task-name> origin/main
```

ห้ามเปิด Agent สองตัวให้แก้ working directory เดียวกัน แม้อยู่คนละ branch

### Commit rules

- Commit ต้องเล็กและมีเรื่องเดียว
- ห้ามรวมไฟล์ชั่วคราว, secrets, database dump, uploaded Excel หรือ pytest temp directories
- ห้ามใช้ `git reset --hard`, force push หรือแก้ history โดยไม่มีคำสั่งชัดเจน
- ห้ามทับหรือลบงานที่มีอยู่แต่ไม่ใช่ของตน

## 6. Required implementation workflow

1. Reproduce หรือระบุ current behavior พร้อมหลักฐาน
2. Trace source/API/database path ที่เกี่ยวข้อง
3. ระบุ assumptions และสิ่งที่จะไม่เปลี่ยน
4. เพิ่มหรือปรับ regression test ให้ fail ด้วยสาเหตุที่ต้องแก้
5. Implement แบบ surgical change
6. รัน focused tests
7. รัน full regression, lint และ production build
8. ตรวจ diff และยืนยันว่าไม่มี unrelated changes
9. สรุป changed files, tests, known risks และ rollback commit

ห้ามสรุปว่า “เสร็จ” จากการมีเมนูหรือ component เท่านั้น ต้องตรวจ end-to-end data path ของ feature นั้น

## 7. Verification gates

Frontend:

```powershell
npm test -- --run
npm run lint
npm run build
```

Backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
```

เลือก focused tests เพิ่มตามไฟล์ที่แก้ แต่ focused tests ไม่ทดแทน full regression ก่อน Merge

ถ้าแก้ shared registry, shared component, importer, mapping, performance query หรือ monitoring ต้อง regression ทุก MT ที่ใช้งานอยู่ ไม่ใช่ตรวจเฉพาะ MT ใหม่

## 8. Database and data safety

- Git rollback ไม่สามารถ rollback ข้อมูล PostgreSQL ได้
- Migration ต้อง additive/backward-compatible เป็นค่าเริ่มต้น
- ห้าม drop table/column, truncate, delete จำนวนมาก หรือแก้ข้อมูล Production โดยไม่มีแผนและการยืนยัน
- ก่อน migration หรือ data correction บน Production ต้องมี backup ที่ตรวจสอบ path, size และ checksum ได้
- Import ต้อง idempotent, audit ได้ และเก็บ source identity/data date ชัดเจน
- ห้ามใช้ Production database ร่วมกันสำหรับการทดลองของหลาย Agent
- งาน parallel ควรใช้ database/container/schema แยก หรือใช้ fixture/test database

## 9. Review before merge

ผู้ตรวจต้องดูทั้ง diff และ actual code path:

```powershell
git log --oneline main..antigravity/<task-name>
git diff --stat main...antigravity/<task-name>
git diff --check main...antigravity/<task-name>
git diff main...antigravity/<task-name>
```

Review checklist:

- Requirement ทุกข้อมี implementation และ test
- ไม่มีไฟล์หรือ refactor นอก scope
- ไม่มี secret, credential, source workbook หรือ generated artifact
- Logic ของ MT อื่นไม่เปลี่ยน
- Database migration ปลอดภัยและมี rollback/backup plan
- UI ใช้ shared pattern และผ่าน visual/accessibility checks
- Full frontend/backend tests ที่เกี่ยวข้องผ่าน
- Staging smoke test ผ่านก่อน Merge เข้า `main`

ใช้ Pull Request เป็นจุด review ที่แนะนำ ห้าม Merge จากข้อความสรุปของ Agent เพียงอย่างเดียว

## 10. Deployment rules

- Deploy Production ได้เฉพาะเมื่อ Product Owner อนุญาตชัดเจน
- Deploy จาก commit/tag ที่ระบุได้ ห้าม Deploy จาก dirty working tree
- Web-only change ให้ rebuild เฉพาะ Web เท่าที่ Compose configuration อนุญาต
- Backend/migration change ต้องตรวจ Alembic head, backup และ API/worker compatibility
- หลัง Deploy ต้องตรวจ commit ปลายทาง, container health, HTTP response และ critical API
- ถ้า smoke test ไม่ผ่าน ให้หยุดและ rollback ไปยัง Production commit/tag ล่าสุดที่ผ่าน

## 11. Agent handoff format

Agent ที่ส่งงานต้องรายงาน:

- Branch และ commit SHA
- Requirement ที่ทำเสร็จ/ยังไม่เสร็จ
- รายการไฟล์ที่เปลี่ยน
- Tests/lint/build ที่รันและผลลัพธ์
- Database migration หรือ data mutation (ถ้ามี)
- วิธีทดสอบบน Staging
- Known risks และ rollback point
- Uncommitted/untracked files ที่ไม่ได้สร้างหรือไม่ได้แตะต้อง

หากข้อมูลใดไม่ทราบ ให้ระบุว่าไม่ทราบ ห้ามเดาหรือสรุปว่าไม่มี
