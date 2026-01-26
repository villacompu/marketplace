from __future__ import annotations
import re
import html

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def safe_text(s: str, max_len: int = 5000) -> str:
    s = (s or "").strip()
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
    return s[:max_len]

def safe_html(s: str, max_len: int = 5000) -> str:
    return html.escape(safe_text(s, max_len), quote=True)

def safe_html_multiline(s: str, max_len: int = 5000) -> str:
    """
    Para texto pegado de web: escapa HTML y convierte saltos de línea a <br>.
    También normaliza bullets para que no active markdown-lists.
    """
    t = safe_text(s, max_len)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # normaliza bullets comunes pegados de web
    t = t.replace("•", "·")
    esc = html.escape(t, quote=True)
    return esc.replace("\n", "<br/>")