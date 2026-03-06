from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from auth.session import get_user
from auth.guards import require_role


# =========================================================
# Compatibilidad de nombres antiguos de eventos
# =========================================================
EVENT_ALIASES = {
    "product_view": "view_product",
    "profile_view": "view_profile",
    "home_view": "view_home",
}


# =========================================================
# Helpers base
# =========================================================
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
        s = pd.Series([""] * len(df), index=df.index)

    return s.replace(EVENT_ALIASES)


def _get_meta_field(df: pd.DataFrame, key: str) -> pd.Series:
    """
    Extrae df['meta'][key] de forma segura.
    Si no existe meta o viene mal formado, retorna vacío.
    """
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
    """
    Identificador de visitante:
    - si hay user_id, úsalo
    - si no, usa anon_id
    """
    u = str(row.get("user_id") or "").strip()
    a = str(row.get("anon_id") or "").strip()
    return u if u else a


def _safe_div(num: float, den: float) -> float:
    if not den:
        return 0.0
    return float(num) / float(den)


def _pct_change(cur: float, prev: float) -> float:
    base_prev = max(1.0, float(prev))
    return ((float(cur) - float(prev)) / base_prev) * 100.0


def _metric_delta_text(cur: float, prev: float, suffix: str = "vs 28 días previos") -> str:
    pct = _pct_change(cur, prev)
    return f"{pct:.1f}% {suffix}"


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


def _render_pie(df: pd.DataFrame, names: str, values: str, height: int = 360, key: str = ""):
    fig = px.pie(df, names=names, values=values, hole=0.65)
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch", key=key)


