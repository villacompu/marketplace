from __future__ import annotations

import streamlit as st
import validators
import re

from auth.guards import require_role
from auth.session import get_user
from db.repo_json import user_profile, new_id, now_iso, save_db
from services.validators import safe_text
from urllib.parse import quote_plus
from services.media_urls import normalize_many

# ✅ Incluimos Bebidas y filtramos defaults para evitar errores
CATEGORIES = [
    "Comida", "Bebidas", "Moda", "Servicios", "Tecnología",
    "Hogar", "Salud", "Educación", "Arte", "Belleza", "Mascotas"
]

LINK_FIELDS = [
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("tiktok", "TikTok"),
    ("whatsapp", "WhatsApp (solo número)"),
    ("website", "Página web"),
    ("external_catalog", "Catálogo externo"),
    ("phone", "Celular"),
]

DEFAULT_WHATSAPP_TEXT = "Hola, vi tu emprendimiento en el Marketplace y quiero una asesoría."

def _digits_only_phone(v: str) -> str:
    return re.sub(r"\D", "", (v or ""))

def build_whatsapp_url(phone_raw: str, text: str = DEFAULT_WHATSAPP_TEXT) -> str:
    digits = _digits_only_phone(phone_raw)

    # Si escriben 10 dígitos (Colombia sin indicativo), anteponer 57
    if len(digits) == 10:
        digits = "57" + digits

    msg = quote_plus(text or "")
    return f"https://api.whatsapp.com/send?phone={digits}&text={msg}"


