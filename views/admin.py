from __future__ import annotations

import streamlit as st
import pandas as pd
import unicodedata
import json

from auth.guards import require_role
from db.repo_json import user_profile, save_db, now_iso
from services.featured import (
    get_featured_products,
    set_featured_products,
)




# -------------------------
# Helpers
# -------------------------
def _format_price(pr: dict) -> str:
    pt = (pr.get("price_type") or "FIXED").upper()
    pv = pr.get("price_value")
    if pt == "AGREE":
        return "A convenir"
    if pt == "FROM":
        return f"Desde ${int(pv or 0):,}".replace(",", ".")
    return f"${int(pv or 0):,}".replace(",", ".")


def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def _match_query(haystack: str, needle: str) -> bool:
    """Match tolerante: ignora tildes, mayúsculas, y soporta múltiples palabras (AND)."""
    h = _norm_text(haystack)
    n = _norm_text(needle)
    if not n:
        return True
    terms = [t for t in n.split() if t]
    return all(t in h for t in terms)


# ✅ Normaliza estados de usuario a un set fijo
USER_STATUS_OPTIONS = ["Todos", "ACTIVE", "PENDING", "BLOCKED"]

def _user_status_label(v: str) -> str:
    return {"ACTIVE": "Activo", "PENDING": "Pendiente", "BLOCKED": "Bloqueado", "Todos": "Todos"}.get(v, v)