def _render_line(df: pd.DataFrame, x: str, y: str, height: int = 340, key: str = ""):
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
def render(db: dict):
    u = get_user()
    if not u:
        st.warning("Debes iniciar sesión.")
        return

    if not require_role(["EMPRENDEDOR", "ADMIN"]):
        return

    u_db = next((x for x in (db.get("users", []) or []) if x.get("id") == u.get("id")), None) or u

    st.markdown("## 📊 Mis estadísticas")
    st.markdown(
        '<div class="muted">Resumen de exposición de tu emprendimiento (sin datos sensibles).</div>',
        unsafe_allow_html=True
    )
    st.write("")

    events = db.get("events", []) or []
    if not events:
        st.info("Aún no hay eventos registrados. Navega productos/perfil para generar estadísticas.")
        return

    df = pd.DataFrame(events)

    # Normalizar columnas por si hay eventos viejos
    for c in ["product_id", "profile_id", "ts", "meta", "user_id", "anon_id"]:
        if c not in df.columns:
            df[c] = ""

    et = _event_type(df)

    # -----------------------------------------
    # Perfil y productos del emprendedor
    # -----------------------------------------
    prof = next(
        (
            p for p in (db.get("profiles", []) or [])
            if (p.get("owner_user_id") == u_db.get("id")) or (p.get("user_id") == u_db.get("id"))
        ),
        None
    ) or {}

    my_profile_id = str(prof.get("id") or "")
    my_products = [p for p in (db.get("products", []) or []) if str(p.get("owner_user_id") or "") == str(u_db.get("id") or "")]
    my_product_ids = {str(p.get("id") or "") for p in my_products}
    prod_map = {str(p.get("id") or ""): p for p in (db.get("products", []) or [])}

    # =========================================================
    # RESUMEN BÁSICO
    # =========================================================
    my_prod_views = df[(et == "view_product") & (df["product_id"].astype(str).isin(list(my_product_ids)))]
    my_prof_views = (
        df[(et == "view_profile") & (df["profile_id"].astype(str) == my_profile_id)]
        if my_profile_id else df.iloc[0:0]
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("Vistas a mis productos", int(len(my_prod_views)))
    k2.metric("Vistas a mi perfil", int(len(my_prof_views)))
    k3.metric(
        "Productos publicados",
        int(sum(1 for p in my_products if (p.get("status") or "").upper() == "PUBLISHED"))
    )

    st.divider()

    st.markdown("### 🔥 Top productos por vistas")
    if my_prod_views.empty:
        st.info("Aún no hay vistas de tus productos.")
    else:
        top = (
            my_prod_views.groupby(my_prod_views["product_id"].astype(str))
            .size()
            .reset_index(name="vistas")
            .sort_values("vistas", ascending=False)
            .head(10)
        )

        rows = []
        for _, r in top.iterrows():
            pid = str(r.iloc[0] or "")
            pr = prod_map.get(pid) or {}
            rows.append({
                "Producto": pr.get("name", "—"),
                "Categoría": pr.get("category", "—"),
                "Estado": (pr.get("status") or "—"),
                "Vistas": int(r["vistas"]),
            })

        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # =========================================================
    # ANALÍTICA AVANZADA
    # =========================================================
    has_advanced = bool(u_db.get("can_view_stats") is True)

    st.write("")
    st.markdown("### 📈 Analítica avanzada")

    if not has_advanced:
        st.info(
            "Tu cuenta tiene acceso al resumen básico. Para ver analítica avanzada, solicita al administrador "
            "el permiso **Acceso a estadísticas**."
        )
        return

    # -----------------------------------------
    # Base con timestamps válidos
    # -----------------------------------------
    df2 = df.copy()
    df2["ts_dt"] = pd.to_datetime(df2["ts"], errors="coerce", utc=True)
    df2 = df2.dropna(subset=["ts_dt"])

    if df2.empty:
        st.info("No hay timestamps válidos para graficar.")
        return

    et2 = _event_type(df2)

    # Solo eventos del emprendedor
    df_me_all = df2[
        ((et2 == "view_product") & (df2["product_id"].astype(str).isin(list(my_product_ids))))
        | ((et2 == "view_profile") & (df2["profile_id"].astype(str) == my_profile_id))
    ].copy()

    if df_me_all.empty:
        st.info("Aún no hay eventos tuyos para analítica avanzada.")
        return

    # -----------------------------------------
    # Meta fields (con fallback)
    # -----------------------------------------
    df_me_all["channel"] = _get_meta_field(df_me_all, "channel").replace({"": "Direct"})
    df_me_all["device"] = _get_meta_field(df_me_all, "device").replace({"": "Desktop"})
    df_me_all["location"] = (
        _get_meta_field(df_me_all, "country")
        .replace({"": ""})
    )

    # fallback más útil para ubicación
    loc_city = _get_meta_field(df_me_all, "city_hint")
    loc_country = _get_meta_field(df_me_all, "country_hint")
    loc_generic = _get_meta_field(df_me_all, "location_hint")

    df_me_all["location"] = df_me_all["location"].where(df_me_all["location"] != "", loc_country)
    df_me_all["location"] = df_me_all["location"].where(df_me_all["location"] != "", loc_city)
    df_me_all["location"] = df_me_all["location"].where(df_me_all["location"] != "", loc_generic)
    df_me_all["location"] = df_me_all["location"].replace({"": "Unknown"})

    df_me_all["entry_source"] = _get_meta_field(df_me_all, "entry_source").replace({"": "Unknown"})
    df_me_all["page_context"] = _get_meta_field(df_me_all, "page_context").replace({"": "Unknown"})
    df_me_all["visitor"] = df_me_all.apply(_visitor_id, axis=1)

    # -----------------------------------------
    # Ventanas de tiempo
    # -----------------------------------------
    end = df_me_all["ts_dt"].max()
    cur_start = end - pd.Timedelta(days=28)
    prev_start = cur_start - pd.Timedelta(days=28)

    df_cur = df_me_all[(df_me_all["ts_dt"] >= cur_start) & (df_me_all["ts_dt"] <= end)].copy()
    df_prev = df_me_all[(df_me_all["ts_dt"] >= prev_start) & (df_me_all["ts_dt"] < cur_start)].copy()

    # Normalizaciones
    for part in [df_cur, df_prev]:
        if not part.empty:
            part["day"] = part["ts_dt"].dt.date.astype(str)
            part["etype"] = _event_type(part)

    # =========================================================
    # TABS GRANDES
    # =========================================================
    t_unique, t_visits, t_sources = st.tabs(["👥 Visitantes únicos", "🔁 Visitas / eventos", "🧭 Origen del tráfico"])

    # =========================================================
    # TAB 1: VISITANTES ÚNICOS
    # =========================================================
    with t_unique:
        st.markdown("#### Audiencia única de los últimos 28 días")

        # ---- métricas únicas
        vis_cur = int(df_cur["visitor"].nunique()) if not df_cur.empty else 0
        vis_prev = int(df_prev["visitor"].nunique()) if not df_prev.empty else 0

        unique_prod_visitors = (
            int(df_cur[df_cur["etype"] == "view_product"]["visitor"].nunique())
            if not df_cur.empty else 0
        )
        unique_prof_visitors = (
            int(df_cur[df_cur["etype"] == "view_profile"]["visitor"].nunique())
            if not df_cur.empty else 0
        )

        # recurrentes = visitantes con más de 1 evento en la ventana
        if not df_cur.empty:
            visitor_counts_cur = df_cur.groupby("visitor").size().reset_index(name="events")
            returning_cur = int((visitor_counts_cur["events"] > 1).sum())
            new_cur = int((visitor_counts_cur["events"] == 1).sum())
        else:
            returning_cur = 0
            new_cur = 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Visitantes únicos", vis_cur, _metric_delta_text(vis_cur, vis_prev))
        m2.metric("Vieron productos", unique_prod_visitors)
        m3.metric("Vieron perfil", unique_prof_visitors)
        m4.metric("Recurrentes", returning_cur)

        st.write("")

        # ---- tendencia única por día
        if not df_cur.empty:
            daily_unique = (
                df_cur.groupby("day")["visitor"]
                .nunique()
                .reset_index(name="visitantes_unicos")
            )
        else:
            daily_unique = pd.DataFrame({"day": [], "visitantes_unicos": []})

        left, right = st.columns([2.15, 1.25], gap="large")

        with left:
            st.markdown("##### Tendencia diaria de visitantes únicos")
            if daily_unique.empty:
                st.info("No hay datos en los últimos 28 días.")
            else:
                _render_line(daily_unique, x="day", y="visitantes_unicos", height=340, key="stats_unique_line")

        with right:
            tabs = st.tabs(["Canales", "Ubicaciones", "Dispositivos"])
            with tabs[0]:
                ch = _prepare_pie(df_cur, "channel", "Direct")
                _render_pie(ch, names="channel", values="count", height=340, key="stats_unique_channel")
            with tabs[1]:
                loc = _prepare_pie(df_cur, "location", "Unknown")
                _render_pie(loc, names="location", values="count", height=340, key="stats_unique_location")
            with tabs[2]:
                dev = _prepare_pie(df_cur, "device", "Desktop")
                _render_pie(dev, names="device", values="count", height=340, key="stats_unique_device")

        st.write("")
        st.markdown("##### Nuevos vs recurrentes")

        n1, n2 = st.columns(2)
        with n1:
            st.metric("Nuevos visitantes", new_cur)
        with n2:
            st.metric("Visitantes recurrentes", returning_cur)

        if not df_cur.empty:
            nr = pd.DataFrame({
                "tipo": ["Nuevos", "Recurrentes"],
                "cantidad": [new_cur, returning_cur],
            })
            _render_bar(nr, x="tipo", y="cantidad", height=280, key="stats_unique_new_vs_returning")
        else:
            st.info("No hay datos suficientes para nuevos vs recurrentes.")

        st.write("")
        st.markdown("##### Detalle por día (visitantes únicos)")

        if daily_unique.empty:
            st.info("No hay datos diarios para mostrar.")
        else:
            st.dataframe(daily_unique, width="stretch", hide_index=True)

    # =========================================================
    # TAB 2: VISITAS / EVENTOS
    # =========================================================
    with t_visits:
        st.markdown("#### Interacciones y visitas de los últimos 28 días")

        total_events_cur = int(len(df_cur))
        total_events_prev = int(len(df_prev))

        prod_events_cur = int(len(df_cur[df_cur["etype"] == "view_product"])) if not df_cur.empty else 0
        prof_events_cur = int(len(df_cur[df_cur["etype"] == "view_profile"])) if not df_cur.empty else 0

        avg_events_per_visitor = round(_safe_div(total_events_cur, max(1, vis_cur)), 2)

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Visitas / eventos", total_events_cur, _metric_delta_text(total_events_cur, total_events_prev))
        v2.metric("Vistas a productos", prod_events_cur)
        v3.metric("Vistas a perfil", prof_events_cur)
        v4.metric("Promedio por visitante", avg_events_per_visitor)

        st.write("")

        # ---- tendencia de eventos
        if not df_cur.empty:
            daily_events_total = (
                df_cur.groupby("day")
                .size()
                .reset_index(name="eventos")
            )
        else:
            daily_events_total = pd.DataFrame({"day": [], "eventos": []})

        left2, right2 = st.columns([2.15, 1.25], gap="large")

        with left2:
            st.markdown("##### Tendencia diaria de visitas / eventos")
            if daily_events_total.empty:
                st.info("No hay datos en los últimos 28 días.")
            else:
                _render_line(daily_events_total, x="day", y="eventos", height=340, key="stats_events_line")

        with right2:
            tabs2 = st.tabs(["Canales", "Ubicaciones", "Dispositivos"])
            with tabs2[0]:
                ch2 = _prepare_pie(df_cur, "channel", "Direct")
                _render_pie(ch2, names="channel", values="count", height=340, key="stats_events_channel")
            with tabs2[1]:
                loc2 = _prepare_pie(df_cur, "location", "Unknown")
                _render_pie(loc2, names="location", values="count", height=340, key="stats_events_location")
            with tabs2[2]:
                dev2 = _prepare_pie(df_cur, "device", "Desktop")
                _render_pie(dev2, names="device", values="count", height=340, key="stats_events_device")

        st.write("")
        st.markdown("##### Comparativo por tipo de evento")

        if not df_cur.empty:
            by_type = (
                df_cur.groupby("etype")
                .size()
                .reset_index(name="cantidad")
                .sort_values("cantidad", ascending=False)
            )
            _render_bar(by_type, x="etype", y="cantidad", height=280, key="stats_events_by_type")
        else:
            st.info("No hay eventos para comparar.")

        st.write("")
        st.markdown("##### Detalle por día (eventos)")

        if not df_cur.empty:
            daily_events = (
                df_cur.groupby(["day", "etype"])
                .size()
                .reset_index(name="count")
                .sort_values(["day", "etype"])
            )

            pivot = (
                daily_events
                .pivot_table(index="day", columns="etype", values="count", fill_value=0)
                .reset_index()
            )

            st.dataframe(pivot, width="stretch", hide_index=True)
        else:
            st.info("No hay detalle diario para mostrar.")

    # =========================================================
    # TAB 3: ORIGEN DEL TRÁFICO
    # =========================================================
    with t_sources:
        st.markdown("#### Desde dónde llegan a tu emprendimiento")

        if df_cur.empty:
            st.info("No hay datos en los últimos 28 días.")
        else:
            # -----------------------------
            # KPIs rápidos
            # -----------------------------
            src_top = (
                df_cur.groupby("entry_source")
                .size()
                .reset_index(name="visitas")
                .sort_values("visitas", ascending=False)
            )

            ctx_top = (
                df_cur.groupby("page_context")
                .size()
                .reset_index(name="visitas")
                .sort_values("visitas", ascending=False)
            )

            top_source = src_top.iloc[0]["entry_source"] if not src_top.empty else "—"
            top_source_n = int(src_top.iloc[0]["visitas"]) if not src_top.empty else 0

            top_context = ctx_top.iloc[0]["page_context"] if not ctx_top.empty else "—"
            top_context_n = int(ctx_top.iloc[0]["visitas"]) if not ctx_top.empty else 0

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Fuentes detectadas", int(df_cur["entry_source"].nunique()))
            s2.metric("Contextos detectados", int(df_cur["page_context"].nunique()))
            s3.metric("Fuente principal", top_source)
            s4.metric("Visitas fuente principal", top_source_n)

            st.write("")

            # -----------------------------
            # Gráficos
            # -----------------------------
            left3, right3 = st.columns([1.5, 1.5], gap="large")

            with left3:
                st.markdown("##### Entrada por fuente")
                src_chart = src_top.head(12).copy()
                if src_chart.empty:
                    st.info("No hay fuentes para mostrar.")
                else:
                    _render_bar(
                        src_chart,
                        x="entry_source",
                        y="visitas",
                        height=320,
                        key="stats_sources_entry_source_bar",
                    )

            with right3:
                st.markdown("##### Entrada por contexto de página")
                ctx_chart = ctx_top.head(12).copy()
                if ctx_chart.empty:
                    st.info("No hay contextos para mostrar.")
                else:
                    _render_bar(
                        ctx_chart,
                        x="page_context",
                        y="visitas",
                        height=320,
                        key="stats_sources_page_context_bar",
                    )

            st.write("")

            # -----------------------------
            # Cruce fuente x tipo de evento
            # -----------------------------
            st.markdown("##### Cruce: fuente vs tipo de evento")

            source_event = (
                df_cur.groupby(["entry_source", "etype"])
                .size()
                .reset_index(name="count")
                .sort_values(["count", "entry_source"], ascending=[False, True])
            )

            if source_event.empty:
                st.info("No hay cruces para mostrar.")
            else:
                pivot_source_event = (
                    source_event.pivot_table(
                        index="entry_source",
                        columns="etype",
                        values="count",
                        fill_value=0
                    )
                    .reset_index()
                )
                st.dataframe(pivot_source_event, width="stretch", hide_index=True)

            st.write("")

            # -----------------------------
            # Tabla detallada de fuentes
            # -----------------------------
            st.markdown("##### Detalle de fuentes")

            source_detail = (
                df_cur.groupby("entry_source")
                .agg(
                    visitas=("entry_source", "size"),
                    visitantes_unicos=("visitor", "nunique"),
                )
                .reset_index()
                .sort_values("visitas", ascending=False)
            )

            if not source_detail.empty:
                source_detail["promedio_por_visitante"] = (
                    source_detail["visitas"] / source_detail["visitantes_unicos"].replace(0, 1)
                ).round(2)

            st.dataframe(source_detail, width="stretch", hide_index=True)

            st.write("")

            # -----------------------------
            # Tabla detallada de contextos
            # -----------------------------
            st.markdown("##### Detalle de contextos de página")

            context_detail = (
                df_cur.groupby("page_context")
                .agg(
                    visitas=("page_context", "size"),
                    visitantes_unicos=("visitor", "nunique"),
                )
                .reset_index()
                .sort_values("visitas", ascending=False)
            )

            if not context_detail.empty:
                context_detail["promedio_por_visitante"] = (
                    context_detail["visitas"] / context_detail["visitantes_unicos"].replace(0, 1)
                ).round(2)

            st.dataframe(context_detail, width="stretch", hide_index=True)