from __future__ import annotations

import streamlit as st

from auth.session import get_user
from db.repo_json import save_db, new_id, now_iso
from services.validators import safe_text
from views.router import goto
from services.tag_catalog import tags_for_category
from services.limits import can_publish_more, count_published_products, get_publish_limit




def _get_my_profile(db, user_id: str):
    return next((p for p in db.get("profiles", []) if p.get("owner_user_id") == user_id), None)


def _parse_urls(raw: str, max_n: int = 6):
    raw = (raw or "").strip()
    if not raw:
        return []
    parts = []
    for line in raw.replace(",", "\n").splitlines():
        u = (line or "").strip()
        if u:
            parts.append(u)
    return parts[:max_n]


def _clear_form_keys(suffix: str):
    """Borra solo las keys del formulario actual (edit_id o 'new')."""
    keys = [
        f"mp_name_{suffix}",
        f"mp_desc_{suffix}",
        f"mp_category_{suffix}",
        f"mp_tags_{suffix}",
        f"mp_tag_suggest_{suffix}",
        f"mp_price_type_{suffix}",
        f"mp_price_value_{suffix}",
        f"mp_photos_raw_{suffix}",
        f"mp_status_{suffix}",
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]


def render(db):
    u = get_user()
    if not u:
        st.warning("Debes iniciar sesión.")
        if st.button("Ir a login"):
            st.session_state["route"] = "login"
            st.rerun()
        return

    if u.get("role") != "EMPRENDEDOR":
        st.error("Solo emprendedores pueden gestionar productos.")
        return

    prof = _get_my_profile(db, u["id"])
    if not prof:
        st.error("No tienes perfil asociado.")
        return

    st.markdown("## Mis productos / servicios")
    approved = bool(prof.get("is_approved"))
    
    # ✅ Cargar usuario REAL desde db (no el cache de sesión)
    u_db = next((x for x in db.get("users", []) if x.get("id") == u.get("id")), None) or u

    # ✅ Default solo si en DB no existe (NO en sesión)
    if "max_published_products" not in u_db or u_db.get("max_published_products") is None:
        u_db["max_published_products"] = 5
        u_db["updated_at"] = now_iso()
        save_db(db)

    # (opcional) refrescar sesión para que quede consistente
    u["max_published_products"] = u_db.get("max_published_products", 5)

    limit = get_publish_limit(u_db)                # -1 = ilimitado
    used = count_published_products(db, u_db["id"]) # cuántos PUBLISHED tiene

    limit_txt = "Ilimitado" if limit == -1 else str(limit)

    st.markdown(
        f'<div class="muted">Publicados: <b>{used}/{limit_txt}</b></div>',
        unsafe_allow_html=True
    )

    if not approved:
        st.info("Tu perfil está pendiente de aprobación. Puedes crear borradores, pero no publicar.")

    # Mis productos
    my_items = [p for p in db.get("products", []) if p.get("owner_user_id") == u["id"]]
    my_items = sorted(my_items, key=lambda x: x.get("created_at", ""), reverse=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("➕ Nuevo producto", use_container_width=True):
            st.session_state["mp_edit_id"] = None
            st.session_state["mp_mode"] = "edit"
            st.rerun()
    with c2:
        if st.button("🏪 Volver a mi perfil", use_container_width=True):
            goto("my_profile")

    st.write("")

    mode = st.session_state.get("mp_mode", "list")
    edit_id = st.session_state.get("mp_edit_id")

    # ===========================
    # FORM (crear/editar)
    # ===========================
    if mode == "edit":
        item = None
        if edit_id:
            item = next(
                (p for p in db.get("products", [])
                 if p.get("id") == edit_id and p.get("owner_user_id") == u["id"]),
                None
            )
            if not item:
                st.error("Producto no encontrado.")
                st.session_state["mp_mode"] = "list"
                st.rerun()

        st.markdown("### " + ("Editar producto" if item else "Nuevo producto"))

        # ✅ Sufijo estable (evita el warning de Streamlit al editar distintos productos)
        suffix = edit_id if edit_id else "new"

        # ✅ Keys únicas por formulario (por producto)
        k_name = f"mp_name_{suffix}"
        k_desc = f"mp_desc_{suffix}"
        k_category = f"mp_category_{suffix}"
        k_tags = f"mp_tags_{suffix}"
        k_tag_suggest = f"mp_tag_suggest_{suffix}"
        k_price_type = f"mp_price_type_{suffix}"
        k_price_value = f"mp_price_value_{suffix}"
        k_photos_raw = f"mp_photos_raw_{suffix}"
        k_status = f"mp_status_{suffix}"

        # ✅ Valores iniciales (NO setdefault)
        init_name = item.get("name", "") if item else ""
        init_desc = item.get("description", "") if item else ""
        init_category = item.get("category", "Comida") if item else "Comida"
        init_tags = item.get("tags", []) if item else []
        init_tag_suggest = item.get("tag_suggestion", "") if item else ""
        init_price_type = item.get("price_type", "FIXED") if item else "FIXED"
        init_price_value = float(item.get("price_value") or 0) if item else 0.0
        init_photos_raw = "\n".join((item.get("photo_urls", []) or [])[:6]) if item else ""
        init_status = item.get("status", "DRAFT") if item else "DRAFT"

        name = st.text_input("Nombre", value=init_name, key=k_name)
        desc = st.text_area("Descripción", value=init_desc, height=120, key=k_desc)

        colA, colB = st.columns([1, 1])
        with colA:
            category = st.selectbox(
                "Categoría",
                ["Comida", "Moda", "Servicios", "Tecnología", "Hogar", "Salud", "Educación", "Arte"],
                index=["Comida", "Moda", "Servicios", "Tecnología", "Hogar", "Salud", "Educación", "Arte"].index(init_category)
                if init_category in ["Comida", "Moda", "Servicios", "Tecnología", "Hogar", "Salud", "Educación", "Arte"] else 0,
                key=k_category,
            )

            # ✅ Tags CONTROLADOS por categoría (NO ensuciar catálogo)
            base_options = tags_for_category(category)

            # ✅ Para no romper si hay tags viejos guardados
            tag_options = sorted(set(base_options + (init_tags or [])))

            tags = st.multiselect(
                "Tags (elige hasta 5)",
                options=tag_options,
                default=[t for t in (init_tags or []) if t in tag_options],
                key=k_tags,
            )

            if len(tags) > 5:
                st.warning("Máximo 5 tags por producto.")
                tags = tags[:5]
                # reflejar en session_state del widget actual
                st.session_state[k_tags] = tags

            tag_suggest = st.text_input(
                "¿No está tu tag? Sugiere 1 para revisar en una proxima actualización (opcional)",
                value=init_tag_suggest,
                placeholder="Ej: 'Urgente', '24/7', 'Sin gluten'...",
                key=k_tag_suggest,
            ).strip()

        with colB:
            price_type = st.selectbox(
                "Precio",
                ["FIXED", "FROM", "AGREE"],
                index=["FIXED", "FROM", "AGREE"].index(init_price_type) if init_price_type in ["FIXED", "FROM", "AGREE"] else 0,
                format_func=lambda v: {"FIXED": "Fijo", "FROM": "Desde", "AGREE": "A convenir"}[v],
                key=k_price_type
            )

            price_value = st.number_input(
                "Valor (COP, si aplica)",
                min_value=0,
                step=1000,
                value=int(init_price_value or 0),
                format="%d",
                key=k_price_value,
                disabled=(price_type == "AGREE"),
            )


            status = st.selectbox(
                "Estado",
                ["DRAFT", "PUBLISHED", "PAUSED"],
                index=["DRAFT", "PUBLISHED", "PAUSED"].index(init_status) if init_status in ["DRAFT", "PUBLISHED", "PAUSED"] else 0,
                format_func=lambda v: {"DRAFT": "Borrador", "PUBLISHED": "Publicado", "PAUSED": "Pausado"}[v],
                key=k_status,
            )

        photos_raw = st.text_area(
            "Fotos (URLs, una por línea o separadas por coma) — máximo 6",
            value=init_photos_raw,
            key=k_photos_raw,
            height=110
        )
        photo_urls = _parse_urls(photos_raw, max_n=6)

        # --- Preview fotos antes de guardar ---
        st.markdown("**Vista previa**")
        if photo_urls:
            cols = st.columns(min(3, len(photo_urls)))
            for i, url in enumerate(photo_urls):
                with cols[i % len(cols)]:
                    st.image(url, use_column_width=True)
        else:
            st.caption("Agrega URLs de imágenes para ver la vista previa aquí.")

        # ✅ Límite: si intenta publicar, validar cupo
        exclude_id = item.get("id") if item else None

        if status == "PUBLISHED" and not can_publish_more(db, u, exclude_product_id=exclude_id):
            limit = get_publish_limit(u)
            used = count_published_products(db, u["id"], exclude_product_id=exclude_id)
            limit_txt = "Ilimitado" if limit == -1 else str(limit)

            st.warning(f"Has alcanzado tu límite de publicación ({used}/{limit_txt}). Se guardará como borrador.")
            status = "DRAFT"



        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("💾 Guardar", use_container_width=True, key=f"mp_save_{suffix}"):
                if not (name or "").strip():
                    st.error("El nombre es obligatorio.")
                    st.stop()

                now = now_iso()

                payload = {
                    "name": name.strip()[:80],
                    "description": (desc or "").strip()[:2000],
                    "category": category,
                    "tags": tags,
                    "tag_suggestion": (tag_suggest[:40] if tag_suggest else ""),
                    "price_type": price_type,
                    "price_value": int(price_value) if price_type != "AGREE" else None,
                    "photo_urls": photo_urls,
                    "status": status,
                    "updated_at": now,
                }

                if item:
                    item.update(payload)
                else:
                    db.setdefault("products", []).append({
                        "id": new_id(),
                        "owner_user_id": u["id"],
                        "profile_id": prof["id"],
                        "created_at": now,
                        **payload,
                    })

                save_db(db)

                # ✅ limpiar estado SOLO del form actual
                _clear_form_keys(suffix)

                st.session_state["mp_mode"] = "list"
                st.session_state["mp_edit_id"] = None
                st.success("Guardado.")
                st.rerun()

        with b2:
            if st.button("↩️ Cancelar", use_container_width=True, key=f"mp_cancel_{suffix}"):
                _clear_form_keys(suffix)
                st.session_state["mp_mode"] = "list"
                st.session_state["mp_edit_id"] = None
                st.rerun()

        return

    # ===========================
    # LISTADO (cards bonitas)
    # ===========================
    if not my_items:
        st.info("Aún no tienes productos. Crea el primero con “Nuevo producto”.")
        return

    # Grid 2 columnas (1 en móvil)
    st.markdown("<div class='mp-grid'>", unsafe_allow_html=True)

    for p in my_items:
        name = safe_text(p.get("name", ""), 80)
        desc = (p.get("description", "") or "").strip()
        desc_short = safe_text(desc, 160) + ("…" if len(desc) > 160 else "")

        category = safe_text(p.get("category", "—"), 30)
        status = (p.get("status", "DRAFT") or "DRAFT").upper()

        # Badges estado
        if status == "PUBLISHED":
            status_label, status_cls = "Publicado", "ok"
            
        elif status == "PAUSED":
            status_label, status_cls = "PAUSED", "warn"
        else:
            status_label, status_cls = "Borrador", "stop"

        # Precio
        pt = p.get("price_type", "FIXED")
        pv = p.get("price_value")
        if pt == "AGREE":
            price_txt = "A convenir"
        elif pt == "FROM":
            price_txt = f"Desde ${int(pv or 0):,}".replace(",", ".")
        else:
            price_txt = f"${int(pv or 0):,}".replace(",", ".")

        # Thumb (usa primera foto si existe, si no placeholder)
        photo = (p.get("photo_urls") or [])
        thumb_txt = safe_text(p.get("category", ""), 18)

        st.markdown("<div class='mp-card'>", unsafe_allow_html=True)
        st.markdown("<div class='mp-body'>", unsafe_allow_html=True)

        top_left, top_right = st.columns([4, 1.3], vertical_alignment="center")
        with top_left:
            st.markdown(
                f"""
                <div class="mp-head">
                  <div>
                    <div class="mp-title">{name}</div>
                    <div class="mp-meta">{price_txt}</div>
                  </div>
                </div>
                <div class="mp-tags">
                  <span class="mp-pill">{category}</span>
                  <span class="mp-pill {status_cls}">{status_label}</span>
                </div>
                <div class="mp-desc">{desc_short if desc_short else "—"}</div>
                """,
                unsafe_allow_html=True
            )

        with top_right:
            if photo and (photo[0] or "").strip():
                st.image(photo[0].strip(), use_column_width=True)
            else:
                st.markdown(f"<div class='mp-thumb'>{thumb_txt}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)  # mp-body

        # Acciones
        st.markdown("<div class='mp-actions'>", unsafe_allow_html=True)

        if st.session_state.get("is_mobile", False):
            a, b = st.columns([1, 1])
            c = st.columns([1])[0]
        else:
            a, b, c = st.columns([1, 1, 1])

        with a:
            if st.button("✏️ Editar", key=f"mp_edit_{p['id']}", use_container_width=True):
                st.session_state["mp_edit_id"] = p["id"]
                st.session_state["mp_mode"] = "edit"
                st.rerun()

        with b:
            next_status = "PAUSED" if status == "PUBLISHED" else "PUBLISHED"
            label = "⏸️ Pausar" if next_status == "PAUSED" else "🚀 Publicar"

            if st.button(label, key=f"mp_toggle_{p['id']}", use_container_width=True):
                # ✅ si quiere publicar, validar cupo y aprobación SIN st.stop()
                if next_status == "PUBLISHED":
                    if not approved:
                        st.warning("Tu perfil aún no está aprobado. No puedes publicar.")
                    elif not can_publish_more(db, u_db, exclude_product_id=p["id"]):
                        limit = get_publish_limit(u_db)
                        used_now = count_published_products(db, u_db["id"], exclude_product_id=p["id"])
                        limit_txt = "Ilimitado" if limit == -1 else str(limit)
                        st.warning(f"No puedes publicar más. Límite: {used_now}/{limit_txt}.")
                    else:
                        p["status"] = "PUBLISHED"
                        p["updated_at"] = now_iso()
                        save_db(db)
                        st.rerun()
                else:
                    # ✅ pausar siempre permitido
                    p["status"] = "PAUSED"
                    p["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()



        with c:
            if st.button("🗑️ Eliminar", key=f"mp_del_{p['id']}", use_container_width=True):
                db["products"] = [x for x in db.get("products", []) if x.get("id") != p["id"]]
                save_db(db)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)  # mp-actions
        st.markdown("</div>", unsafe_allow_html=True)  # mp-card

    st.markdown("</div>", unsafe_allow_html=True)  # mp-grid