def render(db):
    if not require_role(["ADMIN"]):
        return

    st.markdown("## Panel de administración")
    st.markdown(
        '<div class="muted">Aprobar/bloquear emprendedores, moderar productos, destacados y tags sugeridos.</div>',
        unsafe_allow_html=True
    )
    st.write("")

    if st.button("📊 Ver analíticas", use_container_width=True):
        st.session_state["route"] = "admin_stats"
        st.rerun()

    total_emps = sum(1 for u in db.get("users", []) if u.get("role") == "EMPRENDEDOR")
    approved_profiles = sum(1 for p in db.get("profiles", []) if p.get("is_approved"))
    published_products = sum(
        1 for p in db.get("products", []) if (p.get("status") or "").upper() == "PUBLISHED"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Emprendedores", total_emps)
    c2.metric("Perfiles aprobados", approved_profiles)
    c3.metric("Productos publicados", published_products)

    # =========================================================
    # 👤 Emprendedores (tabla + acciones)
    # =========================================================
    st.divider()
    st.markdown("### 👤 Emprendedores")

    emps = [x for x in db.get("users", []) if x.get("role") == "EMPRENDEDOR"]
    rows = []
    for u in emps:
        prof = user_profile(db, u.get("id"))
        rows.append({
            "user_id": u.get("id"),
            "Emprendimiento": (prof.get("business_name") if prof else "—"),
            "Email": u.get("email", "—"),
            "Estado usuario": (u.get("status") or "PENDING"),  # ✅ siempre ACTIVE/PENDING/BLOCKED
            "Perfil aprobado": bool(prof.get("is_approved")) if prof else False,
        })

    if not rows:
        st.info("No hay emprendedores registrados.")
        return

    df = pd.DataFrame(rows)

    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        q = st.text_input(
            "Buscar (nombre o email)",
            value="",
            placeholder="Ej: café / aurora / @gmail / villa..."
        )
    with f2:
        status_user = st.selectbox(
            "Estado usuario",
            USER_STATUS_OPTIONS,
            index=0,
            format_func=_user_status_label
        )
    with f3:
        approved_filter = st.selectbox("Perfil aprobado", ["Todos", "Aprobado", "Pendiente"], index=0)

    fdf = df.copy()

    if (q or "").strip():
        mask = fdf.apply(
            lambda r: _match_query(f"{r['Emprendimiento']} {r['Email']}", q),
            axis=1
        )
        fdf = fdf[mask]

    if status_user != "Todos":
        fdf = fdf[fdf["Estado usuario"] == status_user]

    if approved_filter != "Todos":
        want = True if approved_filter == "Aprobado" else False
        fdf = fdf[fdf["Perfil aprobado"] == want]

    st.caption(f"{len(fdf)} resultado(s)")

    # ✅ Siempre mostramos tabla/selector si hay resultados,
    # y NO cortamos el resto del panel si no hay selección.
    selected_user_id = None

    if fdf.empty:
        st.info("No hay resultados con esos filtros.")
    else:
        options = fdf["user_id"].tolist()

        labels_map = {
            uid: f"{row['Emprendimiento']} — {row['Email']}"
            for uid, row in zip(options, fdf.to_dict("records"))
        }

        st.session_state.setdefault("admin_selected_user_id", options[0] if options else None)

        if st.session_state.get("admin_selected_user_id") not in options:
            st.session_state["admin_selected_user_id"] = options[0]

        selected_user_id = st.selectbox(
            "Selecciona un emprendedor para gestionar",
            options=options,
            format_func=lambda uid: labels_map.get(uid, str(uid)),
            key="admin_selected_user_id",
        )

        show = fdf.drop(columns=["user_id"])
        st.dataframe(show, use_container_width=True, hide_index=True)

        st.write("")
        st.markdown("#### Acciones")

        u_sel = next((x for x in db.get("users", []) if x.get("id") == selected_user_id), None)
        prof_sel = user_profile(db, selected_user_id) if selected_user_id else None

        if not u_sel:
            st.warning("No se encontró el usuario seleccionado.")
        else:
            name = (prof_sel.get("business_name") if prof_sel else "—")
            approved = bool(prof_sel.get("is_approved")) if prof_sel else False
            st.markdown(
                f"**{name}**  \n"
                f"Email: `{u_sel.get('email','—')}`  \n"
                f"Estado: `{u_sel.get('status','—')}`  \n"
                f"Perfil aprobado: `{approved}`"
            )

            a, b, c, d = st.columns(4)
            with a:
                if st.button("✅ Aprobar", use_container_width=True):
                    if prof_sel:
                        prof_sel["is_approved"] = True
                        prof_sel["updated_at"] = now_iso()
                    u_sel["status"] = "ACTIVE"
                    u_sel["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()

            with b:
                if st.button("🕒 Pendiente", use_container_width=True):
                    if prof_sel:
                        prof_sel["is_approved"] = False
                        prof_sel["updated_at"] = now_iso()
                    u_sel["status"] = "PENDING"
                    u_sel["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()

            with c:
                if st.button("⛔ Bloquear", use_container_width=True):
                    u_sel["status"] = "BLOCKED"
                    u_sel["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()

            with d:
                if st.button("🔓 Desbloquear", use_container_width=True):
                    u_sel["status"] = "ACTIVE"
                    u_sel["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()



    # =========================
    # 🔒 Límite + 📊 Acceso stats
    # =========================

    # defaults para usuarios viejos
    if "max_published_products" not in u_sel:
        u_sel["max_published_products"] = 5
    if "can_view_stats" not in u_sel:
        u_sel["can_view_stats"] = False

    st.write("")
    st.markdown("#### 🔒 Límite de publicaciones")

    new_limit = st.number_input(
        "Máximo productos publicados (PUBLISHED). Usa -1 para ilimitado",
        min_value=-1,
        max_value=999,
        value=int(u_sel.get("max_published_products", 5)),
        step=1,
        key=f"admin_limit_{u_sel['id']}",
    )

    st.markdown("#### 📊 Acceso a estadísticas")
    new_stats_access = st.toggle(
        "Permitir ver estadísticas",
        value=bool(u_sel.get("can_view_stats", False)),
        key=f"admin_stats_access_{u_sel['id']}",
    )

    if st.button("💾 Guardar límite / acceso", use_container_width=True, key=f"admin_save_limits_{u_sel['id']}"):
        u_sel["max_published_products"] = int(new_limit)
        u_sel["can_view_stats"] = bool(new_stats_access)
        u_sel["updated_at"] = now_iso()
        save_db(db)
        st.success("Actualizado.")
        st.rerun()

    # =========================================================
    # ⭐ Destacados (Home) - SOLO PRODUCTOS (SIEMPRE visible)
    # =========================================================
    st.divider()
    st.markdown("### ⭐ Destacados (Home)")

    profiles = {p.get("id"): p for p in (db.get("profiles", []) or [])}
    products = db.get("products", []) or []

    published_products_list = [p for p in products if (p.get("status") or "").upper() == "PUBLISHED"]
    prod_opts = [p.get("id") for p in published_products_list if p.get("id")]
    products_by_id = {p.get("id"): p for p in published_products_list}

    def _prod_label(pid: str) -> str:
        pr = products_by_id.get(pid) or {}
        prof = profiles.get(pr.get("profile_id")) or {}
        return f"{pr.get('name','—')} — {prof.get('business_name','—')}"

    current_feat_prods = [x for x in get_featured_products(db) if x in prod_opts]

    with st.form("admin_featured_form", clear_on_submit=False):
        sel_prods = st.multiselect(
            "Productos destacados (solo PUBLISHED)",
            options=prod_opts,
            default=current_feat_prods,
            format_func=_prod_label,
        )
        submitted = st.form_submit_button("💾 Guardar destacados", use_container_width=True)

    if submitted:
        set_featured_products(db, sel_prods, max_n=12)
        save_db(db)
        st.success("Destacados actualizados.")
        st.rerun()

    st.caption(f"Productos destacados: {len(current_feat_prods)}")

    # =========================================================
    # 📦 Moderación de productos
    # =========================================================
    st.divider()
    st.markdown("### 📦 Productos (moderar)")

    users = {u.get("id"): u for u in (db.get("users", []) or [])}
    products = db.get("products", []) or []

    # ---- construir dataset ----
    rows = []
    for pr in products:
        prof = profiles.get(pr.get("profile_id"), {}) or {}
        owner = users.get(pr.get("owner_user_id"), {}) or {}
        rows.append({
            "product_id": pr.get("id"),
            "Producto": pr.get("name", "—"),
            "Estado": (pr.get("status") or "DRAFT").upper(),
            "Categoría": pr.get("category", "—") or "—",
            "Precio": _format_price(pr),
            "Emprendimiento": prof.get("business_name", "—") or "—",
            "Email": owner.get("email", "—") or "—",
            "Actualizado": pr.get("updated_at") or pr.get("created_at") or "—",
        })

    if not rows:
        st.info("No hay productos registrados.")
        return

    dfp = pd.DataFrame(rows)

    # ---- filtros ----
    all_cats = sorted([c for c in dfp["Categoría"].unique().tolist() if c and c != "—"])
    all_status = ["Todos", "PUBLISHED", "PAUSED", "DRAFT"]

    st.session_state.setdefault("admin_prod_status", "Todos")
    st.session_state.setdefault("admin_prod_cat", "Todas")
    st.session_state.setdefault("admin_prod_q", "")

    f1, f2, f3 = st.columns([1, 1, 2])
    with f1:
        status_f = st.selectbox(
            "Estado",
            all_status,
            format_func=lambda v: {"Todos":"Todos", "PUBLISHED":"Publicado", "PAUSED":"Pausado", "DRAFT":"Borrador"}[v],
            key="admin_prod_status",
        )
    with f2:
        cat_f = st.selectbox("Categoría", ["Todas"] + all_cats, key="admin_prod_cat")
    with f3:
        qprod = st.text_input(
            "Buscar (producto, descripción, emprendimiento, email)",
            key="admin_prod_q",
            placeholder="Ej: torta, café aurora, usuario@email..."
        )

    fdfp = dfp.copy()

    if status_f != "Todos":
        fdfp = fdfp[fdfp["Estado"] == status_f]

    if cat_f != "Todas":
        fdfp = fdfp[fdfp["Categoría"] == cat_f]

    if (qprod or "").strip():
        keep_ids = []
        by_id = {x.get("id"): x for x in products}
        for pid in fdfp["product_id"].tolist():
            pr = by_id.get(pid) or {}
            prof = profiles.get(pr.get("profile_id"), {}) or {}
            owner = users.get(pr.get("owner_user_id"), {}) or {}
            hay = " ".join([
                pr.get("name", ""),
                pr.get("description", ""),
                prof.get("business_name", ""),
                owner.get("email", ""),
            ])
            if _match_query(hay, qprod):
                keep_ids.append(pid)

        fdfp = fdfp[fdfp["product_id"].isin(keep_ids)]

    fdfp = fdfp.sort_values(by="Actualizado", ascending=False)

    st.caption(f"Mostrando {len(fdfp)} producto(s).")

    if fdfp.empty:
        st.info("No hay productos con esos filtros.")
    else:
        options = fdfp["product_id"].tolist()
        # ✅ Si quedó una selección pendiente (por ejemplo después de borrar),
        # la aplicamos ANTES de instanciar el selectbox.
        if "admin_next_selected_product_id" in st.session_state:
            st.session_state["admin_selected_product_id"] = st.session_state.pop("admin_next_selected_product_id")
        st.session_state.setdefault("admin_selected_product_id", options[0] if options else None)
        if st.session_state.get("admin_selected_product_id") not in options:
            st.session_state["admin_selected_product_id"] = options[0]

        def _prod_label2(pid: str) -> str:
            r = fdfp[fdfp["product_id"] == pid].iloc[0]
            return f"{r['Producto']} — {r['Emprendimiento']} — {r['Estado']}"

        selected_pid = st.selectbox(
            "Selecciona un producto",
            options=options,
            format_func=_prod_label2,
            key="admin_selected_product_id",
        )

        show_cols = ["Producto", "Estado", "Categoría", "Precio", "Emprendimiento", "Email", "Actualizado"]
        st.dataframe(fdfp[show_cols], use_container_width=True, hide_index=True)

        st.write("")
        st.markdown("#### Acciones del producto seleccionado")

        pr = next((x for x in products if x.get("id") == selected_pid), None)
        if not pr:
            st.warning("Producto no encontrado.")
        else:
            prof = profiles.get(pr.get("profile_id"), {}) or {}
            owner = users.get(pr.get("owner_user_id"), {}) or {}

            pname = pr.get("name", "—")
            bname = prof.get("business_name", "—")
            email = owner.get("email", "—")
            status = (pr.get("status") or "DRAFT").upper()
            cat = pr.get("category", "—")
            price = _format_price(pr)
            updated = pr.get("updated_at") or pr.get("created_at") or "—"

            if status == "PUBLISHED":
                st_state = "✅ Publicado"
            elif status == "PAUSED":
                st_state = "⏸️ Pausado"
            else:
                st_state = "📝 Borrador"

            st.markdown(
                f"**{pname}** · {st_state}  \n"
                f"Categoría: `{cat}` · Precio: **{price}**  \n"
                f"Emprendimiento: **{bname}** · Usuario: `{email}`  \n"
                f"Actualizado: `{updated}`"
            )

            a1, a2, a3, a4 = st.columns([1.2, 1.2, 1.2, 1.2])

            with a1:
                if st.button("👁️ Ver", key=f"admin_prod_view_{selected_pid}", use_container_width=True):
                    st.session_state["selected_product_id"] = selected_pid
                    st.session_state["route"] = "product_detail"
                    st.rerun()

            with a2:
                if status == "PUBLISHED":
                    lbl = "⏸️ Pausar"
                    next_status = "PAUSED"
                else:
                    lbl = "🚀 Publicar"
                    next_status = "PUBLISHED"

                if st.button(lbl, key=f"admin_prod_toggle_{selected_pid}", use_container_width=True):
                    pr["status"] = next_status
                    pr["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()

            with a3:
                if st.button("🧊 Borrador", key=f"admin_prod_draft_{selected_pid}", use_container_width=True):
                    pr["status"] = "DRAFT"
                    pr["updated_at"] = now_iso()
                    save_db(db)
                    st.rerun()

            with a4:
                confirm_key = f"admin_prod_del_confirm_{selected_pid}"
                st.session_state.setdefault(confirm_key, False)

                if not st.session_state[confirm_key]:
                    if st.button("🗑️ Eliminar", key=f"admin_prod_del_{selected_pid}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("¿Seguro que deseas eliminar este producto? Esta acción no se puede deshacer.")
                    cA, cB = st.columns(2, gap="small")
                    with cA:
                        if st.button("✅ Sí, eliminar", key=f"admin_prod_del_yes_{selected_pid}", use_container_width=True):
                            db["products"] = [x for x in db.get("products", []) if x.get("id") != selected_pid]
                            save_db(db)
                            st.session_state[confirm_key] = False
                            remaining = [x.get("id") for x in db.get("products", []) if x.get("id")]
                            st.session_state["admin_next_selected_product_id"] = remaining[0] if remaining else None
                            st.rerun()
                    with cB:
                        if st.button("↩️ Cancelar", key=f"admin_prod_del_no_{selected_pid}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()

    # ... dentro de render(db), para ADMIN:
    st.divider()
    st.markdown("### 🗄️ Backup de datos")

    st.download_button(
        "⬇️ Descargar base de datos (db.json)",
        data=json.dumps(db, ensure_ascii=False, indent=2),
        file_name="db_export.json",
        mime="application/json",
        use_container_width=True
    )

    # =========================================================
    # 🏷️ Sugerencias de tags (tabla + seleccionar + acciones)
    # =========================================================
    st.divider()
    st.markdown("### 🏷️ Sugerencias de tags (pendientes)")

    sug_rows = []
    for pr in products:
        sug = (pr.get("tag_suggestion") or "").strip()
        if sug:
            prof = profiles.get(pr.get("profile_id"), {}) or {}
            owner = users.get(pr.get("owner_user_id"), {}) or {}
            sug_rows.append({
                "product_id": pr.get("id"),
                "Sugerencia": sug,
                "Categoría": pr.get("category", "—"),
                "Producto": pr.get("name", "—"),
                "Emprendimiento": prof.get("business_name", "—"),
                "Email": owner.get("email", "—"),
                "Actualizado": pr.get("updated_at") or pr.get("created_at") or "—",
            })

    if not sug_rows:
        st.info("No hay sugerencias de tags por revisar.")
        return

    dfs = pd.DataFrame(sug_rows).sort_values(by="Actualizado", ascending=False)

    s1, s2 = st.columns([2, 1])
    with s1:
        qs = st.text_input(
            "Buscar sugerencia / producto / emprendimiento",
            key="admin_sug_q",
            placeholder="Ej: 24/7, sin gluten..."
        )
        qs = (qs or "").strip()
    with s2:
        cat_s = st.selectbox(
            "Categoría",
            ["Todas"] + sorted([c for c in dfs["Categoría"].unique().tolist() if c and c != "—"]),
            key="admin_sug_cat"
        )

    fds = dfs.copy()
    if cat_s != "Todas":
        fds = fds[fds["Categoría"] == cat_s]
    if qs:
        mask = []
        for _, r in fds.iterrows():
            hay = " ".join([str(r["Sugerencia"]), str(r["Producto"]), str(r["Emprendimiento"]), str(r["Email"])])
            mask.append(_match_query(hay, qs))
        fds = fds[mask]

    st.caption(f"{len(fds)} sugerencia(s).")

    if fds.empty:
        st.info("No hay sugerencias con esos filtros.")
        return

    options = fds["product_id"].tolist()
    st.session_state.setdefault("admin_selected_sug_pid", options[0] if options else None)
    if st.session_state.get("admin_selected_sug_pid") not in options:
        st.session_state["admin_selected_sug_pid"] = options[0]

    selected_sug_pid = st.selectbox(
        "Selecciona una sugerencia",
        options=options,
        format_func=lambda pid: f"{fds[fds['product_id']==pid].iloc[0]['Sugerencia']} — {fds[fds['product_id']==pid].iloc[0]['Producto']}",
        key="admin_selected_sug_pid",
    )

    st.dataframe(
        fds[["Sugerencia", "Categoría", "Producto", "Emprendimiento", "Email", "Actualizado"]],
        use_container_width=True,
        hide_index=True
    )

    st.write("")
    b1, b2 = st.columns([1, 1])

    with b1:
        if st.button("👁️ Ver producto", key=f"admin_sug_view_{selected_sug_pid}", use_container_width=True):
            st.session_state["selected_product_id"] = selected_sug_pid
            st.session_state["route"] = "product_detail"
            st.rerun()

    with b2:
        if st.button("✅ Marcar revisada (limpiar)", key=f"admin_sug_clear_{selected_sug_pid}", use_container_width=True):
            prod = next((x for x in products if x.get("id") == selected_sug_pid), None)
            if prod:
                prod["tag_suggestion"] = ""
                prod["updated_at"] = now_iso()
                save_db(db)
            st.rerun()



    

