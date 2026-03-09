from __future__ import annotations

import re
import streamlit as st
import streamlit.components.v1 as components

from services.validators import safe_text, safe_html
from auth.session import get_user
from services.analytics import log_view_profile
from services.catalog import format_price
from views.router import goto


# =========================
# Helpers (tel/wa/chips)
# =========================
def _clean_phone(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    raw = re.sub(r"(?!^\+)[^\d]", "", raw)
    return "" if raw == "+" else raw


def _wa_from_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return f"https://wa.me/{digits}" if digits else ""


def _icon_for_label(label: str) -> str:
    low = (label or "").lower()
    if "whats" in low:
        return "📲"
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
    url = (url or "").strip()
    if not url:
        return ""

    icon = _icon_for_label(label)
    label_safe = safe_html(label, 40)
    url_safe = safe_html(url, 500)

    if kind == "tel":
        return (
            f'<a class="chip-link" href="{url_safe}">'
            f'<span class="chip-ico">{icon}</span>'
            f"<span>{label_safe}</span>"
            f"</a>"
        )

    return (
        f'<a class="chip-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">'
        f'<span class="chip-ico">{icon}</span>'
        f"<span>{label_safe}</span>"
        f"</a>"
    )


# =========================
# Helpers (products)
# =========================
def _product_cover_url(pr: dict) -> str:
    if not pr:
        return ""

    for k in ("image_url", "cover_url", "thumbnail_url", "photo_url"):
        v = (pr.get(k) or "").strip()
        if v:
            return v

    for k in ("photo_urls", "image_urls", "photos", "gallery_urls"):
        arr = pr.get(k) or []
        if isinstance(arr, list) and arr:
            v = (arr[0] or "").strip()
            if v:
                return v

    return ""


def _product_price(pr: dict) -> str:
    try:
        return format_price(pr)
    except Exception:
        return "Precio no disponible"


def _render_product_card(pr: dict, key_prefix: str = "pp") -> None:
    title = safe_html(pr.get("name", "Producto"), 80)
    price_txt = safe_html(_product_price(pr), 60)
    cover_url = safe_html(_product_cover_url(pr), 500)
    category = safe_html(pr.get("category", "—"), 30)

    thumb_style = ""
    if cover_url:
        thumb_style = f"background-image:url('{cover_url}');"

    card_html = (
        '<div class="card-wrap">'
        '<div class="card">'
        f'<div class="thumb" style="{thumb_style}">'
        f"<span>{title}</span>"
        "</div>"
        f'<div class="title">{title}</div>'
        '<div class="row">'
        f'<span class="badge">{category}</span>'
        f'<span class="price">{price_txt}</span>'
        "</div>"
        "</div>"
        "</div>"
    )

    st.markdown(card_html, unsafe_allow_html=True)

    if st.button(
        "👀 Ver producto",
        key=f"{key_prefix}_prod_view_{pr.get('id')}",
        width="stretch",
    ):
        st.session_state["entry_source"] = "public_profile_products"
        goto("product_detail", selected_product_id=pr.get("id"))


def _render_products_grid(products: list[dict], key_prefix: str = "pp") -> None:
    if not products:
        st.info("Este emprendimiento aún no tiene productos publicados.")
        return

    cols = st.columns(3, gap="large")
    for i, pr in enumerate(products):
        with cols[i % 3]:
            _render_product_card(pr, key_prefix=f"{key_prefix}_{i}")


# =========================
# Instagram embed
# =========================
_IG_DOMAIN_RE = re.compile(r"^https?://(www\.)?instagram\.com/", re.IGNORECASE)
_IG_POST_RE = re.compile(r"^https?://(www\.)?instagram\.com/(p|reel|tv)/", re.IGNORECASE)


def _normalize_instagram_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    url = url.split("?")[0].strip()
    if _IG_DOMAIN_RE.match(url) and not _IG_POST_RE.match(url):
        if not url.endswith("/"):
            url += "/"
    return url


def _render_instagram_section(insta_url: str) -> None:
    insta_url = _normalize_instagram_url(insta_url)

    if not insta_url:
        st.info("Este emprendimiento no tiene Instagram configurado.")
        return

    if not _IG_DOMAIN_RE.match(insta_url):
        st.warning("El enlace de Instagram no parece válido.")
        return

    st.markdown(
        '<div class="muted">*Si el perfil o la publicación es privada, Instagram puede no mostrar el contenido aquí.*</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    html = f"""
    <div style="display:flex;justify-content:center;">
      <blockquote class="instagram-media"
        data-instgrm-permalink="{insta_url}"
        data-instgrm-version="14"
        style="background:#FFF;border:0;margin:0;max-width:540px;min-width:326px;padding:0;width:99.375%;">
      </blockquote>
    </div>
    <script async src="https://www.instagram.com/embed.js"></script>
    """

    height = 760 if _IG_POST_RE.match(insta_url) else 980
    components.html(html, height=height, scrolling=False)

    st.write("")
    st.markdown(f"🔗 Abrir en Instagram: {insta_url}")


# =========================
# Main render
# =========================
def render(db):
    pid = st.session_state.get("selected_profile_id")
    if not pid:
        st.warning("No hay perfil seleccionado.")
        return

    prof = next((p for p in (db.get("profiles", []) or []) if p.get("id") == pid), None)
    if not prof:
        st.error("Perfil no encontrado.")
        return

    st.session_state.setdefault("entry_source", "public_profile")

    # ---- analytics view ----
    u = get_user()
    log_view_profile(
        profile_id=prof.get("id"),
        user_id=(u or {}).get("id"),
        meta={
            "entry_source": st.session_state.get("entry_source") or st.session_state.get("last_route", "public_profile"),
            "page_context": "public_profile",
        },
    )

    links = prof.get("links") or {}

    phone_clean = _clean_phone(links.get("phone", ""))
    tel_url = f"tel:{phone_clean}" if phone_clean else ""

    wa_url = (links.get("whatsapp") or "").strip()
    if not wa_url and phone_clean:
        wa_url = _wa_from_phone(phone_clean)

    city = prof.get("city") or "—"
    schedule = prof.get("availability") or "—"
    cats = prof.get("categories") or []
    cats_txt = ", ".join([safe_text(x, 30) for x in cats]) if cats else "—"
    phone_show = phone_clean if phone_clean else "—"

    business_name = safe_html(prof.get("business_name", "Emprendimiento"), 120)
    short_desc = safe_html(prof.get("short_desc", ""), 180)
    long_desc = safe_html(prof.get("long_desc", "") or "—", 3000)
    hero = (prof.get("logo_url") or "").strip()

    # ---- Header hero ----
    head_left, head_right = st.columns([1.2, 1.8], gap="large")

    with head_left:
        if hero:
            st.markdown("<div class='pd-hero-wrap'>", unsafe_allow_html=True)
            st.image(hero, width="stretch")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='pp-hero-placeholder'>🛍️</div>", unsafe_allow_html=True)

    with head_right:
        st.markdown(f"<div class='pp-title'>{business_name}</div>", unsafe_allow_html=True)
        if short_desc:
            st.markdown(f"<div class='pp-sub'>{short_desc}</div>", unsafe_allow_html=True)

        st.write("")

        info_html = (
            '<div class="pp-card">'
            '<div class="pp-card-title">Información clave</div>'
            '<div class="pp-kv">'
            '<div class="pp-k">📍 Ciudad</div>'
            f'<div class="pp-v">{safe_html(city, 60)}</div>'
            "</div>"
            '<div class="pp-kv">'
            '<div class="pp-k">🏷️ Categorías</div>'
            f'<div class="pp-v">{safe_html(cats_txt, 120)}</div>'
            "</div>"
            '<div class="pp-kv">'
            '<div class="pp-k">🕒 Horario</div>'
            f'<div class="pp-v">{safe_html(schedule, 80)}</div>'
            "</div>"
            '<div class="pp-kv">'
            '<div class="pp-k">📞 Celular</div>'
            f'<div class="pp-v">{safe_html(phone_show, 20)}</div>'
            "</div>"
            "</div>"
        )
        st.markdown(info_html, unsafe_allow_html=True)

    st.write("")

    # ---- Chips / contactos ----
    order = [
        ("WhatsApp", wa_url),
        ("Instagram", links.get("instagram")),
        ("Teléfono", tel_url),
        ("Facebook", links.get("facebook")),
        ("TikTok", links.get("tiktok")),
        ("Página web", links.get("website")),
        ("Catálogo", links.get("external_catalog") or links.get("catalog")),
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
            scrolling=False,
        )

    st.write("")

    # ---- Tabs ----
    insta_url = (links.get("instagram") or "").strip()
    tabs = ["📌 Resumen", "🖼️ Galería"]
    if insta_url:
        tabs.append("📸 Instagram")

    tab_objs = st.tabs(tabs)

    t_resume = tab_objs[0]
    t_gallery = tab_objs[1]
    t_insta = tab_objs[2] if insta_url else None

    # =========================================================
    # TAB: Resumen
    # =========================================================
    with t_resume:
        st.markdown("<div class='pp-section-title'>Sobre el emprendimiento</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pp-long'>{long_desc}</div>", unsafe_allow_html=True)

        st.write("")

        products_all = db.get("products", []) or []
        profile_id = prof.get("id")
        owner_uid = prof.get("owner_user_id") or prof.get("user_id") or ""

        def _is_published(p: dict) -> bool:
            return (p.get("status") or "").strip().upper() == "PUBLISHED"

        my_products = []
        for p in products_all:
            if not _is_published(p):
                continue
            if p.get("profile_id") == profile_id:
                my_products.append(p)
                continue
            if owner_uid and (p.get("owner_user_id") == owner_uid):
                my_products.append(p)

        def _upd(x: dict) -> str:
            return (x.get("updated_at") or x.get("created_at") or "")

        my_products = sorted(my_products, key=_upd, reverse=True)

        if my_products:
            st.markdown("<div class='pp-section-title'>Productos destacados</div>", unsafe_allow_html=True)
            preview = my_products[:3]
            _render_products_grid(preview, key_prefix="pp_resume")

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
                    st.image(url, width="stretch")

    # =========================================================
    # TAB: Instagram
    # =========================================================
    if t_insta:
        with t_insta:
            st.markdown("### 📸 Instagram")
            _render_instagram_section(insta_url)