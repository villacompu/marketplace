from __future__ import annotations

import random
import re
import json

import streamlit as st
import streamlit.components.v1 as components

from auth.session import get_user
from views.router import goto
from services.validators import safe_text, safe_html
from services.catalog import format_price
from services.analytics import track_event, log_contact_click


# =========================================================
# Helpers
# =========================================================
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


def _product_desc(pr: dict, max_len: int = 180) -> str:
    raw = (pr.get("description") or "").strip()
    if not raw:
        return "Sin descripción"
    txt = safe_text(raw, max_len)
    if len(raw) > max_len:
        txt += "…"
    return txt


def _is_public_product_allowed(db: dict, product: dict) -> bool:
    if not product:
        return False

    if (product.get("status") or "").upper() != "PUBLISHED":
        return False

    profile_id = product.get("profile_id")
    prof = next((x for x in (db.get("profiles", []) or []) if x.get("id") == profile_id), None)
    if not prof or not prof.get("is_approved"):
        return False

    owner_id = product.get("owner_user_id")
    if owner_id:
        u = next((x for x in (db.get("users", []) or []) if x.get("id") == owner_id), None)
        if u and (u.get("status") or "").upper() != "ACTIVE":
            return False

    return True


def _build_feed_product_ids(db: dict) -> list[str]:
    products = db.get("products", []) or []
    public_products = [p for p in products if _is_public_product_allowed(db, p)]

    ids = [str(p.get("id")) for p in public_products if p.get("id")]
    random.shuffle(ids)
    return ids


def _get_profile(db: dict, profile_id: str | None) -> dict:
    if not profile_id:
        return {}
    return next((x for x in (db.get("profiles", []) or []) if x.get("id") == profile_id), {}) or {}


def _track_feed_view_once(product_id: str, profile_id: str, user_id: str | None) -> None:
    seen = st.session_state.setdefault("_feed_seen_products", set())
    key = f"{product_id}"
    if key in seen:
        return

    seen.add(key)

    track_event(
        event_type="view_feed_product",
        user_id=user_id,
        product_id=product_id,
        profile_id=profile_id,
        meta={
            "entry_source": "feed",
            "page_context": "feed",
        },
    )


