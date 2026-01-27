from __future__ import annotations
import streamlit as st

from auth.hashing import hash_password
from db.repo_json import new_id, now_iso, save_db


def render(db):
    st.markdown("## Crear cuenta (Emprendedor)")
    st.markdown(
        '<div class="muted">Registro simple para emprendedores.</div>',
        unsafe_allow_html=True
    )
    st.write("")

    # ✅ Si venimos de un registro exitoso, limpiamos ANTES de instanciar widgets
    if st.session_state.pop("_reg_clear", False):
        st.session_state.pop("reg_email", None)
        st.session_state.pop("reg_pass", None)
        st.session_state.pop("reg_pass2", None)
        st.session_state.pop("reg_business", None)
        st.session_state.pop("reg_city", None)
        st.session_state.pop("reg_categories", None)

    # ✅ Defaults
    st.session_state.setdefault("reg_email", "")
    st.session_state.setdefault("reg_pass", "")
    st.session_state.setdefault("reg_pass2", "")
    st.session_state.setdefault("reg_business", "")
    st.session_state.setdefault("reg_city", "")
    st.session_state.setdefault("reg_categories", [])

    email = st.text_input("Email", placeholder="tu@email.com", key="reg_email")
    password = st.text_input("Contraseña", type="password", placeholder="Mínimo 8 caracteres", key="reg_pass")
    password2 = st.text_input("Confirmar contraseña", type="password", placeholder="Repite la contraseña", key="reg_pass2")

    business_name = st.text_input("Nombre del emprendimiento", placeholder="Ej: Panadería Luna", key="reg_business")
    city = st.text_input("Ciudad (opcional)", placeholder="Ej: Medellín", key="reg_city")
    categories = st.multiselect(
        "Categorías",
        ["Comida", "Moda", "Servicios", "Tecnología", "Hogar", "Salud", "Educación", "Arte"],
        key="reg_categories"
    )

    if st.button("Crear cuenta", use_container_width=True):
        e = (email or "").strip().lower()

        if not e:
            st.error("El email es obligatorio.")
            st.stop()

        if len(password or "") < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            st.stop()

        if (password or "") != (password2 or ""):
            st.error("Las contraseñas no coinciden.")
            st.stop()

        if not (business_name or "").strip():
            st.error("El nombre del emprendimiento es obligatorio.")
            st.stop()

        if any((u.get("email") or "").strip().lower() == e for u in db.get("users", [])):
            st.error("Ese email ya está registrado.")
            st.stop()

        user_id = new_id()
        db.setdefault("users", []).append({
            "id": user_id,
            "email": e,
            "password_hash": hash_password(password),
            "role": "EMPRENDEDOR",
            "status": "PENDING",
            "max_published_products": 5,
            "can_view_stats": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "reset_token": None,
            "reset_token_expires_at": None,
            "must_change_password": False,
        })

        profile_id = new_id()
        db.setdefault("profiles", []).append({
            "id": profile_id,
            "owner_user_id": user_id,
            "business_name": (business_name or "").strip()[:80],
            "short_desc": "Descripción corta (edítame).",
            "long_desc": "Descripción larga (edítame).",
            "categories": categories or [],
            "city": (city or "").strip()[:60],
            "availability": "",
            "links": {
                "instagram": "",
                "facebook": "",
                "tiktok": "",
                "whatsapp": "",
                "website": "",
                "external_catalog": "",
                "phone": ""
            },
            "logo_url": "",
            "gallery_urls": [],
            "is_approved": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

        db.setdefault("events", [])
        save_db(db)

        st.success("Cuenta creada. Ahora inicia sesión (tu perfil quedará pendiente de aprobación).")

        # ✅ Marcamos flag y redirigimos (sin tocar keys en este run)
        st.session_state["_reg_clear"] = True
        st.session_state["route"] = "login"
        st.rerun()
