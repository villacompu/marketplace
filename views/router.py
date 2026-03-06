from __future__ import annotations

import streamlit as st


def goto(route: str, **params):
    # Guardar desde dónde venía el usuario
    st.session_state["last_route"] = st.session_state.get("route", "home")

    # Ruta nueva
    st.session_state["route"] = route

    # Parámetros en query string
    for k, v in params.items():
        st.query_params[k] = str(v)

    st.rerun()


def current_route(default: str = "home") -> str:
    return st.session_state.get("route", default)