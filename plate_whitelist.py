"""Simple whitelist storage and matching for license plates using SQLite."""

from __future__ import annotations

import os
import database


def _normalize(plate: str) -> str:
    return "".join(plate.upper().split())


def load_whitelist() -> set[str]:
    return database.load_whitelist()


def add_plate(plate: str) -> set[str]:
    database.add_plate(_normalize(plate))
    return load_whitelist()


def remove_plate(plate: str) -> set[str]:
    database.remove_plate(_normalize(plate))
    return load_whitelist()


def should_allow_plate(plate: str, whitelist: set[str] | None = None) -> bool:
    """Allow all when PLATE_WHITELIST_ALLOW_ALL=1, otherwise require whitelist match."""
    if os.environ.get("PLATE_WHITELIST_ALLOW_ALL", "0").strip() == "1":
        return True
    wl = whitelist if whitelist is not None else load_whitelist()
    return _normalize(plate) in wl
