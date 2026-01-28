from __future__ import annotations

import re
import streamlit as st
import streamlit.components.v1 as components

from services.validators import safe_text
from auth.session import get_user
from services.analytics import log_view_profile
from db.repo_json import save_db
from services.catalog import format_price


def _clean_phone(raw: str) -> str:
    """Deja + y dígitos. Ej: '+57 300-123 4567' -> '+573001234567'."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    raw = re.sub(r"(?!^\+)[^\d]", "", raw)  # quita no-dígitos excepto + inicial
    return "" if raw == "+" else raw


def _wa_from_phone(phone: str) -> str:
    """Ej: +573001234567 -> https://wa.me/573001234567"""
    digits = re.sub(r"\D", "", phone or "")
    return f"https://wa.me/{digits}" if digits else ""


def _icon_for_label(label: str) -> str:
    low = (label or "").lower()
    if "whats" in low:
        return "🟢"
    if "insta" in low:
        return "📸"
    if "face" in low:
        return "🔵"
    if "tiktok" in low:
        return "🎵"
    if "web" in low or "página" in low or "pagina" in low:
        return "🌐"
    if "cat" in low:
        return "🛍️"
    if "tel" in low or "cel" in low or "phone" in low:
        return "📞"
    return "🔗"


def _link_chip(label: str, url: str, kind: str = "url") -> str:
    """
    kind:
      - "url": link normal (target blank)
      - "tel": link tel: (sin target blank)
    """
    url = (url or "").strip()
    if not url:
        return ""

    icon = _icon_for_label(label)

    # Para tel: no usamos target=_blank
    if kind == "tel":
        return f"""
        <a class="chip-link" href="{url}">
          <span class="chip-ico">{icon}</span>
          <span>{safe_text(label, 40)}</span>
        </a>
        """

    return f"""
    <a class="chip-link" href="{url}" target="_blank" rel="noopener noreferrer">
      <span class="chip-ico">{icon}</span>
      <span>{safe_text(label, 40)}</span>
    </a>
    """


def _product_cover_url(pr: dict) -> str:
    """Intenta sacar una imagen representativa sin inventar estructura rígida."""
    if not pr:
        return ""

    # campos comunes (string)
    for k in ("image_url", "cover_url", "thumbnail_url", "photo_url"):
        v = (pr.get(k) or "").strip()
        if v:
            return v

    # listas comunes (list)
    for k in ("photo_urls", "image_urls", "photos", "gallery_urls"):
        arr = pr.get(k) or []
        if isinstance(arr, list) and arr:
            v = (arr[0] or "").strip()
            if v:
                return v

    return ""



def _render_products_grid(products: list[dict]):
    """Renderiza una grilla simple de productos (3 columnas) sin romper estilos."""
    if not products:
        st.info("Este emprendimiento aún no tiene productos publicados.")
        return

    cols = st.columns(3, gap="large")
    for i, pr in enumerate(products):
        with cols[i % 3]:
            title = safe_text(pr.get("name", "Producto"), 80)

            # ✅ Precio usando la misma lógica de admin.py
            try:
                price_txt = format_price(pr)
            except Exception:
                price_txt = "Precio no disponible"
                

            cover_url = _product_cover_url(pr)

            if cover_url:
                st.image(cover_url, use_column_width=True)
            else:
                st.markdown("<div class='pp-hero-placeholder'>🛍️</div>", unsafe_allow_html=True)

            st.markdown(f"**{title}**")
            st.markdown(f"💲 {price_txt}")



