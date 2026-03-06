from __future__ import annotations

from datetime import datetime
import re
import uuid
import streamlit as st

from services.analytics_context import get_event_context


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

    q = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "<email>", q, flags=re.I)
    q = re.sub(r"\+?\d[\d\s().-]{6,}\d", "<phone>", q)

    q = " ".join(q.split())
    return q[:max_len]


def _safe_meta(meta: dict | None) -> dict:
    """
    Asegura que meta siempre sea dict y elimina valores enormes.
    """
    if not isinstance(meta, dict):
        return {}

    cleaned = {}
    for k, v in meta.items():
        key = str(k)[:80]
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str):
                cleaned[key] = v[:500]
            else:
                cleaned[key] = v
        elif isinstance(v, list):
            cleaned[key] = [str(x)[:120] for x in v[:20]]
        elif isinstance(v, dict):
            inner = {}
            for ik, iv in v.items():
                ik2 = str(ik)[:80]
                if isinstance(iv, str):
                    inner[ik2] = iv[:300]
                elif isinstance(iv, (int, float, bool)) or iv is None:
                    inner[ik2] = iv
                else:
                    inner[ik2] = str(iv)[:300]
            cleaned[key] = inner
        else:
            cleaned[key] = str(v)[:300]

    return cleaned


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
    Guarda eventos básicos.
    - NO guardamos IP
    - NO guardamos PII sensible
    - Mantiene un máximo para que el JSON no crezca infinito

    Compat:
    - Guardamos `type` y también `event` con el mismo valor.
    """
    db.setdefault("events", [])

    ctx = _safe_meta(get_event_context())
    base_meta = _safe_meta(meta)

    # prioridad: meta explícita sobrescribe contexto si trae la misma llave
    merged_meta = {**ctx, **base_meta}

    db["events"].append(
        {
            "ts": _now_iso(),
            "type": event_type,
            "event": event_type,
            "user_id": user_id or "",
            "anon_id": anon_id or "",
            "product_id": product_id or "",
            "profile_id": profile_id or "",
            "meta": merged_meta,
        }
    )

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


# -------------------------------------------------------------------
# Helpers listos para usar
# -------------------------------------------------------------------

def log_view_home(
    db: dict,
    *,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    anon = get_anon_id(st.session_state)
    merged = {"page_context": "home", **(meta or {})}
    return track_event_once(
        db,
        dedupe_key="home",
        event_type="view_home",
        user_id=user_id,
        anon_id=anon,
        meta=merged,
    )


def log_view_product(
    db: dict,
    *,
    product_id: str,
    profile_id: str | None = None,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    anon = get_anon_id(st.session_state)
    merged = {"page_context": "product_detail", **(meta or {})}
    return track_event_once(
        db,
        dedupe_key=f"product:{product_id}",
        event_type="view_product",
        user_id=user_id,
        anon_id=anon,
        product_id=product_id,
        profile_id=profile_id,
        meta=merged,
    )


def log_view_profile(
    db: dict,
    *,
    profile_id: str,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    anon = get_anon_id(st.session_state)
    merged = {"page_context": "public_profile", **(meta or {})}
    return track_event_once(
        db,
        dedupe_key=f"profile:{profile_id}",
        event_type="view_profile",
        user_id=user_id,
        anon_id=anon,
        profile_id=profile_id,
        meta=merged,
    )


def log_view_directory(
    db: dict,
    *,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    anon = get_anon_id(st.session_state)
    merged = {"page_context": "directory", **(meta or {})}
    return track_event_once(
        db,
        dedupe_key="directory",
        event_type="view_directory",
        user_id=user_id,
        anon_id=anon,
        meta=merged,
    )


def log_search(
    db: dict,
    *,
    q: str,
    filters: dict | None = None,
    results_n: int | None = None,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    anon = get_anon_id(st.session_state)

    search_meta = {
        "q": _sanitize_query(q),
        "filters": _safe_meta(filters or {}),
        "results_n": int(results_n or 0),
        **(meta or {}),
    }

    sig = f"{search_meta['q']}|{search_meta.get('filters')}"
    return track_event_once(
        db,
        dedupe_key=f"search:{sig}",
        event_type="search",
        user_id=user_id,
        anon_id=anon,
        meta=search_meta,
    )


def log_contact_click(
    db: dict,
    *,
    kind: str,
    product_id: str | None = None,
    profile_id: str | None = None,
    user_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    """
    kind: 'whatsapp' | 'instagram' | 'call' | 'website' | 'catalog'
    """
    anon = get_anon_id(st.session_state)
    event_type = f"click_{kind}"
    dedupe = f"{event_type}|p:{product_id or ''}|pr:{profile_id or ''}"

    click_meta = {
        "click_kind": kind,
        **(meta or {}),
    }

    return track_event_once(
        db,
        dedupe_key=dedupe,
        event_type=event_type,
        user_id=user_id,
        anon_id=anon,
        product_id=product_id,
        profile_id=profile_id,
        meta=click_meta,
    )