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

    # ✅ Keys estables para poder limpiar luego
    st.session_state.setdefault("reg_email", "")
    st.session_state.setdefault("reg_pass", "")
    st.session_state.setdefault("reg_business", "")
    st.session_state.setdefault("reg_city", "")
    st.session_state.setdefault("reg_categories", [])

    email = st.text_input("Email", placeholder="tu@email.com", key="reg_email")
    password = st.text_input("Contraseña", type="password", placeholder="Mínimo 8 caracteres", key="reg_pass")
    business_name = st.text_input("Nombre del emprendimiento", placeholder="Ej: Panadería Luna", key="reg_business")
    city = st.text_input("Ciudad (opcional)", placeholder="Ej: Medellín", key="reg_city")
    categories = st.multiselect(
        "Categorías",
        ["Comida", "Moda", "Servicios", "Tecnología", "Hogar", "Salud", "Educación", "Arte"],
        key="reg_categories"
    )

    if st.button("Crear cuenta", use_container_width=True):
        e = (email or "").strip().lower()

        if len(password or "") < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            st.stop()

        if not (business_name or "").strip():
            st.error("El nombre del emprendimiento es obligatorio.")
            st.stop()

        if any(u.get("email") == e for u in db.get("users", [])):
            st.error("Ese email ya está registrado.")
            st.stop()

        user_id = new_id()
        db.setdefault("users", []).append({
            "id": user_id,
            "email": e,
            "password_hash": hash_password(password),
            "role": "EMPRENDEDOR",
            "status": "PENDING",
            "max_published_products": 5,  # ✅ NUEVO: límite inicial
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "reset_token": None,
            "reset_token_expires_at": None,
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
            "is_featured": False,          # ✅ NUEVO: destacados
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        
        # ✅ recomendado:
        db.setdefault("events", [])
        save_db(db)

        # ✅ Limpiar campos del formulario
        st.session_state["reg_email"] = ""
        st.session_state["reg_pass"] = ""
        st.session_state["reg_business"] = ""
        st.session_state["reg_city"] = ""
        st.session_state["reg_categories"] = []

        st.success("Cuenta creada. Ahora inicia sesión (tu perfil quedará pendiente de aprobación).")

        # ✅ Redirigir a Login
        st.session_state["route"] = "login"
        st.rerun()
