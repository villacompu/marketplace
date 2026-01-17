from __future__ import annotations
import re

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def safe_text(s: str, max_len: int = 5000) -> str:
    s = (s or "").strip()
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
    return s[:max_len]
