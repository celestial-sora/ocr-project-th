# OCR Barrier Gate — ระบบเปิด-ปิดไม้กั้นอัตโนมัติด้วย OCR

> Automatic vehicle license plate recognition system for barrier gate control  
> ระบบอ่านทะเบียนรถอัตโนมัติเพื่อควบคุมไม้กั้นประตู

---
<!-- if you're reading this, you're a nerd :D -->
## 📋 ภาพรวม / Overview

ระบบนี้ใช้ **EasyOCR** + **YOLO** เพื่ออ่านทะเบียนรถจากกล้อง แล้วเปรียบเทียบกับ whitelist ในฐานข้อมูล SQLite — ถ้าตรง จะส่งคำสั่งไปยัง **ESP8266** ผ่าน Serial เพื่อเปิดไม้กั้น พร้อมแสดงผลสถานะบนหน้าจอ OLED และแจ้งเตือนผ่าน **LINE Messaging API**

This system uses **EasyOCR** + **YOLO** to read license plates from a camera, compares them against a SQLite whitelist database, then sends a command to an **ESP8266** via Serial to open the barrier gate, displaying status on an OLED screen, with **LINE Messaging API** notifications.

---

## ✨ ฟีเจอร์ / Features

- อ่านทะเบียนรถแบบ Real-time ผ่านกล้อง
- ตรวจจับป้ายทะเบียนด้วย YOLO11n
- OCR ด้วย EasyOCR (รองรับภาษาไทย + อังกฤษ)
- ระบบ Whitelist จัดเก็บในฐานข้อมูล SQLite
- ควบคุม ESP8266 ผ่าน Serial (พร้อมควบคุม Servo Motor และแสดงผลบนหน้าจอ OLED)
- แจ้งเตือนผ่าน LINE ทุกครั้งที่ป้ายได้รับอนุญาตผ่านด่าน
- Web UI Dashboard สำหรับจัดการ whitelist (เพิ่ม/ลบ) และดูประวัติการสแกน (Logs)
- บันทึกประวัติการตรวจจับทะเบียนพร้อมความมั่นใจ (Confidence Score) และเวลาอัตโนมัติ

---

## Tech Stack

| Component | Technology |
|---|---|
| Object Detection | YOLO11n |
| OCR | EasyOCR |
| Backend | Python |
| Web UI | Flask |
| Database | SQLite |
| Microcontroller | ESP8266 (Arduino) |
| Notification | LINE Messaging API |
| Serial Comm | pyserial |

---

## โครงสร้างไฟล์ / File Structure

```
ocr-project-th/
├── main.py              # Main loop — camera + OCR + serial
├── app.py               # Flask web UI
├── database.py          # SQLite database connection & migration
├── plate_utils.py       # OCR & plate processing logic
├── plate_whitelist.py   # Whitelist matching via SQLite
├── esp_serial.py        # ESP8266 serial communication
├── line_notify.py       # LINE Messaging API
├── app_secrets.py       # API credentials (gitignored)
├── ocr_project.db       # SQLite database (gitignored, auto-created)
├── requirements.txt     # Python dependencies
├── static/              # Web UI assets (HTML dashboard, JS & CSS)
└── templates/           # Flask HTML templates (index.html)
```

---

## การติดตั้ง / Installation

```bash
# 1. Clone repo
git clone https://github.com/celestial-sora/ocr-project-th.git
cd ocr-project-th

# 2. สร้าง virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. ติดตั้ง dependencies
pip install -r requirements.txt

# 4. ตั้งค่า API credentials
# สร้างไฟล์ app_secrets.py แล้วใส่ข้อมูลด้านล่าง
```

---

## การตั้งค่า / Configuration

สร้างไฟล์ `app_secrets.py` (ไม่ถูก commit ขึ้น git):

```python
LINE_CHANNEL_ACCESS_TOKEN = "your_line_token_here"
LINE_PUSH_TO = "Uxxxxxxxxxxxxxxxxx"  # LINE userId
```

ตั้งค่า ESP_PORT ใน environment:
```bash
# Windows
set ESP_PORT=COM3

# Linux
export ESP_PORT=/dev/ttyUSB0
```

---

## การใช้งาน / Usage

```bash
# รัน main system
python main.py

# รัน web UI (แยก terminal)
python app.py
```

Web UI จะเปิดที่ `http://localhost:5000`

---

## LINE Notification

ระบบจะส่งข้อความแจ้งเตือนไปยัง LINE ทุกครั้งที่:
- ทะเบียนอยู่ใน whitelist → เปิดไม้กั้น
- ทะเบียนไม่อยู่ใน whitelist → ปฏิเสธ

---

## Requirements

```
easyocr
ultralytics. Fake
pyserial
flask
opencv-python
torch
```

ดูรายละเอียดทั้งหมดใน `requirements.txt`

---

## 👤 Author

**Sorachan** — [@celestial-sora](https://github.com/celestial-sora)
