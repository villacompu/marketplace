from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from auth.guards import require_role
from db.repo_json import load_analytics


# =========================================================
# Compatibilidad de nombres antiguos de eventos
# =========================================================
EVENT_ALIASES = {
    "product_view": "view_product",
    "profile_view": "view_profile",
    "home_view": "view_home",
    "directory_view": "view_directory",
}


# =========================================================
# Etiquetas amigables
# =========================================================
def _label_channel(v: str) -> str:
    m = {
        "Direct": "Acceso directo",
        "Organic Search": "Búsqueda orgánica",
        "Organic Social": "Redes sociales",
        "Referral": "Referencia",
        "Campaign": "Campaña",
        "Unknown": "No identificado",
        "unknown": "No identificado",
        "": "No identificado",
    }
    v = str(v or "").strip()
    return m.get(v, v if v else "No identificado")


def _label_device(v: str) -> str:
    m = {
        "Desktop": "Computador",
        "Mobile": "Móvil",
        "Tablet": "Tablet",
        "Unknown": "No identificado",
        "unknown": "No identificado",
        "": "No identificado",
    }
    v = str(v or "").strip()
    return m.get(v, v if v else "No identificado")


def _label_entry_source(v: str) -> str:
    m = {
        "home": "Inicio",
        "home_top": "Inicio",
        "home_search": "Búsqueda en inicio",
        "home_filters": "Filtros del inicio",
        "home_featured": "Destacados del inicio",
        "home_results": "Resultados del inicio",
        "home_featured_profile": "Perfil desde destacados",
        "home_directory_button": "Botón directorio desde inicio",
        "home_feed_button": "Botón explorar productos desde inicio",

        "feed": "Feed",
        "feed_card": "Tarjeta del feed",
        "feed_product": "Producto del feed",
        "feed_profile": "Perfil desde feed",
        "feed_contact": "Contacto desde feed",

        "directory": "Directorio",
        "directory_search": "Búsqueda en directorio",
        "directory_filters": "Filtros del directorio",
        "directory_product_card": "Producto desde directorio",
        "directory_profile_card": "Perfil abierto desde directorio",
        "directory_contact": "Contacto desde directorio",

        "product_detail": "Detalle del producto",
        "product_detail_profile_button": "Perfil abierto desde producto",
        "product_detail_contact": "Contacto desde detalle del producto",
        "product_card": "Tarjeta de producto",
        "featured_product": "Producto destacado",

        "public_profile": "Perfil público",
        "public_profile_contact": "Contacto desde perfil público",
        "profile_card": "Tarjeta de emprendimiento",

        "my_profile": "Mi perfil",
        "my_products": "Mis productos",

        "search": "Búsqueda",
        "favorites": "Favoritos",

        # histórico
        "Unknown": "Histórico sin trazabilidad",
        "unknown": "Histórico sin trazabilidad",
        "direct": "Acceso directo",
        "": "Histórico sin trazabilidad",
    }

    v = str(v or "").strip()
    return m.get(v, v.replace("_", " ").capitalize() if v else "Histórico sin trazabilidad")


def _label_page_context(v: str) -> str:
    m = {
        "home": "Inicio",
        "directory": "Directorio",
        "product_detail": "Detalle del producto",
        "public_profile": "Perfil público",
        "my_profile": "Mi perfil",
        "my_products": "Mis productos",
        "favorites": "Favoritos",
        "search": "Búsqueda",
        "feed": "Feed",

        # histórico
        "Unknown": "Histórico sin trazabilidad",
        "unknown": "Histórico sin trazabilidad",
        "": "Histórico sin trazabilidad",
    }
    v = str(v or "").strip()
    return m.get(v, v.replace("_", " ").capitalize() if v else "Histórico sin trazabilidad")


