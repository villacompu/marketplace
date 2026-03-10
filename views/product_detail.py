from __future__ import annotations

import json
import re
import textwrap

import streamlit as st
import streamlit.components.v1 as components

from services.validators import safe_text
from views.router import goto
from auth.session import get_user
from services.analytics import log_view_product, log_contact_click
from services.catalog import format_price


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


def _open_url(url: str, same_tab: bool = False) -> None:
    if not url:
        return

    target = "_self" if same_tab else "_blank"
    components.html(
        f"""
        <script>
            window.open({json.dumps(url)}, {json.dumps(target)});
        </script>
        """,
        height=0,
    )


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

    # ✅ Tracking de vista
    log_view_product(
        product_id=p.get("id"),
        profile_id=p.get("profile_id"),
        user_id=(u or {}).get("id"),
        meta={
            "entry_source": st.session_state.get("entry_source") or st.session_state.get("last_route", "product_detail"),
            "page_context": "product_detail",
        },
    )

    # -------- Header --------
    st.markdown(
        f"<div class='pd-title'>{safe_text(p.get('name', 'Producto'), 120)}</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<div class='pd-sub'>{safe_text(p.get('category', ''), 40)}</div>",
        unsafe_allow_html=True
    )
    st.write("")

    # -------- Imágenes --------
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
            if st.button("👤 Ver emprendimiento", width="stretch", key="pd_view_profile"):
                st.session_state["entry_source"] = "product_detail_profile_button"
                goto("public_profile", selected_profile_id=prof["id"])

        tags = p.get("tags") or []
        tags_txt = ", ".join([safe_text(t, 40) for t in tags]) if tags else "—"

        links = (prof or {}).get("links") or {}
        wa_href = _wa_href(links.get("whatsapp") or "")
        ig_href = _ig_href(links.get("instagram") or "")
        tel_href = _tel_href(links.get("phone") or "")
        web_href = (links.get("website") or "").strip()
        catalog_href = (links.get("external_catalog") or links.get("catalog") or "").strip()

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

# -------- Contactos medibles + llamada funcional --------
        action_buttons = []

        if wa_href:
            action_buttons.append(("📲 WhatsApp", "whatsapp", wa_href, False))

        if ig_href:
            action_buttons.append(("📸 Instagram", "instagram", ig_href, False))

        if web_href:
            action_buttons.append(("🌐 Web", "website", web_href, False))

        if catalog_href:
            action_buttons.append(("🛍️ Catálogo", "catalog", catalog_href, False))

        if action_buttons:
            st.write("")
            for i in range(0, len(action_buttons), 3):
                row = action_buttons[i:i + 3]
                cols = st.columns(len(row), gap="small")

                for j, (label, kind, url, same_tab) in enumerate(row):
                    with cols[j]:
                        if st.button(
                            label,
                            key=f"pd_contact_{kind}_{p.get('id')}_{i}_{j}",
                            use_container_width=True,
                        ):
                            log_contact_click(
                                kind=kind,
                                product_id=p.get("id"),
                                profile_id=p.get("profile_id"),
                                user_id=(u or {}).get("id"),
                                meta={
                                    "entry_source": "product_detail_contact",
                                    "page_context": "product_detail",
                                },
                            )
                            _open_url(url, same_tab=same_tab)

        if tel_href:
            st.write("")
            st.markdown(
                f'<a class="btn-contact" href="{tel_href}">📞 Llamar</a>',
                unsafe_allow_html=True,
            )

    # -------- Descripción --------
    st.write("")
    st.markdown("<div class='pd-section-title'>Descripción</div>", unsafe_allow_html=True)
    desc = (p.get("description") or "").strip() or "—"
    st.markdown(f"<div class='pd-desc'>{safe_text(desc, 2000)}</div>", unsafe_allow_html=True)