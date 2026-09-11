# -*- coding: utf-8 -*-
"""
โมดูลตรวจจับกรอบป้ายทะเบียนและอ่านข้อความด้วย EasyOCR
Plate detection (contours) + OCR utilities for Thai license plates.
"""

from __future__ import annotations

import re
from typing import Any

import cv2
import numpy as np

# รูปแบบป้ายไทย: พยัญชนะไทย 1-3 ตัว + ตัวเลข 1-4 ตัว (ชื่อจังหวัดตัดออกจาก regex หลักเพื่อความเสถียร)
THAI_PLATE_PATTERN = re.compile(r"[ก-ฮ]{1,3}\s*\d{1,4}")

# อัตราส่วนป้ายทะเบียนโดยประมาณ (กว้าง:สูง) ~ 2:1 ถึง 5:1
ASPECT_MIN = 2.0
ASPECT_MAX = 5.0
MIN_CONTOUR_AREA = 2000
OCR_CONFIDENCE_THRESHOLD = 0.5


def create_reader() -> Any:
    """สร้าง EasyOCR reader — ไทย + อังกฤษ, ปิด GPU เพื่อความเข้ากันได้"""
    import easyocr

    return easyocr.Reader(["th", "en"], gpu=False, verbose=False)


def _filter_plate_text(raw: str) -> str | None:
    """คัดเฉพาะข้อความที่ตรงรูปแบบป้ายไทย"""
    s = raw.strip()
    if not s:
        return None
    m = THAI_PLATE_PATTERN.search(s)
    if m:
        return m.group(0).strip()
    # ลองตัดช่องว่างแปลก ๆ
    compact = re.sub(r"\s+", "", s)
    m2 = THAI_PLATE_PATTERN.search(compact)
    if m2:
        return m2.group(0).strip()
    return None


def _plate_characters(raw: str) -> str:
    """เก็บเฉพาะอักษรไทยและตัวเลขที่เป็นไปได้ในเลขทะเบียน"""
    return "".join(ch for ch in raw.upper() if "ก" <= ch <= "ฮ" or ch.isdigit())


def _bbox_center_x(bbox: Any) -> float:
    """หาค่า x กึ่งกลางของ OCR bounding box เพื่อเรียงข้อความจากซ้ายไปขวา"""
    try:
        xs = [float(point[0]) for point in bbox]
        return sum(xs) / len(xs) if xs else 0.0
    except (TypeError, ValueError, IndexError):
        return 0.0


def detect_plate_roi(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    หา ROI ป้ายทะเบียนจากเฟรม:
    grayscale -> bilateral -> Canny -> contours -> กรอง aspect ratio และพื้นที่
    คืน (x, y, w, h) หรือ None ถ้าไม่พบ
    """
    if frame is None or frame.size == 0:
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # bilateral ลดสัญญาณรบกวนโดยยังเก็บขอบ
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(blur, 30, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    h_frame, w_frame = frame.shape[:2]
    best: tuple[float, tuple[int, int, int, int]] | None = None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CONTOUR_AREA:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        x, y, w, h = cv2.boundingRect(approx)

        if h <= 0 or w <= 0:
            continue
        aspect = w / float(h)
        if not (ASPECT_MIN <= aspect <= ASPECT_MAX):
            continue

        # อยู่ในกรอบภาพ
        x = max(0, min(x, w_frame - 1))
        y = max(0, min(y, h_frame - 1))
        w = min(w, w_frame - x)
        h = min(h, h_frame - y)
        if w < 10 or h < 10:
            continue

        score = area
        if best is None or score > best[0]:
            best = (score, (x, y, w, h))

    return best[1] if best else None


def read_plate_text(reader: Any, plate_bgr: np.ndarray) -> tuple[str, float] | None:
    """
    รัน EasyOCR เฉพาะบริเวณ crop ของป้าย
    คืน (ข้อความที่ผ่าน regex, confidence ของข้อความที่ประกอบแล้ว) หรือ None

    OCR สามารถแบ่งทะเบียนออกเป็นหลาย bounding boxes ได้ เช่น "กข" และ "1234".
    จึงต้องประกอบ candidate จากทุก box ก่อนใช้ confidence threshold กับผลลัพธ์สุดท้าย
    ไม่ควรทิ้ง component เพียงเพราะ confidence ของ component นั้นต่ำกว่า threshold.
    """
    if plate_bgr is None or plate_bgr.size == 0:
        return None

    rgb = cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2RGB)
    results = reader.readtext(rgb, detail=1)

    best_text: str | None = None
    best_conf = 0.0

    # ตรวจแต่ละ box ก่อน เผื่อ EasyOCR คืนทะเบียนครบในกล่องเดียว
    for item in results:
        if len(item) < 3:
            continue
        _bbox, text, conf = item[0], item[1], float(item[2])
        cleaned = _filter_plate_text(text)
        if cleaned and conf >= OCR_CONFIDENCE_THRESHOLD and conf > best_conf:
            best_text = cleaned
            best_conf = conf

    # สำคัญ: เก็บทุก box ที่มีอักษรไทย/ตัวเลขก่อน ไม่กรองด้วย confidence รายกล่อง
    # เพราะทะเบียนเดียวกันอาจถูก EasyOCR แยกเป็นหลายกล่องและมี confidence ไม่เท่ากัน
    candidates: list[tuple[float, str]] = []
    for item in results:
        if len(item) < 3:
            continue
        bbox, text, conf = item[0], str(item[1]), float(item[2])
        chars = _plate_characters(text)
        if chars:
            candidates.append((_bbox_center_x(bbox), chars))

    candidates.sort(key=lambda candidate: candidate[0])
    if candidates:
        combined = "".join(text for _, text in candidates)
        merged_clean = _filter_plate_text(combined)

        if merged_clean:
            # ใช้ค่าเฉลี่ย confidence ของทุก component ที่นำมาประกอบ
            # และให้ threshold ตัดสินหลังจากประกอบทะเบียนแล้ว
            component_confidences = [
                float(item[2])
                for item in results
                if len(item) >= 3 and _plate_characters(str(item[1]))
            ]
            avg_conf = sum(component_confidences) / len(component_confidences)
            if avg_conf >= OCR_CONFIDENCE_THRESHOLD and (
                best_text is None or len(merged_clean) >= len(best_text)
            ):
                best_text = merged_clean
                best_conf = avg_conf

    if best_text is None:
        return None
    return (best_text, best_conf)
