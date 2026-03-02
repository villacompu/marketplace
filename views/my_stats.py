from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from auth.session import get_user
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


def _get_meta_field(df: pd.DataFrame, key: str) -> pd.Series:
    """
    Extrae df['meta'][key] de forma segura.
    Si no existe meta o viene mal formado, retorna vacío.
    """
    if "meta" not in df.columns:
        return pd.Series([""] * len(df))

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


def render(db: dict):
    u = get_user()
    if not u:
        st.warning("Debes iniciar sesión.")
        return

    # ✅ Solo emprendedores (y admin si quieres probar)
    if not require_role(["EMPRENDEDOR", "ADMIN"]):
        return

    # ✅ cargar usuario REAL desde DB (no confiar solo en sesión)
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

    # 🔎 encontrar mi perfil y mis productos
    prof = next(
        (p for p in (db.get("profiles", []) or []) if p.get("owner_user_id") == u_db.get("id")),
        None
    ) or {}
    my_profile_id = str(prof.get("id") or "")

    my_products = [p for p in (db.get("products", []) or []) if p.get("owner_user_id") == u_db.get("id")]
    my_product_ids = {str(p.get("id") or "") for p in my_products}
    prod_map = {str(p.get("id") or ""): p for p in (db.get("products", []) or [])}

    # ==========================
    # ✅ BÁSICO (para TODOS)
    # ==========================
    my_prod_views = df[(et == "view_product") & (df["product_id"].astype(str).isin(list(my_product_ids)))]
    my_prof_views = (
        df[(et == "view_profile") & (df["profile_id"].astype(str) == my_profile_id)]
        if my_profile_id else df.iloc[0:0]
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Vistas a mis productos", int(len(my_prod_views)))
    c2.metric("Vistas a mi perfil", int(len(my_prof_views)))
    c3.metric(
        "Productos publicados",
        int(sum(1 for p in my_products if (p.get("status") or "").upper() == "PUBLISHED"))
    )

    st.divider()

    # Top productos
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
            pid = str(r.iloc[0] or "")  # primer col = product_id tras groupby
            pr = prod_map.get(pid) or {}
            rows.append({
                "Producto": pr.get("name", "—"),
                "Categoría": pr.get("category", "—"),
                "Estado": (pr.get("status") or "—"),
                "Vistas": int(r["vistas"]),
            })

        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    # ==========================
    # ✅ AVANZADO (solo con permiso)
    # ==========================
    has_advanced = bool(u_db.get("can_view_stats") is True)

    st.write("")
    st.markdown("### 📈 Analítica avanzada")
    if not has_advanced:
        st.info(
            "Tu cuenta tiene acceso al resumen básico. Para ver analítica avanzada, solicita al administrador "
            "el permiso **Acceso a estadísticas**."
        )
        return

    # ----------------------------------------------------------
    # 1) Base con timestamps + filtro “solo mis eventos”
    # ----------------------------------------------------------
    df2 = df.copy()
    df2["ts_dt"] = pd.to_datetime(df2["ts"], errors="coerce", utc=True)
    df2 = df2.dropna(subset=["ts_dt"])
    if df2.empty:
        st.info("No hay timestamps válidos para graficar.")
        return

    et2 = _event_type(df2)

    df_me_all = df2[
        ((et2 == "view_product") & (df2["product_id"].astype(str).isin(list(my_product_ids))))
        | ((et2 == "view_profile") & (df2["profile_id"].astype(str) == my_profile_id))
    ].copy()

    if df_me_all.empty:
        st.info("Aún no hay eventos tuyos para analítica avanzada.")
        return

    # ----------------------------------------------------------
    # 2) “Visitantes” 28 días vs 28 días previos + tendencia
    # ----------------------------------------------------------
    end = df_me_all["ts_dt"].max()
    cur_start = end - pd.Timedelta(days=28)
    prev_start = cur_start - pd.Timedelta(days=28)

    df_cur = df_me_all[(df_me_all["ts_dt"] >= cur_start) & (df_me_all["ts_dt"] <= end)].copy()
    df_prev = df_me_all[(df_me_all["ts_dt"] >= prev_start) & (df_me_all["ts_dt"] < cur_start)].copy()

    df_cur["visitor"] = df_cur.apply(_visitor_id, axis=1)
    df_prev["visitor"] = df_prev.apply(_visitor_id, axis=1)

    vis_cur = int(df_cur["visitor"].nunique())
    vis_prev = int(df_prev["visitor"].nunique())
    base_prev = max(1, vis_prev)
    pct = ((vis_cur - vis_prev) / base_prev) * 100.0

    # Tendencia diaria (visitantes únicos)
    df_cur["day"] = df_cur["ts_dt"].dt.date.astype(str)
    daily = df_cur.groupby("day")["visitor"].nunique().reset_index(name="visitors")

    # ----------------------------------------------------------
    # 3) Meta para donuts: Canal / Ubicación / Dispositivo
    # (Si no estás guardando meta aún, saldrá “Direct/Unknown/Desktop”)
    # ----------------------------------------------------------
    df_cur["channel"] = _get_meta_field(df_cur, "channel").replace({"": "Direct"})
    df_cur["device"] = _get_meta_field(df_cur, "device").replace({"": "Desktop"})
    df_cur["location"] = _get_meta_field(df_cur, "country").replace({"": "Unknown"})

    # ----------------------------------------------------------
    # 4) UI tipo “Analytics”
    # ----------------------------------------------------------
    left, right = st.columns([2.2, 1.3], gap="large")

    with left:
        st.markdown("#### Todos los visitantes")
        st.metric("Visitantes (últimos 28 días)", vis_cur, f"{pct:.1f}% vs 28 días previos")

        fig_line = px.line(daily, x="day", y="visitors")
        fig_line.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig_line, width='stretch')

    with right:
        tab1, tab2, tab3 = st.tabs(["Canales", "Ubicaciones", "Dispositivos"])

        with tab1:
            ch = df_cur.groupby("channel").size().reset_index(name="count").sort_values("count", ascending=False)
            fig = px.pie(ch, names="channel", values="count", hole=0.65)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
            st.plotly_chart(fig, width='stretch')

        with tab2:
            loc = df_cur.groupby("location").size().reset_index(name="count").sort_values("count", ascending=False)
            fig = px.pie(loc, names="location", values="count", hole=0.65)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
            st.plotly_chart(fig, width='stretch')

        with tab3:
            dev = df_cur.groupby("device").size().reset_index(name="count").sort_values("count", ascending=False)
            fig = px.pie(dev, names="device", values="count", hole=0.65)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
            st.plotly_chart(fig, width='stretch')

    st.divider()

    # ----------------------------------------------------------
    # 5) Tabla diaria (opcional): view_product vs view_profile
    # ----------------------------------------------------------
    st.markdown("#### Detalle por día (eventos)")
    df_cur["etype"] = _event_type(df_cur)

    daily_events = (
        df_cur.groupby(["day", "etype"])
        .size()
        .reset_index(name="count")
        .sort_values(["day", "etype"])
    )

    pivot = daily_events.pivot_table(index="day", columns="etype", values="count", fill_value=0).reset_index()
    st.dataframe(pivot, width='stretch', hide_index=True)

