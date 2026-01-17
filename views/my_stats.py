from __future__ import annotations

import streamlit as st
import pandas as pd

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
    st.markdown('<div class="muted">Resumen de exposición de tu emprendimiento (sin datos sensibles).</div>', unsafe_allow_html=True)
    st.write("")

    events = db.get("events", []) or []
    if not events:
        st.info("Aún no hay eventos registrados. Navega productos/perfil para generar estadísticas.")
        return

    df = pd.DataFrame(events)

    # Normalizar columnas por si hay eventos viejos
    for c in ["product_id", "profile_id", "ts", "meta"]:
        if c not in df.columns:
            df[c] = ""

    et = _event_type(df)

    # 🔎 encontrar mi perfil y mis productos
    prof = next((p for p in (db.get("profiles", []) or []) if p.get("owner_user_id") == u_db.get("id")), None) or {}
    my_profile_id = str(prof.get("id") or "")

    my_products = [p for p in (db.get("products", []) or []) if p.get("owner_user_id") == u_db.get("id")]
    my_product_ids = {str(p.get("id") or "") for p in my_products}
    prod_map = {str(p.get("id") or ""): p for p in (db.get("products", []) or [])}

    # ==========================
    # ✅ BÁSICO (para TODOS)
    # ==========================
    my_prod_views = df[(et == "view_product") & (df["product_id"].astype(str).isin(list(my_product_ids)))]
    my_prof_views = df[(et == "view_profile") & (df["profile_id"].astype(str) == my_profile_id)] if my_profile_id else df.iloc[0:0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Vistas a mis productos", int(len(my_prod_views)))
    c2.metric("Vistas a mi perfil", int(len(my_prof_views)))
    c3.metric("Productos publicados", int(sum(1 for p in my_products if (p.get("status") or "").upper() == "PUBLISHED")))

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
            pid = str(r["product_id"] or r["index"] or "")
            pr = prod_map.get(pid) or {}
            rows.append({
                "Producto": pr.get("name", "—"),
                "Categoría": pr.get("category", "—"),
                "Estado": (pr.get("status") or "—"),
                "Vistas": int(r["vistas"]),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ==========================
    # ✅ AVANZADO (solo con permiso)
    # ==========================
    has_advanced = bool(u_db.get("can_view_stats") is True)

    st.write("")
    st.markdown("### 📈 Analítica avanzada")
    if not has_advanced:
        st.info("Tu cuenta tiene acceso al resumen básico. Para ver analítica avanzada, solicita al administrador el permiso **Acceso a estadísticas**.")
        return

    # ---- Tendencia por día (últimos 30 días) ----
    st.write("")
    st.markdown("#### Tendencia (últimos 30 días)")

    # parse ts -> datetime (si ts viene en ISO)
    df2 = df.copy()
    df2["ts_dt"] = pd.to_datetime(df2["ts"], errors="coerce", utc=True)
    df2 = df2.dropna(subset=["ts_dt"])
    if df2.empty:
        st.info("No hay timestamps válidos para graficar tendencia.")
    else:
        cutoff = df2["ts_dt"].max() - pd.Timedelta(days=30)
        df2 = df2[df2["ts_dt"] >= cutoff]

        # filtrar solo eventos del emprendedor (sus prod + su perfil)
        df_me = df2[
            ((et.loc[df2.index] == "view_product") & (df2["product_id"].astype(str).isin(list(my_product_ids))))
            | ((et.loc[df2.index] == "view_profile") & (df2["profile_id"].astype(str) == my_profile_id))
        ].copy()

        if df_me.empty:
            st.info("No hay eventos tuyos en los últimos 30 días.")
        else:
            df_me["day"] = df_me["ts_dt"].dt.date.astype(str)
            df_me["etype"] = _event_type(df_me)

            daily = (
                df_me.groupby(["day", "etype"])
                .size()
                .reset_index(name="count")
                .sort_values(["day", "etype"])
            )

            # pivot simple para mostrar tabla (y que sea fácil leer)
            pivot = daily.pivot_table(index="day", columns="etype", values="count", fill_value=0).reset_index()
            st.dataframe(pivot, use_container_width=True, hide_index=True)

   

    
