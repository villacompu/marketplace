from __future__ import annotations
from typing import Any, Dict, Optional
import streamlit as st

def get_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("auth_user")

def set_user(user: Optional[Dict[str, Any]]) -> None:
    st.session_state["auth_user"] = user

def logout() -> None:
    set_user(None)
