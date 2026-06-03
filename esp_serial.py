# -*- coding: utf-8 -*-
"""
ส่งคำสั่งไป ESP8266 ผ่าน USB Serial เพื่อควบคุมเซอร์โว
Protocol: ส่งมุมเป็นตัวเลข 0–180 แล้วขึ้นบรรทัดใหม่ (ESP ใช้ Serial.parseInt() ได้สะดวก)

ตั้งค่าผ่านตัวแปรสภาพแวดล้อม (ไม่บังคับ):
  ESP_PORT   — เช่น COM3 (Windows) หรือ /dev/ttyUSB0; ถ้าว่าง = ปิดการใช้ serial
  ESP_BAUD   — default 115200
"""
from __future__ import annotations

import os

import serial


def _port() -> str:
    return os.environ.get("ESP_PORT", "").strip()


def _baud() -> int:
    return int(os.environ.get("ESP_BAUD", "115200"))


def try_open() -> serial.Serial | None:
    """เปิดพอร์ตถ้ามี ESP_PORT; ถ้าไม่ตั้งหรือเปิดไม่ได้ คืน None (ไม่ crash)"""
    port = _port()
    if not port:
        import serial.tools.list_ports
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        print("Serial: ไม่ได้ตั้ง ESP_PORT — ข้ามการเชื่อม ESP8266")
        if available_ports:
            print(f"พอร์ตที่ตรวจพบ: {', '.join(available_ports)}")
            print(f"ลองใช้คำสั่ง: $env:ESP_PORT='{available_ports[0]}'")
        else:
            print("ไม่พบพอร์ต COM ใด ๆ — โปรดตรวจสอบว่าเสียบ ESP8266 หรือยัง")
        return None
    try:
        ser = serial.Serial(port, _baud(), timeout=0.2)
        print(f"Serial: เชื่อม {port} @ {_baud()} baud")
        return ser
    except Exception as e:  # noqa: BLE001 — แสดงข้อความแล้วทำงานต่อได้
        import serial.tools.list_ports
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        print(f"Serial: เปิดพอร์ตไม่ได้ ({port}): {e}")
        if available_ports:
            print(f"พอร์ตที่มีในระบบ: {', '.join(available_ports)}")
        return None


def send_servo_angle(ser: serial.Serial | None, angle: int) -> bool:
    """
    ส่งมุมเซอร์โว 0–180 เป็น ASCII บรรทัดเดียว (เช่น b'90\\n')
    คืน True ถ้าส่งได้
    """
    if ser is None or not ser.is_open:
        return False
    a = max(0, min(180, int(angle)))
    try:
        ser.write(f"{a}\n".encode("ascii", errors="ignore"))
        ser.flush()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Serial: ส่งคำสั่งไม่ได้: {e}")
        return False


def send_plate_status(ser: serial.Serial | None, plate: str, allowed: bool) -> bool:
    """
    ส่งเลขป้ายทะเบียนและสถานะการอนุญาตไปที่ ESP8266
    Protocol: ส่ง "OPEN:<plate>\n" หรือ "DENIED:<plate>\n"
    """
    if ser is None or not ser.is_open:
        return False
    prefix = "OPEN" if allowed else "DENIED"
    cmd = f"{prefix}:{plate}\n"
    try:
        ser.write(cmd.encode("utf-8", errors="ignore"))
        ser.flush()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Serial: ส่งสถานะป้ายไม่ได้: {e}")
        return False


def send_close(ser: serial.Serial | None) -> bool:
    """
    ส่งคำสั่งปิดไม้กั้นไปที่ ESP8266
    Protocol: ส่ง "CLOSE\n"
    """
    if ser is None or not ser.is_open:
        return False
    try:
        ser.write(b"CLOSE\n")
        ser.flush()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Serial: ส่งคำสั่งปิดไม้กั้นไม่ได้: {e}")
        return False


def close(ser: serial.Serial | None) -> None:
    if ser is not None and ser.is_open:
        try:
            ser.close()
        except Exception:
            pass
