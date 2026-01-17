# services/analytics.py
from __future__ import annotations

from datetime import datetime
import re
import uuid
import streamlit as st


MAX_EVENTS = 5000


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_anon_id(session_state: dict) -> str:
    session_state.setdefault("anon_id", str(uuid.uuid4()))
    return session_state["anon_id"]


def _sanitize_query(q: str, max_len: int = 120) -> str:
    """
    Evita guardar datos sensibles por accidente.
    - Reemplaza emails y teléfonos por tokens.
    - Recorta longitud.
    """
    q = (q or "").strip()
    if not q:
        return ""

    # emails
    q = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "<email>", q, flags=re.I)
    # teléfonos (muy aproximado)
    q = re.sub(r"\+?\d[\d\s().-]{6,}\d", "<phone>", q)

    q = " ".join(q.split())
    return q[:max_len]


def track_event(
    db: dict,
    *,
    event_type: str,
    user_id: str | None = None,
    anon_id: str | None = None,
    product_id: str | None = None,
    profile_id: str | None = None,
    meta: dict | None = None,
) -> None:
    """
    Guarda eventos básicos (MVP).
    - NO guardamos IP
    - NO guardamos info sensible
    - Mantiene un máximo para que el JSON no crezca infinito

    Compat:
    - Guardamos `type` y también `event` con el mismo valor.
    """
    db.setdefault("events", [])
    db["events"].append({
        "ts": _now_iso(),
        "type": event_type,   # ✅ recomendado para stats
        "event": event_type,  # ✅ compat con lo viejo (si ya lo usabas)
        "user_id": user_id or "",
        "anon_id": anon_id or "",
        "product_id": product_id or "",
        "profile_id": profile_id or "",
        "meta": meta or {},
    })

    if len(db["events"]) > MAX_EVENTS:
        db["events"] = db["events"][-MAX_EVENTS:]


def track_event_once(
    db: dict,
    *,
    dedupe_key: str,
    event_type: str,
    user_id: str | None = None,
    anon_id: str | None = None,
    product_id: str | None = None,
    profile_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    """
    Dedup por sesión: evita duplicados por rerun.
    Retorna True si se registró el evento, False si fue deduplicado.
    """
    st.session_state.setdefault("_analytics_dedupe", set())
    k = f"{event_type}|{dedupe_key}"
    if k in st.session_state["_analytics_dedupe"]:
        return False

    st.session_state["_analytics_dedupe"].add(k)
    track_event(
        db,
        event_type=event_type,
        user_id=user_id,
        anon_id=anon_id,
        product_id=product_id,
        profile_id=profile_id,
        meta=meta,
    )
    return True


# Helpers listos para usar (para que el código quede limpio)
def log_view_home(db: dict, *, user_id: str | None = None) -> bool:
    anon = get_anon_id(st.session_state)
    return track_event_once(db, dedupe_key="home", event_type="view_home", user_id=user_id, anon_id=anon)


def log_view_product(db: dict, *, product_id: str, profile_id: str | None = None, user_id: str | None = None) -> bool:
    anon = get_anon_id(st.session_state)
    return track_event_once(
        db,
        dedupe_key=f"product:{product_id}",
        event_type="view_product",
        user_id=user_id,
        anon_id=anon,
        product_id=product_id,
        profile_id=profile_id,
    )


def log_view_profile(db: dict, *, profile_id: str, user_id: str | None = None) -> bool:
    anon = get_anon_id(st.session_state)
    return track_event_once(
        db,
        dedupe_key=f"profile:{profile_id}",
        event_type="view_profile",
        user_id=user_id,
        anon_id=anon,
        profile_id=profile_id,
    )


def log_search(db: dict, *, q: str, filters: dict | None = None, results_n: int | None = None, user_id: str | None = None) -> bool:
    anon = get_anon_id(st.session_state)
    meta = {"q": _sanitize_query(q), "filters": (filters or {}), "results_n": results_n}
    # dedupe por “misma búsqueda aplicada” en sesión (evita reruns)
    sig = f"{meta['q']}|{meta.get('filters')}"
    return track_event_once(db, dedupe_key=f"search:{sig}", event_type="search", user_id=user_id, anon_id=anon, meta=meta)


def log_contact_click(db: dict, *, kind: str, product_id: str | None = None, profile_id: str | None = None, user_id: str | None = None) -> bool:
    """
    kind: 'whatsapp' | 'instagram' | 'call'
    """
    anon = get_anon_id(st.session_state)
    event_type = f"click_{kind}"
    dedupe = f"{event_type}|p:{product_id or ''}|pr:{profile_id or ''}"
    return track_event_once(
        db,
        dedupe_key=dedupe,
        event_type=event_type,
        user_id=user_id,
        anon_id=anon,
        product_id=product_id,
        profile_id=profile_id,
    )
