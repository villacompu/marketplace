from __future__ import annotations
import streamlit as st
import pandas as pd

from auth.guards import require_role




# Compat: si en algún momento guardaste "product_view"/"profile_view",
# lo mapeamos a los nuevos nombres.
EVENT_ALIASES = {
    "product_view": "view_product",
    "profile_view": "view_profile",
    "home_view": "view_home",
}


def _event_type(df: pd.DataFrame) -> pd.Series:
    """
    Retorna la columna de tipo de evento de forma robusta:
    - preferimos 'type'
    - si no existe, usamos 'event'
    - además normalizamos alias viejos
    """
    if "type" in df.columns:
        s = df["type"].astype(str)
    elif "event" in df.columns:
        s = df["event"].astype(str)
    else:
        s = pd.Series([""] * len(df))

    return s.replace(EVENT_ALIASES)


def render(db):
    if not require_role(["ADMIN"]):
        return

    st.markdown("## 📊 Estadísticas del sitio (MVP)")
    st.markdown('<div class="muted">Vistas y búsquedas básicas (sin datos sensibles).</div>', unsafe_allow_html=True)
    st.write("")

    events = db.get("events", []) or []
    if not events:
        st.info("Aún no hay eventos registrados. Navega home/productos/perfiles para generar estadísticas.")
        return

    df = pd.DataFrame(events)

    # Normalizar columnas por si hay eventos viejos
    for c in ["product_id", "profile_id", "ts"]:
        if c not in df.columns:
            df[c] = ""

    et = _event_type(df)

    total_events = int(len(df))
    home_views = int((et == "view_home").sum())
    prod_views = int((et == "view_product").sum())
    prof_views = int((et == "view_profile").sum())
    searches = int((et == "search").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eventos", total_events)
    c2.metric("Vistas Home", home_views)
    c3.metric("Vistas Producto", prod_views)
    c4.metric("Vistas Perfil", prof_views)

    st.caption(f"Búsquedas registradas: {searches}")
    st.divider()

    products = db.get("products", []) or []
    profiles = db.get("profiles", []) or []
    prod_map = {p.get("id"): p for p in products}
    prof_map = {p.get("id"): p for p in profiles}

    # ==========================
    # Top productos por vistas
    # ==========================
    st.markdown("### 🔥 Top productos por vistas")
    pv = df[et == "view_product"]
    if pv.empty:
        st.info("No hay vistas de productos aún.")
    else:
        top = pv.groupby("product_id").size().reset_index(name="vistas")
        top = top.sort_values("vistas", ascending=False).head(20)

        rows = []
        for _, r in top.iterrows():
            pid = str(r["product_id"] or "")
            pr = prod_map.get(pid) or {}
            prof = prof_map.get(pr.get("profile_id")) or {}
            rows.append({
                "Producto": pr.get("name", "—"),
                "Emprendimiento": prof.get("business_name", "—"),
                "Categoría": pr.get("category", "—"),
                "Vistas": int(r["vistas"]),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.write("")

    # ==========================
    # Top perfiles por vistas
    # ==========================
    st.markdown("### ⭐ Top emprendimientos por vistas de perfil")
    fv = df[et == "view_profile"]
    if fv.empty:
        st.info("No hay vistas de perfiles aún.")
    else:
        top2 = fv.groupby("profile_id").size().reset_index(name="vistas")
        top2 = top2.sort_values("vistas", ascending=False).head(20)

        rows2 = []
        for _, r in top2.iterrows():
            pid = str(r["profile_id"] or "")
            pr = prof_map.get(pid) or {}
            rows2.append({
                "Emprendimiento": pr.get("business_name", "—"),
                "Ciudad": pr.get("city", "—"),
                "Vistas": int(r["vistas"]),
            })

        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)

    st.write("")
    with st.expander("Ver eventos (raw)"):
        # orden si existe ts, si no, deja tal cual
        if "ts" in df.columns:
            st.dataframe(df.sort_values("ts", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
