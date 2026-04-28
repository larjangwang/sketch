# AI Construction Drawing Assistant

Local-first Windows desktop MVP สำหรับช่วยสถาปนิกและวิศวกรไทยจัดการงานจาก sketch ไปสู่ชุดแบบก่อสร้างฉบับร่าง โดยเน้นการเก็บไฟล์ในเครื่อง, ใช้ SQLite, และเชื่อม Gemini API เป็นผู้ช่วยอ่านแบบ/ตรวจ checklist

## แนวทางเวอร์ชันแรก

- รันบน Windows โดยตรง ไม่ต้องใช้ NAS และไม่ต้องมี server
- เก็บ project, sketch, generated files, exports และ revisions ใน `Documents/AI-Construction-Drawing`
- ใช้ SQLite เป็นฐานข้อมูล local
- ใช้ Gemini API key จากผู้ใช้ในหน้า Settings
- ให้ AI สรุป/อ่าน sketch เป็น structured JSON แล้วให้ผู้ใช้ตรวจยืนยันก่อนสร้าง output
- Export MVP เป็น drawing index, HTML summary, DXF placeholder และ PDF summary เบื้องต้น
- เตรียมโครง Inno Setup installer สำหรับแพ็กเป็น `Setup.exe`

> หมายเหตุ: output จาก AI เป็น draft เท่านั้น ต้องให้สถาปนิก/วิศวกรผู้มีใบอนุญาตตรวจและรับรองก่อนยื่นราชการ

## Run Locally

เปิด PowerShell ที่โฟลเดอร์นี้ แล้วรัน:

```powershell
.\scripts\run.ps1
```

หรือรันตรงด้วย Python:

```powershell
$env:PYTHONPATH = "src"
python -m sketch_assistant
```

## Test

```powershell
.\scripts\test.ps1
```

## Gemini API

1. เปิดแอป
2. ไปที่แท็บ `Settings`
3. ใส่ Gemini API key และ model เช่น `gemini-2.5-flash`
4. กด Save Settings

API key จะถูกเก็บใน user profile ของ Windows ไม่ถูก commit ลง source code

## Installer

โครง installer อยู่ที่ `installer/` ใช้แนวทาง:

```powershell
.\installer\build.ps1
```

สคริปต์จะพยายามใช้ PyInstaller เพื่อสร้าง `.exe` และเรียก Inno Setup (`ISCC.exe`) ถ้ามีติดตั้งในเครื่อง

## Project Structure

```text
src/sketch_assistant/       Desktop app, local DB, Gemini service, exporters
src/sketch_assistant/resources/checklists/
worker/                    CLI worker สำหรับทดลอง extract sketch
installer/                 Inno Setup script และ build script
scripts/                   run/test helper scripts
tests/                     unittest-based tests
docs/                      product and implementation notes
```

## Next Implementation Milestones

1. เพิ่ม canvas editor สำหรับตรวจ scale, wall, opening, room และ dimension
2. เพิ่ม PDF/DXF exporter จริงจาก geometry model
3. เพิ่ม template engine สำหรับ title block, sheet index, symbol และ layer standard
4. เพิ่ม professional review workflow และ revision compare
5. เพิ่ม auto-update/installer signing เมื่อเริ่มใช้งานนอกเครื่องพัฒนา