def _clean_phone(raw: str) -> str:
    """
    Deja + y dígitos.
    Ej: '+57 300-123 4567' -> '+573001234567'
    Ej: '300 123 4567' -> '3001234567'
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    raw = re.sub(r"(?!^\+)[^\d]", "", raw)  # quita no-dígitos excepto + inicial
    if raw == "+":
        return ""
    return raw

def _is_phone_like(v: str) -> bool:
    """Acepta 7-15 dígitos (con + opcional)."""
    if not v:
        return True
    digits = re.sub(r"\D", "", v)
    return 7 <= len(digits) <= 15

def _is_url(u: str) -> bool:
    u = (u or "").strip()
    if not u:
        return True
    return bool(validators.url(u))

def _split_urls(text: str, max_items: int = 9) -> list[str]:
    raw = (text or "").replace(",", "\n").splitlines()
    urls = [x.strip() for x in raw if x.strip()]
    return urls[:max_items]


def render(db):
    if not require_role(["EMPRENDEDOR"]):
        return

    u = get_user()
    uid = u["id"]

    prof = user_profile(db, uid)

    if not prof:
        prof = {
            "id": new_id(),
            "owner_user_id": uid,
            "business_name": "Mi emprendimiento",
            "short_desc": "",
            "long_desc": "",
            "categories": [],
            "city": "",
            "availability": "",
            "links": {k: "" for k, _ in LINK_FIELDS},
            "logo_url": "",
            "gallery_urls": [],
            "is_approved": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        db.setdefault("profiles", []).append(prof)
        save_db(db)

    

    st.markdown("## 🏪 Mi Perfil")
    status_txt = "✅ Aprobado" if prof.get("is_approved") else "🕒 Pendiente de aprobación"
    st.markdown(
        f'<div class="muted">Configura tu perfil público. Estado: <b>{status_txt}</b></div>',
        unsafe_allow_html=True
    )
    st.write("")

    t1, t2, t3 = st.tabs(["Información", "Imágenes", "Redes y enlaces"])

    # -------- TAB 1: Información --------
    with t1:
        with st.form("profile_info_form", clear_on_submit=False):
            business_name = st.text_input(
                "Nombre del emprendimiento",
                value=prof.get("business_name", ""),
                placeholder="Ej: Café Aurora",
            )
            short_desc = st.text_area(
                "Descripción corta",
                value=prof.get("short_desc", ""),
                placeholder="Una frase clara (máx ~140 caracteres).",
                height=80,
            )
            long_desc = st.text_area(
                "Descripción larga",
                value=prof.get("long_desc", ""),
                placeholder="Cuenta tu historia, qué ofreces y cómo pueden contactarte.",
                height=160,
            )

            default_cats = [c for c in (prof.get("categories") or []) if c in CATEGORIES]
            categories = st.multiselect(
                "Categorías",
                options=CATEGORIES,
                default=default_cats,
            )

            c1, c2 = st.columns(2)
            with c1:
                city = st.text_input("Ciudad (opcional)", value=prof.get("city", ""), placeholder="Ej: Bogotá")
            with c2:
                availability = st.text_input(
                    "Horario / disponibilidad (opcional)",
                    value=prof.get("availability", ""),
                    placeholder="Ej: Lun–Sáb 8am–6pm",
                )

            submitted = st.form_submit_button("💾 Guardar información", use_container_width=True)

        if submitted:
            business_name = safe_text(business_name, 80)
            short_desc = safe_text(short_desc, 180)
            long_desc = safe_text(long_desc, 5000)
            city = safe_text(city, 60)
            availability = safe_text(availability, 80)

            if not business_name.strip():
                st.error("El nombre del emprendimiento es obligatorio.")
                st.stop()

            prof["business_name"] = business_name
            prof["short_desc"] = short_desc
            prof["long_desc"] = long_desc
            prof["categories"] = categories
            prof["city"] = city
            prof["availability"] = availability
            prof["updated_at"] = now_iso()

            save_db(db)
            st.success("Perfil actualizado.")
            st.rerun()

    from services.media_urls import normalize_many

# -------- TAB 2: Imágenes (por URL) --------
    with t2:
        st.caption("En el MVP usamos URLs.")

        with st.form("profile_images_form", clear_on_submit=False):
            logo_url = st.text_input(
                "URL del logo / foto principal",
                value=prof.get("logo_url", ""),
                placeholder="https://... (opcional)",
            )

            gallery_text = st.text_area(
                "Galería (URLs, una por línea o separadas por coma) — máximo 8",
                value="\n".join(prof.get("gallery_urls", []) or []),
                height=140,
                placeholder="https://... \nhttps://... \n...",
            )

            submitted = st.form_submit_button("💾 Guardar imágenes", use_container_width=True)

        if submitted:
            logo_url = (logo_url or "").strip()
            gallery_urls = _split_urls(gallery_text, max_items=8)

            # ✅ Validación sobre lo que el usuario escribió (antes de normalizar)
            errors = []
            if logo_url and not _is_url(logo_url):
                errors.append("Logo: URL inválida.")
            bad_gallery = [u for u in gallery_urls if not _is_url(u)]
            if bad_gallery:
                errors.append(f"Galería: hay URLs inválidas ({len(bad_gallery)}).")

            if errors:
                for e in errors:
                    st.error(e)
                st.stop()

            # ✅ Normalización (Drive -> lh3.googleusercontent.com/d/<id>)
            logo_norm = normalize_many([logo_url], max_n=1)
            logo_url = (logo_norm[0] if (logo_norm and logo_norm[0]) else "")

            gallery_urls = normalize_many(gallery_urls, max_n=8)

            prof["logo_url"] = logo_url
            prof["gallery_urls"] = gallery_urls
            prof["updated_at"] = now_iso()
            save_db(db)
            st.success("Imágenes actualizadas.")
            st.rerun()

        st.write("")
        st.markdown("### Vista previa")

        # ✅ Vista previa también normalizada (por si en DB quedaron links viejos)
        logo_prev = normalize_many([prof.get("logo_url", "")], max_n=1)
        logo_prev = logo_prev[0] if (logo_prev and logo_prev[0]) else ""

        if logo_prev:
            st.image(logo_prev, caption="Logo / principal", use_column_width=True)

        urls = normalize_many(prof.get("gallery_urls", []) or [], max_n=8)
        urls = [u for u in urls if (u or "").strip()]
        if urls:
            cols = st.columns(3)
            for i, u in enumerate(urls[:8]):
                with cols[i % 3]:
                    st.image(u, use_column_width=True)

    # -------- TAB 3: Redes y enlaces --------
    with t3:
        st.caption("Pega tus enlaces. Validamos que sean URLs (excepto Celular).")

        current_links = prof.get("links") or {k: "" for k, _ in LINK_FIELDS}

        with st.form("profile_links_form", clear_on_submit=False):
            new_links = {}

            for k, label in LINK_FIELDS:
                if k == "whatsapp":
                    new_links[k] = st.text_input(
                        "WhatsApp (solo número)",
                        value=current_links.get("whatsapp_phone", ""),
                        placeholder="+57 3001234567 (opcional)",
                    )
                elif k == "phone":
                    new_links[k] = st.text_input(
                        label,
                        value=current_links.get(k, ""),
                        placeholder="+57 3001234567 (opcional)",
                    )
                else:
                    new_links[k] = st.text_input(
                        label,
                        value=current_links.get(k, ""),
                        placeholder="https://... (opcional)",
                    )

            submitted = st.form_submit_button("💾 Guardar enlaces", use_container_width=True)


        if submitted:
            errors = []
            cleaned = dict(current_links)  # para conservar otros campos existentes

            # ---- WhatsApp como número ----
            wa_in = (new_links.get("whatsapp") or "").strip()
            wa_phone = _clean_phone(wa_in)

            if wa_phone and not _is_phone_like(wa_phone):
                errors.append("whatsapp: número inválido (usa 7–15 dígitos).")

            # Guardamos número aparte (útil si luego quieres mostrarlo en UI)
            cleaned["whatsapp_phone"] = wa_phone

            # Generar link solo si hay número; si no, dejar vacío
            cleaned["whatsapp"] = build_whatsapp_url(wa_phone) if wa_phone else ""

            # ---- Celular (phone) ----
            phone_in = (new_links.get("phone") or "").strip()
            phone = _clean_phone(phone_in)
            if phone and not _is_phone_like(phone):
                errors.append("phone: número inválido (usa 7–15 dígitos).")
            cleaned["phone"] = phone

            # ---- Otros links (URL) ----
            for k, _label in LINK_FIELDS:
                if k in ("whatsapp", "phone"):
                    continue
                v = (new_links.get(k) or "").strip()
                if v and not _is_url(v):
                    errors.append(f"{k}: URL inválida.")
                cleaned[k] = safe_text(v, 300)

            if errors:
                for e in errors:
                    st.error(e)
                st.stop()

            prof["links"] = cleaned
            prof["updated_at"] = now_iso()
            save_db(db)
            st.success("Enlaces guardados.")
            st.rerun()



    if st.button("📦 Mis productos", key="profile_my_products", use_container_width=True):
        st.session_state["route"] = "my_products"
        st.rerun()