from __future__ import annotations
from typing import List
import streamlit as st
from auth.session import get_user

def require_role(roles: List[str]) -> bool:
    u = get_user()
    if not u:
        st.warning("Debes iniciar sesión para acceder aquí.")
        return False
    if u.get("role") not in roles:
        st.error("No tienes permisos para acceder a esta sección.")
        return False
    if u.get("status") == "BLOCKED":
        st.error("Tu cuenta está bloqueada. Contacta al administrador.")
        return False
    return True
