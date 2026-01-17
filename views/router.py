from __future__ import annotations
import streamlit as st

def goto(route: str, **params) -> None:
    st.session_state["route"] = route
    for k, v in params.items():
        st.session_state[k] = v
    st.rerun()

def current_route(default: str = "home") -> str:
    return st.session_state.get("route", default)

