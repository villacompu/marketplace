from __future__ import annotations
import streamlit as st

from services.catalog import filter_products, format_price
from services.validators import safe_text
from views.router import goto
from services.favorites import is_favorite, toggle_favorite, list_favorites
from services.featured import get_featured_products

from services.analytics import log_view_home, log_search
from db.repo_json import save_db
from auth.session import get_user


PAGE_STEP = 9  # 3 cols x 3 filas


def _sig(q: str, category: str, city: str, tag: str, price_range: tuple[int, int], sort_by: str) -> str:
    return f"{q}|{category}|{city}|{tag}|{price_range[0]}-{price_range[1]}|{sort_by}"


def render(db):
    st.markdown("## Descubre productos y servicios locales")
    st.markdown('<div class="muted">Busca productos y servicios de emprendedores locales.</div>', unsafe_allow_html=True)
    st.write("")

    # -----------------------------
    # Estado buscador (draft vs aplicado)
    # -----------------------------
    st.session_state.setdefault("global_q", "")
    st.session_state.setdefault("global_q_draft", "")
    st.session_state.setdefault("home_limit", PAGE_STEP)
    st.session_state.setdefault("home_sig", "")

    # ✅ 1) Track view_home (dedupe por sesión)
    u = get_user()
    did = log_view_home(db, user_id=(u or {}).get("id"))
    if did:
        save_db(db)


    # Buscador superior centrado + botones
    _, mid, _ = st.columns([1, 2.5, 1])
    with mid:
        q_draft = st.text_input(
            "Buscar",
            value=st.session_state["global_q_draft"],
            placeholder="Ej: crispetas, galletas, brownies, mantenimiento…",
            label_visibility="collapsed",
            key="global_q_input_draft",
        )
        st.session_state["global_q_draft"] = q_draft

        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("Buscar", use_container_width=True):
                st.session_state["global_q"] = (st.session_state["global_q_draft"] or "").strip()
                st.session_state["home_limit"] = PAGE_STEP  # ✅ reset
                st.rerun()
        with b2:
            if st.button("Mostrar todo", use_container_width=True):
                st.session_state["global_q"] = ""
                st.session_state["global_q_draft"] = ""
                st.session_state["home_limit"] = PAGE_STEP  # ✅ reset
                st.rerun()

    st.write("")
    q = st.session_state.get("global_q", "")

    # ✅ Botón visible solo si hay al menos 1 favorito
    fav_ids = list_favorites(db)
    fav_count = len(fav_ids)

    top_left, top_right = st.columns([3, 1])
    with top_right:
        if fav_count > 0:
            if st.button(f"❤️ Favoritos ({fav_count})", use_container_width=True):
                st.session_state["route"] = "favorites"
                st.rerun()

    # -----------------------------
    # Sidebar filtros
    # -----------------------------
    st.sidebar.header("Filtros")

    all_categories = sorted({
        p.get("category", "") for p in db.get("products", [])
        if p.get("status") == "PUBLISHED" and p.get("category")
    })
    all_cities = sorted({
        pr.get("city", "") for pr in db.get("profiles", [])
        if pr.get("is_approved") and pr.get("city")
    })
    all_tags = sorted({t for pr in db.get("products", []) for t in (pr.get("tags") or [])})

    # Keys estables
    st.session_state.setdefault("home_cat", "Todas")
    st.session_state.setdefault("home_city", "Todas")
    st.session_state.setdefault("home_tag", "Todos")
    st.session_state.setdefault("home_sort", "Relevancia")

    category = st.sidebar.selectbox("Categoría", ["Todas"] + all_categories, key="home_cat")
    city = st.sidebar.selectbox("Ciudad", ["Todas"] + all_cities, key="home_city")
    tag = st.sidebar.selectbox("Etiquetas", ["Todos"] + all_tags, key="home_tag")

    numeric_prices = [
        p["price_value"] for p in db.get("products", [])
        if p.get("status") == "PUBLISHED" and isinstance(p.get("price_value"), (int, float))
    ]
    if numeric_prices:
        min_price = int(min(numeric_prices))
        max_price = int(max(numeric_prices))
        # Key estable
        st.session_state.setdefault("home_price_min", min_price)
        st.session_state.setdefault("home_price_max", max_price)
        # Si cambia el rango global, ajusta defaults sin romper
        if st.session_state["home_price_min"] != min_price or st.session_state["home_price_max"] != max_price:
            st.session_state["home_price_min"] = min_price
            st.session_state["home_price_max"] = max_price


        price_range = st.sidebar.slider(
            "Rango de precio",
            min_value=min_price,
            max_value=max_price,
            value=st.session_state.get("home_price_range", (min_price, max_price)),
            key="home_price_range",
        )
    else:
        price_range = (0, 10**9)

    sort_by = st.sidebar.selectbox("Ordenar", ["Relevancia", "Más recientes", "Precio ↑", "Precio ↓"], key="home_sort")

    # -----------------------------
    # Reset automático paginación cuando cambian filtros/busqueda
    # -----------------------------
    current_sig = _sig(q, category, city, tag, price_range, sort_by)
    if st.session_state.get("home_sig", "") != current_sig:
        st.session_state["home_sig"] = current_sig
        st.session_state["home_limit"] = PAGE_STEP

    # -----------------------------
    # Resultados filtrados (completo) + corte por paginación
    # -----------------------------
    results_all = filter_products(db, q, category, city, tag, price_range, sort_by)

    # ✅ 2) Track search (dedupe por sesión, solo si hay búsqueda o filtros activos)
    # Nota: puedes registrar siempre; yo lo registro cuando hay "intención" (q o filtros ≠ default).
    has_intent = bool((q or "").strip()) or category != "Todas" or city != "Todas" or tag != "Todos" or sort_by != "Relevancia"
    if has_intent:
        filters = {
            "category": category,
            "city": city,
            "tag": tag,
            "price_range": [int(price_range[0]), int(price_range[1])],
            "sort_by": sort_by,
        }
        if log_search(db, q=q, filters=filters, results_n=len(results_all), user_id=(u.get("id") if u else None)):
            save_db(db)

    st.markdown("### Resultados")
    info_txt = f"{len(results_all)} publicación(es) encontrada(s)"
    if q:
        info_txt += f" para “{safe_text(q, 60)}”"
    st.markdown(f'<div class="muted">{info_txt}</div>', unsafe_allow_html=True)
    st.write("")

    if not results_all:
        st.info("No hay resultados con esos filtros. Prueba otra búsqueda o quita filtros.")
        return

    limit = int(st.session_state.get("home_limit", PAGE_STEP))
    results = results_all[:limit]

    # -----------------------------
    # Grilla real (3 columnas)
    # -----------------------------
    n_cols = 3
    for i in range(0, len(results), n_cols):
        row = results[i:i + n_cols]
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

                photos = p.get("photo_urls") or []
                photos = [u.strip() for u in photos if (u or "").strip()]
                thumb_url = photos[0] if photos else ""
                thumb_style = f"background-image:url('{thumb_url}');" if thumb_url else ""

                st.markdown(
                    f"""
                    <div class="card">
                      <div class="thumb" style="{thumb_style}">
                        <span>{safe_text(owner, 40)}</span>
                      </div>

                      <div class="title">{safe_text(p.get("name",""), 70)}</div>

                      <div class="row">
                        <span class="badge">{safe_text(badge, 30)}</span>
                        <span class="price">{price}</span>
                      </div>

                      <div class="divider"></div>

                      <div class="small">{desc}</div>

                      <div class="row" style="margin-top:10px;">
                        <span class="badge badge2">{safe_text(city_txt, 30)}</span>
                        <span class="small">Publicado</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown('<div class="actions-3">', unsafe_allow_html=True)
                b1, b2, b3 = st.columns([1.6, 0.5, 0.5], gap="small")

                with b1:
                    st.markdown('<div class="btn-view">', unsafe_allow_html=True)
                    if st.button("👁️ Ver", key=f"view_{p['id']}", use_container_width=True):
                        goto("product_detail", selected_product_id=p["id"])
                    st.markdown('</div>', unsafe_allow_html=True)

                with b2:
                    st.markdown('<div class="btn-ico">', unsafe_allow_html=True)
                    if st.button("👤", key=f"biz_{p['id']}", use_container_width=True, help="Ver emprendimiento"):
                        goto("public_profile", selected_profile_id=prof["id"])
                    st.markdown('</div>', unsafe_allow_html=True)

                with b3:
                    st.markdown('<div class="btn-fav">', unsafe_allow_html=True)
                    fav = is_favorite(db, p["id"])
                    if st.button("❤️" if fav else "♡", key=f"fav_{p['id']}", use_container_width=True, help="Guardar en favoritos"):
                        toggle_favorite(db, p["id"])
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("</div></div>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Cargar más
    # -----------------------------
    if len(results_all) > len(results):
        st.write("")
        _, mid_btn, _ = st.columns([1, 1.2, 1])
        with mid_btn:
            if st.button(f"➕ Cargar más ({len(results)} / {len(results_all)})", use_container_width=True):
                st.session_state["home_limit"] = min(len(results_all), limit + PAGE_STEP)
                st.rerun()

    # ============================
    # ⭐ Destacados (si existen)
    # ============================
    st.divider()
    featured_prod_ids = get_featured_products(db)
    if featured_prod_ids:
        by_id = {p.get("id"): p for p in db.get("products", []) if (p.get("status") or "").upper() == "PUBLISHED"}
        feat = [by_id.get(pid) for pid in featured_prod_ids]
        feat = [p for p in feat if p]

        if feat:
            st.markdown("### ⭐ Destacados")
            st.write("")

            n_cols = 3
            for i in range(0, len(feat), n_cols):
                row = feat[i:i+n_cols]
                cols = st.columns(n_cols, gap="medium")
                for col, p in zip(cols, row):
                    prof = next((x for x in db.get("profiles", []) if x.get("id") == p.get("profile_id")), {}) or {}
                    price = format_price(p.get("price_type"), p.get("price_value"))
                    badge = p.get("category", "—")
                    city_txt = prof.get("city") or "—"
                    owner = prof.get("business_name") or "Emprendimiento"

                    desc = safe_text(p.get("description", ""), 110)
                    if len(p.get("description", "")) > 110:
                        desc += "…"

                    with col:
                        st.markdown('<div class="card-wrap">', unsafe_allow_html=True)

                        photos = p.get("photo_urls") or []
                        photos = [u.strip() for u in photos if (u or "").strip()]
                        thumb_url = photos[0] if photos else ""
                        thumb_style = f"background-image:url('{thumb_url}');" if thumb_url else ""

                        st.markdown(
                            f"""
                            <div class="card">
                            <div class="thumb" style="{thumb_style}">
                                <span>{safe_text(owner, 40)}</span>
                            </div>

                            <div class="title">{safe_text(p.get("name",""), 70)}</div>
                            <div class="row">
                                <span class="badge">{safe_text(badge, 30)}</span>
                                <span class="price">{price}</span>
                            </div>
                            <div class="divider"></div>
                            <div class="small">{desc}</div>
                            <div class="row" style="margin-top:10px;">
                                <span class="badge badge2">{safe_text(city_txt, 30)}</span>
                                <span class="small">Destacado</span>
                            </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        st.markdown('<div class="card-actions"><div class="actions-3">', unsafe_allow_html=True)
                        b1, b2, b3 = st.columns([1.6, 0.5, 0.5], gap="small")

                        with b1:
                            st.markdown('<div class="btn-view">', unsafe_allow_html=True)
                            if st.button("👁️ Ver", key=f"feat_view_{p['id']}", use_container_width=True):
                                goto("product_detail", selected_product_id=p["id"])
                            st.markdown('</div>', unsafe_allow_html=True)

                        with b2:
                            st.markdown('<div class="btn-ico">', unsafe_allow_html=True)
                            if st.button("👤", key=f"feat_biz_{p['id']}", use_container_width=True, help="Ver emprendimiento"):
                                goto("public_profile", selected_profile_id=prof.get("id"))
                            st.markdown('</div>', unsafe_allow_html=True)

                        with b3:
                            st.markdown('<div class="btn-fav">', unsafe_allow_html=True)
                            fav = is_favorite(db, p["id"])
                            if st.button("❤️" if fav else "♡", key=f"feat_fav_{p['id']}", use_container_width=True):
                                toggle_favorite(db, p["id"])
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

                        st.markdown("</div></div>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

            st.write("")
            st.divider()
