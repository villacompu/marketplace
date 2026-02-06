# services/analytics_context.py
from __future__ import annotations
import re
import streamlit as st

def _device_from_ua(ua: str) -> str:
    ua = (ua or "").lower()
    if any(k in ua for k in ["iphone", "android", "mobile"]):
        return "Mobile"
    if any(k in ua for k in ["ipad", "tablet"]):
        return "Tablet"
    return "Desktop"

def _channel_from_utm(utm_source: str, utm_medium: str) -> str:
    s = (utm_source or "").lower()
    m = (utm_medium or "").lower()
    if not s and not m:
        return "Direct"

    # reglas simples (ajústalas a tu gusto)
    if "instagram" in s or "ig" == s or "instagram" in m:
        return "Organic Social"
    if "tiktok" in s or "tiktok" in m:
        return "Organic Social"
    if "facebook" in s or "fb" == s or "facebook" in m:
        return "Organic Social"
    if "google" in s or "cpc" in m or "seo" in m or "organic" in m:
        return "Organic Search"
    return "Referral"

def get_event_context() -> dict:
    """
    Devuelve meta extra sin guardar IP.
    Depende de que Streamlit exponga headers (en versiones nuevas: st.context.headers).
    """
    meta: dict = {}

    # 1) UTM por query params (muy útil para “canales”)
    q = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
    utm_source = (q.get("utm_source", [""])[0] if isinstance(q.get("utm_source"), list) else q.get("utm_source", "")) or ""
    utm_medium = (q.get("utm_medium", [""])[0] if isinstance(q.get("utm_medium"), list) else q.get("utm_medium", "")) or ""
    meta["utm_source"] = utm_source
    meta["utm_medium"] = utm_medium
    meta["channel"] = _channel_from_utm(utm_source, utm_medium)

    # 2) Device + referrer desde headers (si existen)
    ua = ""
    ref = ""
    try:
        headers = getattr(st, "context", None).headers  # Streamlit nuevo
        ua = headers.get("user-agent", "") or headers.get("User-Agent", "") or ""
        ref = headers.get("referer", "") or headers.get("Referer", "") or ""
    except Exception:
        pass

    meta["user_agent"] = ua[:300]
    meta["device"] = _device_from_ua(ua)
    meta["referrer"] = ref[:300]

    return meta