def _label_event_type(v: str) -> str:
    m = {
        "view_home": "Vista de inicio",
        "view_directory": "Vista de directorio",
        "view_product": "Vista de producto",
        "view_profile": "Vista de perfil",
        "search": "Búsqueda",

        "click_whatsapp": "Clic en WhatsApp",
        "click_instagram": "Clic en Instagram",
        "click_call": "Clic en llamada",
        "click_website": "Clic en página web",
        "click_catalog": "Clic en catálogo",

        # feed
        "view_feed": "Vista del feed",
        "view_feed_product": "Vista de producto en feed",
        "feed_next": "Siguiente en feed",
        "feed_prev": "Anterior en feed",
        "feed_shuffle": "Aleatorio en feed",
        "feed_open_product": "Abrir producto desde feed",
        "feed_open_profile": "Abrir emprendimiento desde feed",
    }

    v = str(v or "").strip()
    return m.get(v, v.replace("_", " ").capitalize() if v else "Evento")


# =========================================================
# Helpers base
# =========================================================
def _event_type(df: pd.DataFrame) -> pd.Series:
    if "type" in df.columns:
        s = df["type"].astype(str)
    elif "event" in df.columns:
        s = df["event"].astype(str)
    else:
        s = pd.Series([""] * len(df), index=df.index)
    return s.replace(EVENT_ALIASES)


def _get_meta_field(df: pd.DataFrame, key: str) -> pd.Series:
    if "meta" not in df.columns:
        return pd.Series([""] * len(df), index=df.index)

    def pick(x):
        try:
            if isinstance(x, dict):
                return x.get(key, "") or ""
            return ""
        except Exception:
            return ""

    return df["meta"].apply(pick).astype(str)


def _visitor_id(row: pd.Series) -> str:
    u = str(row.get("user_id") or "").strip()
    a = str(row.get("anon_id") or "").strip()
    return u if u else a


def _prepare_pie(df: pd.DataFrame, col: str, label_empty: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({col: [label_empty], "count": [1]})

    s = df[col].fillna("").astype(str).replace({"": label_empty})
    out = (
        s.groupby(s)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    out.columns = [col, "count"]
    return out


def _render_pie(df: pd.DataFrame, names: str, values: str, height: int = 340, key: str = ""):
    fig = px.pie(df, names=names, values=values, hole=0.65)
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch", key=key)


def _render_line(df: pd.DataFrame, x: str, y: str, height: int = 320, key: str = ""):
    fig = px.line(df, x=x, y=y)
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        xaxis_title="",
        yaxis_title="",
    )
    st.plotly_chart(fig, width="stretch", key=key)


def _render_bar(df: pd.DataFrame, x: str, y: str, height: int = 320, key: str = ""):
    fig = px.bar(df, x=x, y=y)
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        xaxis_title="",
        yaxis_title="",
    )
    st.plotly_chart(fig, width="stretch", key=key)


