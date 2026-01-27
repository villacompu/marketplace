from __future__ import annotations
import streamlit as st

from auth.session import get_user
from auth.hashing import hash_password
from db.repo_json import save_db, now_iso


def render(db):
    u = get_user()
    if not u:
        st.warning("Debes iniciar sesión.")
        st.session_state["route"] = "login"
        st.rerun()
        return

    st.markdown("## 🔒 Debes cambiar tu contraseña")
    st.markdown('<div class="muted">Por seguridad, actualiza tu contraseña para continuar.</div>', unsafe_allow_html=True)
    st.write("")

    # traer usuario real desde db
    u_db = next((x for x in db.get("users", []) if x.get("id") == u.get("id")), None)
    if not u_db:
        st.error("Usuario no encontrado.")
        return

    p1 = st.text_input("Nueva contraseña", type="password", key="fcp_pw1")
    p2 = st.text_input("Confirmar contraseña", type="password", key="fcp_pw2")

    if st.button("✅ Guardar y continuar", use_container_width=True):
        if len((p1 or "")) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            st.stop()
        if p1 != p2:
            st.error("Las contraseñas no coinciden.")
            st.stop()

        u_db["password_hash"] = hash_password(p1)
        u_db["must_change_password"] = False
        u_db["updated_at"] = now_iso()
        save_db(db)

        # refrescar sesión también
        u["must_change_password"] = False

        st.success("Contraseña actualizada. Bienvenido.")
        st.session_state["route"] = "home"
        st.rerun()
