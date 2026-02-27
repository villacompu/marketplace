# services/media_urls.py
from __future__ import annotations
import re
from urllib.parse import urlparse, parse_qs

_DRIVE_FILE_D_RE = re.compile(r"https?://drive\.google\.com/file/d/([^/]+)", re.I)
_DRIVE_OPEN_ID_RE = re.compile(r"https?://drive\.google\.com/open", re.I)
_DRIVE_UC_RE = re.compile(r"https?://drive\.google\.com/uc", re.I)
_DRIVE_FOLDER_RE = re.compile(r"https?://drive\.google\.com/drive/folders/", re.I)

def extract_drive_file_id(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""

    # si es carpeta, no sirve como imagen directa
    if _DRIVE_FOLDER_RE.search(u):
        return ""

    m = _DRIVE_FILE_D_RE.search(u)
    if m:
        return m.group(1).strip()

    # open?id=...
    if _DRIVE_OPEN_ID_RE.search(u):
        try:
            qs = parse_qs(urlparse(u).query)
            fid = (qs.get("id") or [""])[0].strip()
            return fid
        except Exception:
            return ""

    # uc?...&id=...
    if _DRIVE_UC_RE.search(u):
        try:
            qs = parse_qs(urlparse(u).query)
            fid = (qs.get("id") or [""])[0].strip()
            return fid
        except Exception:
            return ""

    return ""

def normalize_image_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""

    fid = extract_drive_file_id(u)
    if fid:
        return f"https://lh3.googleusercontent.com/d/{fid}"

    return u

def normalize_many(urls: list[str], max_n: int | None = None) -> list[str]:
    out: list[str] = []
    for x in (urls or []):
        nx = normalize_image_url(x)
        if nx:
            out.append(nx)
        if max_n and len(out) >= max_n:
            break
    return out