# =========================================================
# Main
# =========================================================
def render(db):
    if not require_role(["ADMIN"]):
        return

    st.markdown("## 📊 Estadísticas del sitio")
    st.markdown(
        '<div class="muted">Resumen general de tráfico, interacción y rendimiento del marketplace.</div>',
        unsafe_allow_html=True
    )
    st.write("")

    analytics = load_analytics()
    events = analytics.get("events", []) or []

    if not events:
        st.info("Aún no hay eventos registrados. Navega el sitio para generar estadísticas.")
        return

    df = pd.DataFrame(events)

    for c in ["product_id", "profile_id", "ts", "meta", "user_id", "anon_id"]:
        if c not in df.columns:
            df[c] = ""

    df["etype"] = _event_type(df)
    df["visitor"] = df.apply(_visitor_id, axis=1)

    df["channel"] = _get_meta_field(df, "channel").replace({"": "Direct"})
    df["device"] = _get_meta_field(df, "device").replace({"": "Desktop"})
    df["entry_source"] = _get_meta_field(df, "entry_source").replace({"": "Unknown"})
    df["page_context"] = _get_meta_field(df, "page_context").replace({"": "Unknown"})

    df["channel_label"] = df["channel"].apply(_label_channel)
    df["device_label"] = df["device"].apply(_label_device)
    df["entry_source_label"] = df["entry_source"].apply(_label_entry_source)
    df["page_context_label"] = df["page_context"].apply(_label_page_context)
    df["etype_label"] = df["etype"].apply(_label_event_type)

    df["ts_dt"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    df_valid_ts = df.dropna(subset=["ts_dt"]).copy()

    products = db.get("products", []) or []
    profiles = db.get("profiles", []) or []

    prod_map = {str(p.get("id")): p for p in products}
    prof_map = {str(p.get("id")): p for p in profiles}

    # =========================================================
    # KPIs generales
    # =========================================================
    total_events = int(len(df))
    unique_visitors = int(df["visitor"].replace("", pd.NA).dropna().nunique())

    home_views = int((df["etype"] == "view_home").sum())
    directory_views = int((df["etype"] == "view_directory").sum())
    prod_views = int((df["etype"] == "view_product").sum())
    prof_views = int((df["etype"] == "view_profile").sum())
    searches = int((df["etype"] == "search").sum())

    click_whatsapp = int((df["etype"] == "click_whatsapp").sum())
    click_instagram = int((df["etype"] == "click_instagram").sum())
    click_website = int((df["etype"] == "click_website").sum())
    click_catalog = int((df["etype"] == "click_catalog").sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Eventos", total_events)
    k2.metric("Visitantes únicos", unique_visitors)
    k3.metric("Búsquedas", searches)
    k4.metric("Clics de contacto", click_whatsapp + click_instagram + click_website + click_catalog)

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Vistas Inicio", home_views)
    k6.metric("Vistas Directorio", directory_views)
    k7.metric("Vistas Producto", prod_views)
    k8.metric("Vistas Perfil", prof_views)

    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WhatsApp", click_whatsapp)
    c2.metric("Instagram", click_instagram)
    c3.metric("Web", click_website)
    c4.metric("Catálogo", click_catalog)

    st.divider()

    # =========================================================
    # Tabs grandes
    # =========================================================
    t_overview, t_products, t_profiles, t_sources, t_contacts = st.tabs([
        "📈 Visión general",
        "📦 Productos",
        "🏪 Emprendimientos",
        "🧭 Tráfico",
        "📲 Contactos",
    ])

    # =========================================================
    # TAB 1: Visión general
    # =========================================================
    with t_overview:
        st.markdown("### 📈 Tendencia general")

        if df_valid_ts.empty:
            st.info("No hay fechas válidas para mostrar tendencias.")
        else:
            df_valid_ts["day"] = df_valid_ts["ts_dt"].dt.date.astype(str)

            daily_events = (
                df_valid_ts.groupby("day")
                .size()
                .reset_index(name="eventos")
            )

            daily_visitors = (
                df_valid_ts.groupby("day")["visitor"]
                .nunique()
                .reset_index(name="visitantes_unicos")
            )

            left, right = st.columns(2, gap="large")

            with left:
                st.markdown("#### Eventos por día")
                _render_line(daily_events, x="day", y="eventos", height=320, key="admin_daily_events")

            with right:
                st.markdown("#### Visitantes únicos por día")
                _render_line(daily_visitors, x="day", y="visitantes_unicos", height=320, key="admin_daily_visitors")

        st.write("")
        st.markdown("### Distribución por tipo de evento")

        by_type = (
            df.groupby("etype_label")
            .size()
            .reset_index(name="cantidad")
            .sort_values("cantidad", ascending=False)
        )

        if by_type.empty:
            st.info("No hay eventos para mostrar.")
        else:
            _render_bar(by_type, x="etype_label", y="cantidad", height=320, key="admin_events_by_type")

    # =========================================================
    # TAB 2: Productos
    # =========================================================
    with t_products:
        st.markdown("### 🔥 Top productos por vistas")

        pv = df[df["etype"] == "view_product"]
        if pv.empty:
            st.info("No hay vistas de productos aún.")
        else:
            top = (
                pv.groupby(pv["product_id"].astype(str))
                .size()
                .reset_index(name="vistas")
                .sort_values("vistas", ascending=False)
                .head(20)
            )

            rows = []
            for _, r in top.iterrows():
                pid = str(r["product_id"] or "")
                pr = prod_map.get(pid) or {}
                prof = prof_map.get(str(pr.get("profile_id") or "")) or {}

                rows.append({
                    "Producto": pr.get("name", "—"),
                    "Emprendimiento": prof.get("business_name", "—"),
                    "Categoría": pr.get("category", "—"),
                    "Vistas": int(r["vistas"]),
                })

            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        st.write("")
        st.markdown("### 📲 Top productos por clics de contacto")

        prod_contact = df[
            (df["etype"].isin(["click_whatsapp", "click_instagram", "click_website", "click_catalog"]))
            & (df["product_id"].astype(str).ne(""))
        ]

        if prod_contact.empty:
            st.info("No hay clics de contacto asociados a productos.")
        else:
            top_contact = (
                prod_contact.groupby(prod_contact["product_id"].astype(str))
                .size()
                .reset_index(name="interacciones")
                .sort_values("interacciones", ascending=False)
                .head(20)
            )

            rows_contact = []
            for _, r in top_contact.iterrows():
                pid = str(r["product_id"] or "")
                pr = prod_map.get(pid) or {}
                prof = prof_map.get(str(pr.get("profile_id") or "")) or {}

                rows_contact.append({
                    "Producto": pr.get("name", "—"),
                    "Emprendimiento": prof.get("business_name", "—"),
                    "Interacciones": int(r["interacciones"]),
                })

            st.dataframe(pd.DataFrame(rows_contact), width="stretch", hide_index=True)

    # =========================================================
    # TAB 3: Emprendimientos
    # =========================================================
    with t_profiles:
        st.markdown("### ⭐ Top emprendimientos por vistas de perfil")

        fv = df[df["etype"] == "view_profile"]
        if fv.empty:
            st.info("No hay vistas de perfiles aún.")
        else:
            top2 = (
                fv.groupby(fv["profile_id"].astype(str))
                .size()
                .reset_index(name="vistas")
                .sort_values("vistas", ascending=False)
                .head(20)
            )

            rows2 = []
            for _, r in top2.iterrows():
                pid = str(r["profile_id"] or "")
                pr = prof_map.get(pid) or {}

                rows2.append({
                    "Emprendimiento": pr.get("business_name", "—"),
                    "Ciudad": pr.get("city", "—"),
                    "Vistas": int(r["vistas"]),
                })

            st.dataframe(pd.DataFrame(rows2), width="stretch", hide_index=True)

        st.write("")
        st.markdown("### 🧲 Top emprendimientos por interacción total")

        profile_related = df[
            (df["profile_id"].astype(str).ne(""))
            & df["etype"].isin([
                "view_profile",
                "view_product",
                "click_whatsapp",
                "click_instagram",
                "click_website",
                "click_catalog",
            ])
        ]

        if profile_related.empty:
            st.info("No hay interacciones suficientes para emprendimientos.")
        else:
            top_profiles = (
                profile_related.groupby(profile_related["profile_id"].astype(str))
                .size()
                .reset_index(name="interacciones")
                .sort_values("interacciones", ascending=False)
                .head(20)
            )

            rows3 = []
            for _, r in top_profiles.iterrows():
                pid = str(r["profile_id"] or "")
                pr = prof_map.get(pid) or {}

                rows3.append({
                    "Emprendimiento": pr.get("business_name", "—"),
                    "Ciudad": pr.get("city", "—"),
                    "Interacciones": int(r["interacciones"]),
                })

            st.dataframe(pd.DataFrame(rows3), width="stretch", hide_index=True)

    # =========================================================
    # TAB 4: Tráfico
    # =========================================================
    with t_sources:
        st.markdown("### 🧭 Tráfico y adquisición")

        # Solo eventos con alguna trazabilidad real
        df_traceable = df[
            (df["entry_source_label"] != "Histórico sin trazabilidad") |
            (df["page_context_label"] != "Histórico sin trazabilidad")
        ].copy()

        traceable_events = int(len(df_traceable))
        traceable_pct = round((traceable_events / max(1, len(df))) * 100, 1)

        a1, a2 = st.columns(2)
        a1.metric("Eventos con origen identificable", traceable_events)
        a2.metric("Cobertura de trazabilidad", f"{traceable_pct}%")

        st.write("")

        if df_traceable.empty:
            st.info("Aún no hay eventos con fuente o contexto identificable. Los eventos antiguos quedaron sin trazabilidad.")
        else:
            left, right = st.columns(2, gap="large")

            with left:
                st.markdown("#### Fuentes de entrada")
                src = (
                    df_traceable.groupby("entry_source_label")
                    .size()
                    .reset_index(name="visitas")
                    .sort_values("visitas", ascending=False)
                    .head(15)
                )
                _render_bar(src, x="entry_source_label", y="visitas", height=320, key="admin_source_bar")

            with right:
                st.markdown("#### Contextos de página")
                ctx = (
                    df_traceable.groupby("page_context_label")
                    .size()
                    .reset_index(name="visitas")
                    .sort_values("visitas", ascending=False)
                    .head(15)
                )
                _render_bar(ctx, x="page_context_label", y="visitas", height=320, key="admin_context_bar")

            st.write("")
            st.markdown("### Detalle de fuentes")

            source_detail = (
                df_traceable.groupby("entry_source_label")
                .agg(
                    visitas=("entry_source_label", "size"),
                    visitantes_unicos=("visitor", "nunique"),
                )
                .reset_index()
                .sort_values("visitas", ascending=False)
                .rename(columns={"entry_source_label": "Fuente"})
            )

            st.dataframe(source_detail, width="stretch", hide_index=True)

            st.write("")
            st.markdown("### Detalle de contextos")

            context_detail = (
                df_traceable.groupby("page_context_label")
                .agg(
                    visitas=("page_context_label", "size"),
                    visitantes_unicos=("visitor", "nunique"),
                )
                .reset_index()
                .sort_values("visitas", ascending=False)
                .rename(columns={"page_context_label": "Contexto"})
            )

            st.dataframe(context_detail, width="stretch", hide_index=True)

    # =========================================================
    # TAB 5: Contactos
    # =========================================================
    with t_contacts:
        st.markdown("### 📲 Interacciones de contacto")

        contact_df = df[df["etype"].isin([
            "click_whatsapp",
            "click_instagram",
            "click_website",
            "click_catalog",
        ])].copy()

        if contact_df.empty:
            st.info("Aún no hay clics de contacto registrados.")
        else:
            by_contact = (
                contact_df.groupby("etype_label")
                .size()
                .reset_index(name="cantidad")
                .sort_values("cantidad", ascending=False)
            )

            left, right = st.columns(2, gap="large")

            with left:
                st.markdown("#### Distribución por tipo de contacto")
                _render_bar(by_contact, x="etype_label", y="cantidad", height=320, key="admin_contact_type_bar")

            with right:
                st.markdown("#### Fuente de esos contactos")
                by_source_contact = (
                    contact_df.groupby("entry_source_label")
                    .size()
                    .reset_index(name="cantidad")
                    .sort_values("cantidad", ascending=False)
                    .head(12)
                )
                _render_bar(
                    by_source_contact,
                    x="entry_source_label",
                    y="cantidad",
                    height=320,
                    key="admin_contact_source_bar",
                )

            st.write("")
            st.markdown("### Detalle de clics de contacto")

            detail_contact = (
                contact_df.groupby(["etype_label", "entry_source_label"])
                .size()
                .reset_index(name="cantidad")
                .sort_values("cantidad", ascending=False)
                .rename(columns={
                    "etype_label": "Tipo de contacto",
                    "entry_source_label": "Fuente",
                })
            )

            st.dataframe(detail_contact, width="stretch", hide_index=True)