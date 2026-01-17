# services/featured.py
from __future__ import annotations

def _ensure_featured(db: dict) -> dict:
    db.setdefault("featured", {})
    db["featured"].setdefault("products", [])
    db["featured"].setdefault("profiles", [])
    return db["featured"]

def get_featured_products(db: dict) -> list[str]:
    f = _ensure_featured(db)
    return list(f.get("products", []) or [])

def get_featured_profiles(db: dict) -> list[str]:
    f = _ensure_featured(db)
    return list(f.get("profiles", []) or [])

def set_featured_products(db: dict, product_ids: list[str], max_n: int = 12) -> None:
    f = _ensure_featured(db)
    # únicos y recortado
    uniq = []
    seen = set()
    for pid in product_ids or []:
        if pid and pid not in seen:
            uniq.append(pid)
            seen.add(pid)
    f["products"] = uniq[:max_n]

def set_featured_profiles(db: dict, profile_ids: list[str], max_n: int = 12) -> None:
    f = _ensure_featured(db)
    uniq = []
    seen = set()
    for pid in profile_ids or []:
        if pid and pid not in seen:
            uniq.append(pid)
            seen.add(pid)
    f["profiles"] = uniq[:max_n]
