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
import time

import serial
import serial.tools.list_ports


def _port() -> str:
    port = os.environ.get("ESP_PORT", "").strip()
    if port:
        return port
    # Auto-detect USB Serial ports on Linux/Windows
    import glob
    usb_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if usb_ports:
        return usb_ports[0]
    return ""


def _baud() -> int:
    return int(os.environ.get("ESP_BAUD", "115200"))


HANDSHAKE_QUERY = b"PING:OCR_CONTROLLER\n"
HANDSHAKE_EXPECTED = "PONG:OCR_GATE"


def _verify_device(ser: serial.Serial) -> bool:
    """ส่งข้อความ Handshake เพื่อยืนยันว่าปลายทางคือบอร์ด ESP8266 ของโปรเจกต์นี้จริง"""
    try:
        # รอให้ชิปเสถียรหลังเปิดพอร์ต (หลีกเลี่ยง DTR reset glitch)
        time.sleep(1.0)
        ser.reset_input_buffer()
        ser.write(HANDSHAKE_QUERY)
        ser.flush()
        
        # รออ่านผลตอบกลับ
        time_start = time.time()
        while time.time() - time_start < 1.5:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if HANDSHAKE_EXPECTED in line:
                    return True
            time.sleep(0.05)
        return False
    except Exception:
        return False


def try_open() -> serial.Serial | None:
    """
    เชื่อมต่อพอร์ตอัตโนมัติ พร้อมทำ Handshake Verify ป้องกันการเชื่อมต่อผิดอุปกรณ์
    คืน object serial.Serial หรือ None ถ้าไม่พบบอร์ดที่ถูกต้อง
    """
    manual_port = os.environ.get("ESP_PORT", "").strip()
    baud = _baud()

    # ถ้ากำหนด ESP_PORT แบบเจาะจง
    if manual_port:
        try:
            ser = serial.Serial(manual_port, baud, timeout=0.5)
            time.sleep(0.2)
            if _verify_device(ser):
                print(f"Serial: ยืนยันอุปกรณ์ถูกต้องบน {manual_port} @ {baud} baud")
                return ser
            print(f"Serial: {manual_port} เปิดได้แต่ไม่ผ่านการ Verify (ไม่ใช่บอร์ด OCR Gate)")
            ser.close()
            return None
        except Exception as e:
            print(f"Serial: เปิดพอร์ต {manual_port} ไม่ได้: {e}")
            return None

    # สแกนหาพอร์ต USB Serial อัตโนมัติ
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    if not available_ports:
        print("Serial: ไม่พบพอร์ตเชื่อมต่อใด ๆ ในระบบ")
        return None

    print(f"Serial: กำลังสแกนและ Verify พอร์ตอัตโนมัติ ({len(available_ports)} พอร์ต)...")
    for port in available_ports:
        # กรองเฉพาะพอร์ตประเภท USB / ACM
        if not ("USB" in port or "ACM" in port or "COM" in port):
            continue
        try:
            ser = serial.Serial(port, baud, timeout=0.5)
            time.sleep(0.3)
            if _verify_device(ser):
                print(f"Serial: ตรวจพบและ Verify สำเร็จ! เชื่อมต่อ {port} @ {baud} baud")
                return ser
            ser.close()
        except Exception:
            continue

    print("Serial: สแกนเสร็จสิ้น ไม่พบบอร์ด ESP8266 ที่ตอบรับ Verify Handshake")
    return None


# ── Connection Manager & Auto-Reconnect ──
_active_ser: serial.Serial | None = None


def get_connection(force_reconnect: bool = False) -> serial.Serial | None:
    """คืน Serial instance ที่พร้อมใช้งาน ถ้าหลุดหรือปิดอยู่จะ Auto-Reconnect และ Verify ทันที"""
    global _active_ser
    if force_reconnect and _active_ser is not None:
        try:
            _active_ser.close()
        except Exception:
            pass
        _active_ser = None

    if _active_ser is not None and _active_ser.is_open:
        return _active_ser

    # ถ้ายังไม่ได้ต่อ หรือหลุดไป ให้ลองต่อใหม่แบบ Verify
    print("Serial: กำลังพยายามเชื่อมต่อใหม่ (Auto-Reconnect)...")
    _active_ser = try_open()
    return _active_ser


