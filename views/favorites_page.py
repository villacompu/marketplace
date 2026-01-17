from __future__ import annotations
import streamlit as st

from services.favorites import list_favorites, toggle_favorite
from services.catalog import format_price
from services.validators import safe_text
from db.repo_json import find_product, find_profile
from views.router import goto


def render(db):
    # ✅ Back siempre visible
    st.markdown("## ❤️ Favoritos")
    st.markdown('<div class="muted">Tus productos guardados en un solo lugar.</div>', unsafe_allow_html=True)
    st.write("")

    fav_ids = list_favorites(db)

    if not fav_ids:
        st.info("Aún no tienes favoritos. Ve al catálogo y marca ♡.")
        return

    # Cargar productos válidos
    items = []
    for pid in fav_ids:
        p = find_product(db, pid)
        if not p or p.get("status") != "PUBLISHED":
            continue
        prof = find_profile(db, p.get("profile_id", ""))
        if not prof or not prof.get("is_approved", False):
            continue
        items.append({**p, "_profile": prof})

    if not items:
        st.warning("Tus favoritos ya no están disponibles (ocultos o no publicados).")
        return

    # Render en grilla (3 columnas) usando card-wrap + action bar
    n_cols = 3
    for i in range(0, len(items), n_cols):
        row = items[i:i+n_cols]
        cols = st.columns(n_cols, gap="medium")

        for col, p in zip(cols, row):
            prof = p["_profile"]
            price = format_price(p.get("price_type"), p.get("price_value"))
            badge = p.get("category", "—")
            city_txt = prof.get("city") or "—"
            owner = prof.get("business_name") or "Emprendimiento"

            desc = safe_text(p.get("description", ""), 110)
            if len(p.get("description", "")) > 110:
                desc += "…"

            with col:
                st.markdown('<div class="card-wrap">', unsafe_allow_html=True)

                st.markdown(
                    f"""
                    <div class="card">
                      <div class="thumb"><span>{safe_text(owner, 40)}</span></div>
                      <div class="title">{safe_text(p.get("name",""), 70)}</div>
                      <div class="row">
                        <span class="badge">{safe_text(badge, 30)}</span>
                        <span class="price">{price}</span>
                      </div>
                      <div class="divider"></div>
                      <div class="small">{desc}</div>
                      <div class="row" style="margin-top:10px;">
                        <span class="badge badge2">{safe_text(city_txt, 30)}</span>
                        <span class="small">Guardado</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown('<div class="card-actions">', unsafe_allow_html=True)
                b1, b2, b3 = st.columns([1.6, 0.6, 0.6])

                with b1:
                    st.markdown('<div class="btn-view">', unsafe_allow_html=True)
                    if st.button("👁️ Ver", key=f"fav_view_{p['id']}", use_container_width=True):
                        goto("product_detail", selected_product_id=p["id"])
                    st.markdown('</div>', unsafe_allow_html=True)

                with b2:
                    st.markdown('<div class="btn-ico">', unsafe_allow_html=True)
                    if st.button("👤", key=f"fav_biz_{p['id']}", use_container_width=True, help="Ver emprendimiento"):
                        goto("public_profile", selected_profile_id=prof["id"])
                    st.markdown('</div>', unsafe_allow_html=True)

                with b3:
                    st.markdown('<div class="btn-ico">', unsafe_allow_html=True)
                    if st.button("💔", key=f"fav_rm_{p['id']}", use_container_width=True, help="Quitar de favoritos"):
                        toggle_favorite(db, p["id"])
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)  # close card-actions
                st.markdown('</div>', unsafe_allow_html=True)  # close card-wrap
