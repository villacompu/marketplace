from __future__ import annotations
import unicodedata

def normalize_query(s: str) -> str:
    """
    Normaliza texto para búsquedas:
    - case-insensitive (CAFE == cafe)
    - accent-insensitive (café == cafe)
    """
    s = (s or "").strip().casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s
