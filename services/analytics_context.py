from __future__ import annotations

from urllib.parse import urlparse
import streamlit as st


def _safe_first_query_param(qp, key: str) -> str:
    try:
        v = qp.get(key, "")
        if isinstance(v, list):
            return str(v[0]).strip() if v else ""
        return str(v).strip()
    except Exception:
        return ""


def _device_from_ua(ua: str) -> str:
    ua = (ua or "").lower()

    # tablet primero, para no clasificar ipad como mobile
    if any(k in ua for k in ["ipad", "tablet"]):
        return "Tablet"

    if any(k in ua for k in ["iphone", "android", "mobile"]):
        return "Mobile"

    return "Desktop"


def _channel_from_context(
    utm_source: str,
    utm_medium: str,
    referrer: str,
) -> str:
    s = (utm_source or "").lower().strip()
    m = (utm_medium or "").lower().strip()
    r = (referrer or "").lower().strip()

    # 1) Si hay UTM, manda UTM
    if s or m:
        if any(x in s for x in ["instagram", "facebook", "fb", "tiktok", "linkedin"]) or \
           any(x in m for x in ["social", "instagram", "facebook", "tiktok", "linkedin"]):
            return "Organic Social"

        if any(x in s for x in ["google", "bing", "yahoo"]) or \
           any(x in m for x in ["organic", "seo", "search"]):
            return "Organic Search"

        if any(x in m for x in ["cpc", "ppc", "paid", "ads", "paid-social", "display", "email"]):
            return "Campaign"

        return "Referral"

    # 2) Si no hay UTM, inferir por referrer
    if not r:
        return "Direct"

    if any(x in r for x in ["google.", "bing.", "search.yahoo.", "duckduckgo."]):
        return "Organic Search"

    if any(x in r for x in ["instagram.com", "facebook.com", "m.facebook.com", "tiktok.com", "linkedin.com"]):
        return "Organic Social"

    return "Referral"


def _normalize_referrer(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref:
        return ""

    try:
        p = urlparse(ref)
        if p.netloc:
            return f"{p.scheme}://{p.netloc}"
        return ref[:300]
    except Exception:
        return ref[:300]


def _path_from_query_params(qp) -> str:
    """
    Si luego quieres pasar ?src=home o ?from=directory esto lo capturará.
    """
    for k in ["path", "page", "src_page", "from_page", "entry_page"]:
        v = _safe_first_query_param(qp, k)
        if v:
            return v[:80]
    return ""


def get_event_context() -> dict:
    """
    Devuelve meta adicional sin guardar IP ni datos sensibles directos.

    Lo que intenta capturar:
    - UTM
    - canal
    - dispositivo
    - referrer
    - idioma / locale
    - host/path
    - hints opcionales de ubicación si vienen en query params
    """

    meta: dict = {}

    # -------------------------
    # Query params
    # -------------------------
    try:
        qp = st.query_params
    except Exception:
        try:
            qp = st.experimental_get_query_params()
        except Exception:
            qp = {}

    utm_source = _safe_first_query_param(qp, "utm_source")
    utm_medium = _safe_first_query_param(qp, "utm_medium")
    utm_campaign = _safe_first_query_param(qp, "utm_campaign")
    utm_content = _safe_first_query_param(qp, "utm_content")
    utm_term = _safe_first_query_param(qp, "utm_term")

    meta["utm_source"] = utm_source
    meta["utm_medium"] = utm_medium
    meta["utm_campaign"] = utm_campaign
    meta["utm_content"] = utm_content
    meta["utm_term"] = utm_term

    # Origen funcional del flujo
    entry_source = (
        _safe_first_query_param(qp, "src")
        or _safe_first_query_param(qp, "source")
        or _safe_first_query_param(qp, "from")
        or _safe_first_query_param(qp, "entry_source")
    )
    meta["entry_source"] = (entry_source[:80] if entry_source else "direct")

    page_context = _path_from_query_params(qp)
    meta["page_context"] = (page_context[:80] if page_context else "")

    # Hints de ubicación opcionales si algún día los mandas por URL
    meta["country_hint"] = _safe_first_query_param(qp, "country")[:80]
    meta["city_hint"] = _safe_first_query_param(qp, "city")[:80]
    meta["timezone_hint"] = _safe_first_query_param(qp, "tz")[:80]
    meta["locale_hint"] = _safe_first_query_param(qp, "locale")[:80]

    # -------------------------
    # Headers / browser context
    # -------------------------
    ua = ""
    ref = ""
    accept_language = ""
    host = ""

    try:
        ctx = getattr(st, "context", None)
        headers = getattr(ctx, "headers", None)

        if headers:
            ua = headers.get("user-agent", "") or headers.get("User-Agent", "") or ""
            ref = headers.get("referer", "") or headers.get("Referer", "") or ""
            accept_language = (
                headers.get("accept-language", "")
                or headers.get("Accept-Language", "")
                or ""
            )
            host = headers.get("host", "") or headers.get("Host", "") or ""
    except Exception:
        pass

    meta["user_agent"] = ua[:300]
    meta["device"] = _device_from_ua(ua)
    meta["referrer"] = _normalize_referrer(ref)
    meta["host"] = str(host or "")[:150]
    meta["accept_language"] = str(accept_language or "")[:120]

    # idioma principal
    lang = ""
    if accept_language:
        try:
            lang = accept_language.split(",")[0].strip()
        except Exception:
            lang = accept_language[:40]
    meta["lang"] = lang[:40]

    # canal
    meta["channel"] = _channel_from_context(
        utm_source=utm_source,
        utm_medium=utm_medium,
        referrer=ref,
    )

    # autenticación
    try:
        u = st.session_state.get("user") or {}
        meta["is_logged_in"] = bool(u.get("id"))
        meta["role_hint"] = str(u.get("role") or "")[:40]
    except Exception:
        meta["is_logged_in"] = False
        meta["role_hint"] = ""

    return meta
