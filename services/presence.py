from __future__ import annotations
import time
import uuid
import streamlit as st

# session_id -> last_seen_epoch_seconds
_SESSIONS: dict[str, float] = {}

def _now() -> float:
    return time.time()

def get_session_id() -> str:
    if "presence_session_id" not in st.session_state:
        st.session_state["presence_session_id"] = str(uuid.uuid4())
    return st.session_state["presence_session_id"]

def heartbeat(ttl_seconds: int = 90) -> None:
    """Marca esta sesión como activa y limpia las viejas."""
    sid = get_session_id()
    _SESSIONS[sid] = _now()

    # limpieza
    cutoff = _now() - ttl_seconds
    dead = [k for k, ts in _SESSIONS.items() if ts < cutoff]
    for k in dead:
        _SESSIONS.pop(k, None)

def online_count(ttl_seconds: int = 90) -> int:
    """Cuántas sesiones han tenido actividad reciente."""
    cutoff = _now() - ttl_seconds
    return sum(1 for ts in _SESSIONS.values() if ts >= cutoff)