def render(db):
    pid = st.session_state.get("selected_profile_id")
    if not pid:
        st.warning("No hay perfil seleccionado.")
        return

    prof = next((p for p in (db.get("profiles", []) or []) if p.get("id") == pid), None)
    if not prof:
        st.error("Perfil no encontrado.")
        return

    # ---- analytics view ----
    u = get_user()
    did = log_view_profile(db, profile_id=prof.get("id"), user_id=(u or {}).get("id"))
    if did:
        save_db(db)

    
    # ---- Header ----
    st.markdown(
        f"<div class='pp-title'>{safe_text(prof.get('business_name','Emprendimiento'), 120)}</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<div class='pp-sub'>{safe_text(prof.get('short_desc',''), 40)}</div>",
        unsafe_allow_html=True
    )
    st.write("")

    # ---- Chips (MISMO mecanismo que ya te funciona) ----
    links = prof.get("links") or {}
    phone_clean = _clean_phone(links.get("phone", ""))
    tel_url = f"tel:{phone_clean}" if phone_clean else ""

    wa_url = (links.get("whatsapp") or "").strip()
    if not wa_url and phone_clean:
        wa_url = _wa_from_phone(phone_clean)

    order = [
        ("WhatsApp", wa_url),
        ("Instagram", links.get("instagram")),
        ("Facebook", links.get("facebook")),
        ("TikTok", links.get("tiktok")),
        ("Página web", links.get("website")),
        ("Catálogo", links.get("external_catalog") or links.get("catalog")),
        ("Teléfono", tel_url),
    ]

    chips = []
    for label, url in order:
        url = (url or "").strip()
        if not url:
            continue
        if label.lower().startswith("tel"):
            chips.append(_link_chip(label, url, kind="tel"))
        else:
            chips.append(_link_chip(label, url, kind="url"))

    if chips:
        chips_css = """
        <style>
        .pp-chips, .pp-chips *{
          font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
        }
        .pp-chips{
          display:flex;
          flex-wrap:wrap;
          justify-content:center;
          align-items:center;
          gap:10px;
          padding: 2px 0 10px 0;
          max-width: 980px;
          margin: 0 auto;
        }
        .chip-link{
          display:inline-flex;
          align-items:center;
          gap:8px;
          padding:8px 12px;
          border-radius:999px;
          border:1px solid rgba(109,40,217,0.22);
          background: rgba(109,40,217,0.10);
          box-shadow: 0 10px 24px rgba(2,6,23,0.08);
          text-decoration:none !important;
          font-weight:800;
          font-size:13px;
          color: #1d4ed8 !important;
          line-height:1;
          white-space: nowrap;
        }
        .chip-link:hover{
          background: rgba(109,40,217,0.14);
          border-color: rgba(109,40,217,0.30);
          transform: translateY(-1px);
        }
        .chip-ico{
          width:22px;
          height:22px;
          border-radius:999px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          background: rgba(255,255,255,0.92);
          border: 1px solid rgba(15,23,42,0.10);
          font-size:13px;
        }
        @media (max-width: 520px){
          .pp-chips{gap:8px; max-width: 100%;}
          .chip-link{padding:7px 10px; font-size:12.5px;}
          .chip-ico{width:20px;height:20px;font-size:12.5px;}
        }
        </style>
        """
        components.html(
            chips_css + "<div class='pp-chips'>" + "".join(chips) + "</div>",
            height=140 if len(chips) > 4 else 100,
            scrolling=False
        )

    


    # ---- Tabs como Admin ----
    t_resume, t_products, t_gallery = st.tabs(["📌 Resumen", "🛍️ Productos", "🖼️ Galería"])

    # =========================================================
    # TAB: Resumen
    # =========================================================
    with t_resume:            
        hero_left, hero_right = st.columns([1.5, 2.5], gap="large")

        with hero_left:
            hero = (prof.get("logo_url") or "").strip()
            if hero:
                st.markdown("<div class='pd-hero-wrap'>", unsafe_allow_html=True)
                st.image(hero, use_column_width=True)  # compatible (no use_container_width)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='pd-hero-placeholder'>🛍️</div>", unsafe_allow_html=True)

        with hero_right:
            city = prof.get("city") or "—"
            schedule = prof.get("availability") or "—"
            cats = prof.get("categories") or []
            cats_txt = ", ".join([safe_text(x, 30) for x in cats]) if cats else "—"
            phone_show = phone_clean if phone_clean else "—"

            st.markdown("<div class='pp-card-title'>Información</div>", unsafe_allow_html=True)
            
            # si tu CSS global usa pp-card, lo envolvemos para que se vea “tarjeta”
            st.markdown(
            f"""
            <div class="card">
              <div class="title">📍 Ciudad</div>
              <div class="row" style="margin-top:6px;">
                <span class="price">{safe_text(city, 60)}</span>
              </div>
              <div class="small">{cats_txt}</div>

              <div class="divider"></div>

              <div class="title">🕒 Horario</div>
              <div class="small" style="margin-top:6px;"><b>{safe_text(schedule, 80)}</b></div>
              

              <div class="divider"></div>

              <div class="title">📞 Celular</div>
              <div class="small" style="margin-top:6px;">{safe_text(phone_show, 20)}</div>
            </div>
            """,
            unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("<div class='pp-section-title'>Sobre el emprendimiento</div>", unsafe_allow_html=True)
        long_desc = prof.get("long_desc") or "—"
        st.markdown(f"<div class='pp-long'>{safe_text(long_desc, 2000)}</div>", unsafe_allow_html=True)

    # =========================================================
    # TAB: Productos del emprendimiento
    # =========================================================
    with t_products:
        products_all = db.get("products", []) or []
        profile_id = prof.get("id")

        # Fallback por si en productos se usa owner_user_id en vez de profile_id
        owner_uid = prof.get("owner_user_id") or prof.get("user_id") or ""

        def _is_published(p: dict) -> bool:
            return (p.get("status") or "").strip().upper() == "PUBLISHED"

        my_products = []
        for p in products_all:
            if not _is_published(p):
                continue

            # ✅ match principal por profile_id
            if (p.get("profile_id") == profile_id):
                my_products.append(p)
                continue

            # ✅ fallback por dueño del perfil (si existe en tu modelo)
            if owner_uid and (p.get("owner_user_id") == owner_uid):
                my_products.append(p)

        def _upd(x: dict) -> str:
            return (x.get("updated_at") or x.get("created_at") or "")

        my_products = sorted(my_products, key=_upd, reverse=True)

        st.markdown("### 🛍️ Productos publicados")
        _render_products_grid(my_products)


    # =========================================================
    # TAB: Galería
    # =========================================================
    with t_gallery:
        gallery = prof.get("gallery_urls") or []
        gallery = [x for x in gallery if (x or "").strip()]

        if not gallery:
            st.info("Este emprendimiento aún no ha subido imágenes a la galería.")
        else:
            st.markdown("### 🖼️ Galería")
            cols = st.columns(4)
            for i, url in enumerate(gallery[:20]):
                with cols[i % 4]:
                    st.image(url, use_column_width=True)
