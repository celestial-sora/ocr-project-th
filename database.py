# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ocr_project.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """สร้างตาราง whitelist และ plates_log ถ้ายังไม่มี พร้อมทั้งย้ายข้อมูลเดิม"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT UNIQUE NOT NULL,
                owner_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plates_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_allowed INTEGER NOT NULL,
                confidence REAL
            )
        """)
        conn.commit()

        # ย้ายข้อมูล (Migration) จาก whitelist_plates.txt เก่า
        txt_path = Path(__file__).resolve().parent / "whitelist_plates.txt"
        if txt_path.exists():
            try:
                lines = txt_path.read_text(encoding="utf-8").splitlines()
                plates = [
                    "".join(line.strip().upper().split())
                    for line in lines
                    if line.strip()
                ]
                for p in plates:
                    conn.execute(
                        "INSERT OR IGNORE INTO whitelist (plate_number) VALUES (?)",
                        (p,),
                    )
                conn.commit()
                # เปลี่ยนชื่อไฟล์เดิมเป็น .bak เพื่อไม่ให้รันย้ายข้อมูลซ้ำ
                backup_path = txt_path.with_suffix(".txt.bak")
                txt_path.rename(backup_path)
                print(
                    f"Database: ย้ายข้อมูลสำเร็จและเปลี่ยนชื่อ {txt_path.name} -> {backup_path.name}"
                )
            except Exception as e:
                print(f"Database Migration Error: {e}")
    finally:
        conn.close()


def load_whitelist() -> set[str]:
    conn = get_db()
    try:
        cursor = conn.execute("SELECT plate_number FROM whitelist")
        return {row["plate_number"] for row in cursor.fetchall()}
    finally:
        conn.close()


def add_plate(plate: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO whitelist (plate_number) VALUES (?)",
            (plate,),
        )
        conn.commit()
    finally:
        conn.close()


def remove_plate(plate: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM whitelist WHERE plate_number = ?",
            (plate,),
        )
        conn.commit()
    finally:
        conn.close()


def add_log(plate: str, is_allowed: int, confidence: float) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO plates_log (plate_number, is_allowed, confidence) VALUES (?, ?, ?)",
            (plate, is_allowed, confidence),
        )
        conn.commit()
    finally:
        conn.close()


def get_logs(limit: int = 50) -> list[dict]:
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT id, plate_number, timestamp, is_allowed, confidence FROM plates_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def clear_logs() -> None:
    conn = get_db()
    try:
        conn.execute("DELETE FROM plates_log")
        conn.commit()
    finally:
        conn.close()


# Auto-initialize database on import
init_db()
