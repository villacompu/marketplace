from __future__ import annotations

import re
import html
import streamlit as st

from services.validators import safe_text
from views.router import goto
from services.analytics import log_view_directory, log_contact_click
from db.repo_json import save_db
from auth.session import get_user


def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_tel(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    v = re.sub(r"\s+", "", v)
    v = re.sub(r"(?!^\+)[^\d]", "", v)
    return "" if v == "+" else v


def _wa_href(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    low = v.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return v
    num = _norm_tel(v).replace("+", "")
    return f"https://wa.me/{num}" if num else ""


def _ig_href(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    low = v.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return v
    user = v.replace("@", "").strip()
    return f"https://instagram.com/{user}" if user else ""


def _tel_href(v: str) -> str:
    v = _norm_tel(v)
    return f"tel:{v}" if v else ""


def _is_profile_public_allowed(db: dict, prof: dict) -> bool:
    if not prof:
        return False

    if not bool(prof.get("is_approved")):
        return False

    owner_id = prof.get("owner_user_id") or prof.get("user_id")
    if owner_id:
        u = next((x for x in (db.get("users", []) or []) if x.get("id") == owner_id), None)
        if u and (u.get("status") or "").upper() != "ACTIVE":
            return False

    return True


def _profile_cover_url(prof: dict) -> str:
    if not prof:
        return ""

    logo = (prof.get("logo_url") or "").strip()
    if logo:
        return logo

    gallery = prof.get("gallery_urls") or []
    gallery = [x.strip() for x in gallery if (x or "").strip()]
    if gallery:
        return gallery[0]

    return ""


def _profile_categories_text(prof: dict) -> str:
    cats = prof.get("categories") or []
    cats = [safe_text(x, 30) for x in cats if (x or "").strip()]
    return ", ".join(cats) if cats else "—"


def _strip_html(raw: str) -> str:
    """
    Limpia HTML guardado por error dentro de short_desc/long_desc.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""

    # convierte entidades html
    raw = html.unescape(raw)

    # quita script/style si aparecieran
    raw = re.sub(r"<script.*?>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style.*?>.*?</style>", " ", raw, flags=re.I | re.S)

    # quita tags
    raw = re.sub(r"<[^>]+>", " ", raw)

    # colapsa espacios
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _profile_desc_text(prof: dict, max_len: int = 150) -> str:
    raw_desc = (prof.get("short_desc") or "").strip()
    if not raw_desc:
        raw_desc = (prof.get("long_desc") or "").strip()

    raw_desc = _strip_html(raw_desc)
    desc = safe_text(raw_desc, max_len)

    if len(raw_desc) > max_len:
        desc += "…"

    return desc or "—"


def _profile_search_blob(prof: dict) -> str:
    parts = [
        prof.get("business_name", ""),
        _strip_html(prof.get("short_desc", "")),
        _strip_html(prof.get("long_desc", "")),
        prof.get("city", ""),
        " ".join(prof.get("categories") or []),
    ]
    return _norm_text(" ".join(parts))


def render(db: dict):
    st.markdown("## 📇 Directorio de emprendedores")
    st.markdown(
        '<div class="muted">Busca rápido y contacta por WhatsApp / Instagram / Teléfono.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    u = get_user() or {}
    did = log_view_directory(
        db,
        user_id=u.get("id"),
        meta={
            "entry_source": st.session_state.get("entry_source") or st.session_state.get("last_route", "directory"),
            "page_context": "directory",
        },
    )
    if did:
        save_db(db)

    st.session_state.setdefault("entry_source", "directory")

    profiles_all = db.get("profiles", []) or []
    visible_profiles = [p for p in profiles_all if _is_profile_public_allowed(db, p)]

    q = st.text_input(
        "Buscar",
        placeholder="Nombre del emprendimiento, ciudad, categoría...",
        key="dir_q",
    ).strip()

    with st.expander("Filtros (opcional)", expanded=False):
        all_cities = sorted({
            (p.get("city") or "").strip()
            for p in visible_profiles
            if (p.get("city") or "").strip()
        })

        all_categories = sorted({
            c.strip()
            for p in visible_profiles
            for c in (p.get("categories") or [])
            if (c or "").strip()
        })

        city = st.selectbox("Ciudad", ["Todas"] + all_cities, key="dir_city")
        category = st.selectbox("Categoría", ["Todas"] + all_categories, key="dir_category")

    results = []
    qn = _norm_text(q)

    for prof in visible_profiles:
        if qn and qn not in _profile_search_blob(prof):
            continue

        if city != "Todas" and (prof.get("city") or "").strip() != city:
            continue

        if category != "Todas":
            cats = [c.strip() for c in (prof.get("categories") or []) if (c or "").strip()]
            if category not in cats:
                continue

        results.append(prof)

    results = sorted(results, key=lambda x: _norm_text(x.get("business_name", "")))

    st.markdown(
        f'<div class="muted">Mostrando: {len(results)} emprendimiento(s)</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if not results:
        st.info("No hay emprendedores con esos filtros.")
        return

    n_cols = 3
    for i in range(0, len(results), n_cols):
        row = results[i:i + n_cols]
        cols = st.columns(n_cols, gap="large")

        for col, prof in zip(cols, row):
            with col:
                business = safe_text(prof.get("business_name", "Emprendimiento"), 80)
                city_txt = safe_text(prof.get("city", "—"), 40)
                cats_txt = _profile_categories_text(prof)
                desc = _profile_desc_text(prof, max_len=150)

                cover_url = _profile_cover_url(prof)
                thumb_style = ""
                if cover_url:
                    thumb_style = f"background-image:url('{cover_url}');"

                st.markdown('<div class="card-wrap">', unsafe_allow_html=True)

                st.markdown(
                    f"""
                    <div class="card">
                      <div class="thumb" style="{thumb_style}">
                        <span>{business}</span>
                      </div>

                      <div class="title">{business}</div>

                      <div class="row">
                        <span class="badge">📍 {city_txt}</span>
                        <span class="badge badge2">🏷️ {cats_txt}</span>
                      </div>

                      <div class="divider"></div>

                      <div class="small">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown('<div class="card-actions">', unsafe_allow_html=True)

                links = prof.get("links") or {}
                wa_href = _wa_href(links.get("whatsapp") or "")
                ig_href = _ig_href(links.get("instagram") or "")
                tel_href = _tel_href(links.get("phone") or "")

                actions = []
                if wa_href:
                    actions.append(("wa", wa_href, "📲"))
                if ig_href:
                    actions.append(("ig", ig_href, "📸"))
                if tel_href:
                    actions.append(("tel", tel_href, "📞"))

                # perfil siempre va
                actions.append(("profile", "", "👀"))

                btn_cols = st.columns(len(actions), gap="small")

                for btn_col, action in zip(btn_cols, actions):
                    kind, href, label = action
                    with btn_col:
                        if kind == "profile":
                            if st.button(label, key=f"dir_profile_{prof['id']}", use_container_width=True):
                                st.session_state["entry_source"] = "directory_profile_card"
                                goto("public_profile", selected_profile_id=prof["id"])
                        else:
                            st.markdown(
                                f'<a class="btn-contact" href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>',
                                unsafe_allow_html=True,
                            )

                st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)