# =========================================================
# Main
# =========================================================
def render(db: dict):
    st.markdown("## 🎬 Explorar productos")
    st.markdown(
        '<div class="muted">Descubre productos de forma rápida.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    u = get_user() or {}

    if "feed_product_ids" not in st.session_state:
        st.session_state["feed_product_ids"] = _build_feed_product_ids(db)
        st.session_state["feed_idx"] = 0
        st.session_state["_feed_seen_products"] = set()

        track_event(
            event_type="view_feed",
            user_id=u.get("id"),
            meta={
                "entry_source": "feed",
                "page_context": "feed",
            },
        )

    feed_ids = st.session_state.get("feed_product_ids", []) or []
    idx = int(st.session_state.get("feed_idx", 0))

    if not feed_ids:
        st.info("No hay productos públicos disponibles para explorar.")
        return

    if idx < 0:
        idx = 0
    if idx >= len(feed_ids):
        idx = len(feed_ids) - 1

    st.session_state["feed_idx"] = idx

    product_id = feed_ids[idx]
    p = next((x for x in (db.get("products", []) or []) if str(x.get("id")) == str(product_id)), None)

    if not p or not _is_public_product_allowed(db, p):
        st.warning("Este producto ya no está disponible. Se actualizará el feed.")
        st.session_state["feed_product_ids"] = _build_feed_product_ids(db)
        st.session_state["feed_idx"] = 0
        st.rerun()
        return

    prof = _get_profile(db, p.get("profile_id"))
    links = prof.get("links") or {}

    _track_feed_view_once(
        product_id=str(p.get("id") or ""),
        profile_id=str(p.get("profile_id") or ""),
        user_id=u.get("id"),
    )

    cover = _product_cover_url(p)
    title = safe_html(p.get("name", "Producto"), 120)
    price = safe_html(format_price(p), 60)
    category = safe_html(p.get("category", "—"), 40)
    desc = safe_html(_product_desc(p, 180), 220)
    business = safe_html(prof.get("business_name", "Emprendimiento"), 80)
    city = safe_html(prof.get("city", "—"), 50)

    wa_href = _wa_href(links.get("whatsapp") or links.get("phone") or "")

    st.markdown(
        """
        <style>
        .feed-shell{
            max-width: 760px;
            margin: 0 auto;
        }
        .feed-counter{
            text-align:center;
            font-size:14px;
            opacity:.75;
            margin-bottom:12px;
        }
        .feed-card{
            border:1px solid rgba(15,23,42,.08);
            border-radius:24px;
            overflow:hidden;
            background:white;
            box-shadow:0 16px 38px rgba(2,6,23,.08);
        }
        .feed-hero{
            width:100%;
            aspect-ratio: 4 / 5;
            background:#f8fafc center center / cover no-repeat;
        }
        .feed-body{
            padding:20px 20px 16px 20px;
        }
        .feed-title{
            font-size:30px;
            font-weight:800;
            line-height:1.1;
            margin-bottom:8px;
        }
        .feed-meta{
            font-size:14px;
            color:#475569;
            margin-bottom:10px;
        }
        .feed-price{
            font-size:24px;
            font-weight:800;
            margin-bottom:10px;
        }
        .feed-desc{
            font-size:15px;
            color:#334155;
            line-height:1.45;
        }
        .feed-badge{
            display:inline-block;
            margin-right:8px;
            margin-bottom:8px;
            padding:6px 10px;
            border-radius:999px;
            background:rgba(109,40,217,0.10);
            border:1px solid rgba(109,40,217,0.18);
            font-size:13px;
            font-weight:700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="feed-shell">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="feed-counter">Producto {idx + 1} de {len(feed_ids)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="feed-card">', unsafe_allow_html=True)

    if cover:
        st.markdown(
            f'<div class="feed-hero" style="background-image:url(\'{safe_html(cover, 600)}\');"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="feed-hero" style="display:flex;align-items:center;justify-content:center;font-size:64px;">🛍️</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="feed-body">', unsafe_allow_html=True)
    st.markdown(f'<div class="feed-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="feed-price">{price}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="feed-meta"><b>{business}</b> · {city}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<span class="feed-badge">{category}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="feed-desc">{desc}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    a1, a2, a3 = st.columns(3, gap="small")

    with a1:
        if st.button("👀 Ver producto", use_container_width=True, key=f"feed_view_product_{product_id}"):
            track_event(
                event_type="feed_open_product",
                user_id=u.get("id"),
                product_id=str(p.get("id") or ""),
                profile_id=str(p.get("profile_id") or ""),
                meta={
                    "entry_source": "feed",
                    "page_context": "feed",
                },
            )
            st.session_state["entry_source"] = "feed"
            goto("product_detail", selected_product_id=p.get("id"))

    with a2:
        if st.button("👤 Ver emprendimiento", use_container_width=True, key=f"feed_view_profile_{product_id}"):
            track_event(
                event_type="feed_open_profile",
                user_id=u.get("id"),
                product_id=str(p.get("id") or ""),
                profile_id=str(p.get("profile_id") or ""),
                meta={
                    "entry_source": "feed",
                    "page_context": "feed",
                },
            )
            st.session_state["entry_source"] = "feed"
            goto("public_profile", selected_profile_id=p.get("profile_id"))

    with a3:
        if wa_href:
            if st.button("📲 WhatsApp", use_container_width=True, key=f"feed_whatsapp_{product_id}"):
                log_contact_click(
                    kind="whatsapp",
                    product_id=str(p.get("id") or ""),
                    profile_id=str(p.get("profile_id") or ""),
                    user_id=u.get("id"),
                    meta={
                        "entry_source": "feed_contact",
                        "page_context": "feed",
                    },
                )
                _open_url(wa_href, same_tab=False)
        else:
            st.button("📲 WhatsApp", use_container_width=True, key=f"feed_whatsapp_disabled_{product_id}", disabled=True)

    st.write("")

    n1, n2, n3 = st.columns([1, 1.3, 1], gap="small")

    with n1:
        prev_disabled = idx <= 0
        if st.button("⬆️ Anterior", use_container_width=True, disabled=prev_disabled, key=f"feed_prev_{idx}"):
            st.session_state["feed_idx"] = max(0, idx - 1)
            track_event(
                event_type="feed_prev",
                user_id=u.get("id"),
                product_id=str(p.get("id") or ""),
                profile_id=str(p.get("profile_id") or ""),
                meta={
                    "entry_source": "feed",
                    "page_context": "feed",
                },
            )
            st.rerun()

    with n2:
        if st.button("🔀 Mezclar feed", use_container_width=True, key=f"feed_shuffle_{idx}"):
            st.session_state["feed_product_ids"] = _build_feed_product_ids(db)
            st.session_state["feed_idx"] = 0
            st.session_state["_feed_seen_products"] = set()

            track_event(
                event_type="feed_shuffle",
                user_id=u.get("id"),
                meta={
                    "entry_source": "feed",
                    "page_context": "feed",
                },
            )
            st.rerun()

    with n3:
        next_disabled = idx >= (len(feed_ids) - 1)
        if st.button("⬇️ Siguiente", use_container_width=True, disabled=next_disabled, key=f"feed_next_{idx}"):
            st.session_state["feed_idx"] = min(len(feed_ids) - 1, idx + 1)
            track_event(
                event_type="feed_next",
                user_id=u.get("id"),
                product_id=str(p.get("id") or ""),
                profile_id=str(p.get("profile_id") or ""),
                meta={
                    "entry_source": "feed",
                    "page_context": "feed",
                },
            )
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)