def _safe_write(data: bytes, ser: serial.Serial | None = None, retries: int = 2) -> bool:
    """ส่งข้อมูลไปยังบอร์ด พร้อมระบบ Auto-Reconnect อัตโนมัติหากบอร์ดไฟตก/รีเซ็ตตัว"""
    global _active_ser
    current_ser = ser if (ser is not None and ser.is_open) else _active_ser

    for attempt in range(retries + 1):
        if current_ser is None or not current_ser.is_open:
            print(f"Serial: พอร์ตหลุด กำลังต่อบอร์ดใหม่ (ครั้งที่ {attempt + 1}/{retries + 1})...")
            # รอ 1 วินาทีให้ชิป USB Re-enumerate หลัง Brownout Reset
            time.sleep(1.0)
            current_ser = get_connection(force_reconnect=True)
            if current_ser is None:
                continue

        try:
            current_ser.write(data)
            current_ser.flush()
            _active_ser = current_ser
            return True
        except Exception as e:
            print(f"Serial: ส่งข้อมูลล้มเหลว ({e}) กำลัง Reconnect...")
            try:
                current_ser.close()
            except Exception:
                pass
            current_ser = None
            _active_ser = None

    return False


def send_servo_angle(ser: serial.Serial | None, angle: int) -> bool:
    """
    ส่งมุมเซอร์โว 0–180 เป็น ASCII บรรทัดเดียว (เช่น b'80\\n')
    มีระบบ Auto-Reconnect ถ้าบอร์ดรีเซ็ตตัวเอง
    """
    a = max(0, min(180, int(angle)))
    return _safe_write(f"{a}\n".encode("ascii", errors="ignore"), ser=ser)


def send_plate_status(ser: serial.Serial | None, plate: str, allowed: bool) -> bool:
    """
    ส่งเลขป้ายทะเบียนและสถานะการอนุญาตไปที่ ESP8266
    Protocol: ส่ง "OPEN:<plate>\\n" หรือ "DENIED:<plate>\\n"
    มีระบบ Auto-Reconnect ถ้าบอร์ดรีเซ็ตตัวเอง
    """
    prefix = "OPEN" if allowed else "DENIED"
    cmd = f"{prefix}:{plate}\n"
    return _safe_write(cmd.encode("utf-8", errors="ignore"), ser=ser)


def send_close(ser: serial.Serial | None) -> bool:
    """ส่งคำสั่งปิดไม้กั้นไปที่ ESP8266 พร้อม Auto-Reconnect"""
    return _safe_write(b"CLOSE\n", ser=ser)


def send_idle(ser: serial.Serial | None) -> bool:
    """ส่งสถานะ IDLE (ไม่มีรถ / ไม่พบบัตร) ปิดไม้กั้นไปที่ 0 องศา พร้อม Auto-Reconnect"""
    return _safe_write(b"IDLE\n", ser=ser)


def get_device_status(ser: serial.Serial | None = None) -> dict:
    """
    ตรวจสอบสถานะการเชื่อมต่อและสถานะไม้กั้นของ ESP8266
    รักษาการเชื่อมต่อแบบ Persistent ไม่เปิด/ปิดพอร์ตบ่อยๆ เพื่อป้องกันชิปรีเซ็ต
    """
    global _active_ser
    current_ser = ser if (ser is not None and ser.is_open) else _active_ser

    if current_ser is None or not current_ser.is_open:
        current_ser = get_connection()
        if not current_ser:
            return {
                "connected": False,
                "port": None,
                "gate": "DISCONNECTED",
                "angle": 0,
                "remaining_sec": 0,
            }
        _active_ser = current_ser

    try:
        current_ser.reset_input_buffer()
        current_ser.write(b"STATUS\n")
        current_ser.flush()
        t0 = time.time()
        status_line = ""
        while time.time() - t0 < 0.4:
            if current_ser.in_waiting:
                line = current_ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("STATUS:"):
                    status_line = line
                    break
            time.sleep(0.02)

        # รูปแบบ STATUS:<OPEN|CLOSED>:<angle>:<remaining_sec>
        gate = "CLOSED"
        angle = 0
        rem = 0
        if status_line:
            parts = status_line.split(":")
            if len(parts) >= 4:
                gate = parts[1]
                angle = int(parts[2])
                rem = int(parts[3])

        return {
            "connected": True,
            "port": current_ser.port,
            "gate": gate,
            "angle": angle,
            "remaining_sec": rem,
        }
    except Exception as e:
        # เกิด Error สื่อสารไม่ได้ ให้เคลียร์ทิ้งเพื่อให้รอบถัดไป Reconnect
        try:
            current_ser.close()
        except Exception:
            pass
        _active_ser = None
        return {
            "connected": False,
            "port": getattr(current_ser, "port", None),
            "gate": "DISCONNECTED",
            "angle": 0,
            "remaining_sec": 0,
        }


def close(ser: serial.Serial | None) -> None:
    if ser is not None and ser.is_open:
        try:
            ser.close()
        except Exception:
            pass
