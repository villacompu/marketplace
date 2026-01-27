from __future__ import annotations
import streamlit as st

from auth.hashing import verify_password
from auth.session import set_user


def render(db):
    # Si ya hay sesión, no tiene sentido quedarse aquí
    if st.session_state.get("user"):
        st.session_state["route"] = "home"
        st.rerun()

    st.markdown("## Iniciar sesión")
    st.markdown(
        '<div class="muted">Accede como administrador o emprendedor para gestionar contenido.</div>',
        unsafe_allow_html=True
    )
    st.write("")

    # Keys estables
    st.session_state.setdefault("login_email", "")
    st.session_state.setdefault("login_pass", "")

    email = st.text_input("Email", placeholder="tu@email.com", key="login_email")
    password = st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_pass")

    if st.button("Entrar", use_container_width=True):
        e = (email or "").strip().lower()
        u = next((x for x in db.get("users", []) if x.get("email") == e), None)

        if not u:
            st.error("No existe un usuario con ese email.")
            st.stop()

        if u.get("status") == "BLOCKED":
            st.error("Tu cuenta está bloqueada.")
            st.stop()

        if not verify_password(password or "", u.get("password_hash", "")):
            st.error("Contraseña incorrecta.")
            st.stop()

        # Guardar sesión
        set_user({k: u[k] for k in ["id", "email", "role", "status"]})

        if bool(set_user.get("must_change_password", False)):
            st.session_state["route"] = "force_change_password"
            st.rerun()

        # ✅ Redirección inmediata
        st.session_state["route"] = "my_profile" if u.get("role") == "EMPRENDEDOR" else "home"
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="muted">¿No tienes cuenta?</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        if st.button("✨ Regístrate", use_container_width=True):
            st.session_state["route"] = "register"
            st.rerun()
    with c2:
        st.caption("Crea tu cuenta en 1 minuto.")
