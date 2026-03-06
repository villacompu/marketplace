from __future__ import annotations

import streamlit as st
import textwrap
import re

from services.validators import safe_text
from views.router import goto
from auth.session import get_user
from services.analytics import log_view_product
from services.catalog import format_price

from db.repo_json import save_db





def _norm_tel(t: str) -> str:
    """Deja solo + y dígitos."""
    t = (t or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"(?!^\+)[^\d]", "", t)
    return "" if t == "+" else t


def _wa_href(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    low = v.lower()
    if low.startswith("http"):
        return v
    num = _norm_tel(v).replace("+", "")
    return f"https://wa.me/{num}" if num else ""


def _ig_href(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    low = v.lower()
    if low.startswith("http"):
        return v
    user = v.replace("@", "").strip()
    return f"https://instagram.com/{user}" if user else ""


def _tel_href(v: str) -> str:
    v = _norm_tel(v)
    return f"tel:{v}" if v else ""


# ✅ Regla de visibilidad pública real
def _is_public_allowed(db: dict, product: dict) -> bool:
    if (product.get("status") or "").upper() != "PUBLISHED":
        return False

    profile_id = product.get("profile_id")
    prof = next((x for x in db.get("profiles", []) if x.get("id") == profile_id), None)
    if not prof or not prof.get("is_approved"):
        return False

    owner_id = product.get("owner_user_id")
    if owner_id:
        u = next((x for x in db.get("users", []) if x.get("id") == owner_id), None)
        if u and (u.get("status") or "").upper() != "ACTIVE":
            return False

    return True


def render(db):
    pid = st.session_state.get("selected_product_id")
    if not pid:
        st.warning("No hay producto seleccionado.")
        return

    p = next((x for x in db.get("products", []) if x.get("id") == pid), None)
    if not p:
        st.error("Producto no encontrado.")
        return

    # ✅ Bloqueo real (salvo owner o admin)
    u = get_user()
    st.session_state.setdefault("entry_source", "product_detail")
    is_owner = bool(u and u.get("id") == p.get("owner_user_id"))
    is_admin = bool(u and u.get("role") == "ADMIN")

    if not (is_owner or is_admin) and not _is_public_allowed(db, p):
        st.error("Esta publicación no está disponible (pendiente de aprobación o no publicada).")
        if st.button("Volver al catálogo"):
            st.session_state["route"] = "home"
            st.rerun()
        return

    # ✅ Tracking deduplicado (evita duplicados por rerun)
    # (lo hacemos DESPUÉS del bloqueo, para contar solo vistas reales)
    did = log_view_product(
        db,
        product_id=p.get("id"),
        profile_id=p.get("profile_id"),
        user_id=(u or {}).get("id"),
        meta={
            "entry_source": st.session_state.get("entry_source") or st.session_state.get("last_route", "product_detail"),
            "page_context": "product_detail",
        },
    )
    if did:
        save_db(db)


    # -------- Header --------
    st.markdown(
        f"<div class='pd-title'>{safe_text(p.get('name','Producto'), 120)}</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<div class='pd-sub'>{safe_text(p.get('category',''), 40)}</div>",
        unsafe_allow_html=True
    )
    st.write("")

    # -------- Imágenes (siempre hero = primera) --------
    imgs = p.get("photo_urls") or []
    imgs = [u.strip() for u in imgs if (u or "").strip()]
    hero = imgs[0] if imgs else ""

    left, right = st.columns([3, 2], gap="large")

    with left:
        if hero:
            st.markdown(
                f"""
                <div class="pd-hero-wrap">
                  <img class="pd-hero-img" src="{hero}" alt="Imagen principal"/>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div class='pd-hero-placeholder'>🖼️</div>", unsafe_allow_html=True)

        # Miniaturas SOLO si hay más de 1 (NO clickeables)
        if len(imgs) > 1:
            thumbs_html = []
            for i, url in enumerate(imgs[:8]):
                active = "active" if i == 0 else ""
                thumbs_html.append(
                    f'<div class="pd-thumb {active} pd-thumb--static">'
                    f'  <img src="{url}" alt="thumb {i}"/>'
                    f"</div>"
                )

            html = f"""
            <div class="pd-thumbs-title">Más fotos</div>
            <div class="pd-thumbs">
              {''.join(thumbs_html)}
            </div>
            """.strip()

            st.markdown(textwrap.dedent(html), unsafe_allow_html=True)

    with right:
        price_txt = format_price(p)

        prof = None
        profile_id = p.get("profile_id")
        if profile_id:
            prof = next((x for x in db.get("profiles", []) if x.get("id") == profile_id), None)

        business = safe_text((prof or {}).get("business_name", "—"), 60)
        city = safe_text((prof or {}).get("city", "—"), 60)

        if prof:
            if st.button("👤 Ver emprendimiento", width='stretch', key="pd_view_profile"):
                st.session_state["entry_source"] = "product_detail_profile_button"
                goto("public_profile", selected_profile_id=prof["id"])

        tags = p.get("tags") or []
        tags_txt = ", ".join([safe_text(t, 40) for t in tags]) if tags else "—"

        links = (prof or {}).get("links") or {}
        wa_href = _wa_href(links.get("whatsapp") or "")
        ig_href = _ig_href(links.get("instagram") or "")
        tel_href = _tel_href(links.get("phone") or "")

        st.markdown(
            f"""
            <div class="card">
              <div class="title">Precio</div>
              <div class="row" style="margin-top:6px;">
                <span class="price">{price_txt}</span>
              </div>

              <div class="divider"></div>

              <div class="title">Emprendimiento</div>
              <div class="small" style="margin-top:6px;"><b>{business}</b></div>
              <div class="small">{city}</div>

              <div class="divider"></div>

              <div class="title">Etiquetas</div>
              <div class="small" style="margin-top:6px;">{tags_txt}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown('<div class="card-actions"><div class="actions-3">', unsafe_allow_html=True)
        a1, a2, a3 = st.columns([1, 1, 1], gap="small")

        with a1:
            if wa_href:
                st.markdown(
                    f'<a class="btn-contact" href="{wa_href}" target="_blank" rel="noopener noreferrer">📲 WhatsApp</a>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="btn-contact disabled">📲 WhatsApp</div>', unsafe_allow_html=True)

        with a2:
            if ig_href:
                st.markdown(
                    f'<a class="btn-contact" href="{ig_href}" target="_blank" rel="noopener noreferrer">📸 Instagram</a>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="btn-contact disabled">📸 Instagram</div>', unsafe_allow_html=True)

        with a3:
            if tel_href:
                st.markdown(f'<a class="btn-contact" href="{tel_href}">📞 Llamar</a>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="btn-contact disabled">📞 Llamar</div>', unsafe_allow_html=True)

        st.markdown("</div></div>", unsafe_allow_html=True)

    # -------- Descripción --------
    st.write("")
    st.markdown("<div class='pd-section-title'>Descripción</div>", unsafe_allow_html=True)
    desc = (p.get("description") or "").strip() or "—"
    st.markdown(f"<div class='pd-desc'>{safe_text(desc, 2000)}</div>", unsafe_allow_html=True)
