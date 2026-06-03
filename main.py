# -*- coding: utf-8 -*-
"""
โปรแกรมหลัก: เปิดกล้อง USB, ตรวจป้ายทะเบียนไทย, แสดงผลและบันทึก log
Main loop: webcam, plate detection, OCR display, FPS, file log.
"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2

import esp_serial
import line_notify
import plate_utils
import plate_whitelist
import database

database.init_db()

# Cooldown (วินาที) สำหรับป้ายซ้ำ
LOG_COOLDOWN_SEC = 5.0
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"

# มุมเซอร์โวส่งไป ESP เมื่ออ่านป้ายสำเร็จ (และตั้ง ESP_PORT แล้ว)
SERVO_OPEN_DEG = int(os.environ.get("ESP_SERVO_OPEN", "90"))
SERVO_CLOSE_DEG = int(os.environ.get("ESP_SERVO_CLOSE", "0"))


def main() -> None:
    print("กำลังโหลด EasyOCR (ครั้งแรกอาจดาวน์โหลดโมเดล)...")
    reader = plate_utils.create_reader()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ไม่สามารถเปิดกล้อง index 0 ได้ — ตรวจสอบ USB webcam")
        return

    # ประวัติการตรวจจับป้ายทะเบียน
    last_log_time: dict[str, float] = {}

    prev_time = time.perf_counter()
    fps_smooth = 0.0
    fps_alpha = 0.9

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    ser = esp_serial.try_open()

    print("กด 'q' ออก, 's' บันทึกภาพ, 'o' เซอร์โวเปิด, 'c' เซอร์โวปิด (ESP8266 / pyserial)")
    if line_notify.messaging_push_ready():
        print(
            "LINE Messaging API: เปิดอยู่ — plate_whitelist / PLATE_WHITELIST_ALLOW_ALL=1"
        )
    else:
        print(
            "LINE Messaging API: ตั้ง LINE_CHANNEL_ACCESS_TOKEN + LINE_PUSH_TO เพื่อแจ้งเตือน"
        )

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("อ่านเฟรมจากกล้องไม่ได้ — ลองใหม่")
            time.sleep(0.05)
            continue

        now = time.perf_counter()
        dt = now - prev_time
        prev_time = now
        if dt > 0:
            inst_fps = 1.0 / dt
            fps_smooth = fps_alpha * fps_smooth + (1.0 - fps_alpha) * inst_fps if fps_smooth > 0 else inst_fps

        display = frame.copy()
        roi = plate_utils.detect_plate_roi(frame)

        plate_text_display = ""
        if roi is not None:
            x, y, w, h = roi
            # กรอบสีเขียว
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            crop = frame[y : y + h, x : x + w]
            ocr_result = plate_utils.read_plate_text(reader, crop)
            if ocr_result is not None:
                plate_text_display, _conf = ocr_result
                # แสดงข้อความเหนือป้าย
                cv2.putText(
                    display,
                    plate_text_display,
                    (x, max(y - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                ts_wall = time.time()
                if plate_text_display not in last_log_time or (
                    ts_wall - last_log_time[plate_text_display] >= LOG_COOLDOWN_SEC
                ):
                    last_log_time[plate_text_display] = ts_wall
                    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # ตรวจสอบ whitelist
                    wl = plate_whitelist.load_whitelist()
                    allowed = plate_whitelist.should_allow_plate(plate_text_display, wl)

                    # บันทึกฐานข้อมูล SQLite
                    database.add_log(plate_text_display, 1 if allowed else 0, float(_conf))

                    # แจ้ง ESP8266 ด้วยเลขป้ายทะเบียนและสถานะ (เปิด/ปฏิเสธ)
                    esp_serial.send_plate_status(ser, plate_text_display, allowed)

                    # ส่ง LINE Notification (เฉพาะป้ายที่ได้รับอนุญาต)
                    if line_notify.messaging_push_ready() and allowed:
                        msg = f"ป้ายเข้า: {plate_text_display}\n{ts_str}"
                        if not line_notify.send_push_text(msg):
                            print("LINE Push ส่งไม่สำเร็จ (ตรวจ token, LINE_PUSH_TO, เครือข่าย)")
        # ถ้าไม่มี roi — ไม่ทำอะไร (ไม่ crash)

        # FPS มุมซ้ายบน
        fps_label = f"FPS: {fps_smooth:.1f}"
        cv2.putText(
            display,
            fps_label,
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow("Thai License Plate (q=quit, s=screenshot)", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            fname = SCREENSHOT_DIR / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
            cv2.imwrite(str(fname), display)
            print(f"บันทึกภาพ: {fname}")
        if key == ord("o"):
            esp_serial.send_plate_status(ser, "MANUAL OPEN", True)
        if key == ord("c"):
            esp_serial.send_close(ser)

    esp_serial.send_close(ser)
    esp_serial.close(ser)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
