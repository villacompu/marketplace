from __future__ import annotations

import os
import streamlit as st

from auth.session import get_user, logout
from db.repo_json import load_db, seed_if_empty
from views.router import current_route
from views import feed, home, login, register, admin
from views import public_profile, favorites_page, my_profile, directory
from views import product_detail, my_products
from views import admin_stats, my_stats
from views import force_change_password
from services.presence import heartbeat, online_count






APP_NAME = "Marketplace de Emprendedores"


def _inject_css():
    css_path = os.path.join("assets", "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _topbar(db: dict):
    u = get_user()

    # ✅ Refrescar usuario desde DB para que permisos/limites se reflejen en el menú
    if u:
        u_db = next((x for x in (db.get("users", []) or []) if x.get("id") == u.get("id")), None)
        if u_db:
            u = u_db

    # ✅ Topbar como layout nativo (1 fila estable)
    with st.container():
        route = st.session_state.get("route", "home")
        c1, c2, c3 = st.columns([3.0, 3, 1.2], vertical_alignment="center")

        with c1:
            st.markdown(
                '<div class="brand"><span class="dot"></span> Marketplace de Emprendedores</div>',
                unsafe_allow_html=True
            )
            
            


        with c2:
            if u:
                st.caption(f"🟢 Usuarios en línea: {online_count(ttl_seconds=90)}")
                st.markdown(
                    f'<div class="session">Sesión: <b>{u.get("email","—")}</b> • {u.get("role","—")}</div>',
                    unsafe_allow_html=True   
                )
            else:
                st.markdown('<div class="session">Modo visitante</div>', unsafe_allow_html=True)

            
                

        with c3:
            st.markdown('<div class="top-actions">', unsafe_allow_html=True)

            a1, a2 = st.columns([3, 4], vertical_alignment="center")
            with a1:
                if route != "home":
                    if st.button("🏠", key="btn_top_home", help="Ir al catálogo", width='stretch'):
                        st.query_params.clear()
                        st.session_state["route"] = "home"
                        st.rerun()
                
            with a2:
                if not u:
                    if st.button("👤 Ingreso", key="btn_top_login", help="Ingresar", width='stretch'):
                        st.query_params.clear()
                        st.session_state["route"] = "login"
                        st.rerun()
                else:
                    with st.popover("👤 Perfil", help="Cuenta",width='stretch'):
                        # -------------------------
                        # EMPRENDEDOR
                        # -------------------------
                        if u.get("role") == "EMPRENDEDOR":
                            if st.button("🏪 Mi perfil", width='stretch', key="btn_my_profile"):
                                st.query_params.clear()
                                st.session_state["route"] = "my_profile"
                                st.rerun()

                            if st.button("📦 Mis productos", width='stretch', key="btn_my_products"):
                                st.query_params.clear()
                                st.session_state["route"] = "my_products"
                                st.rerun()

                            if st.button("📊 Mis estadísticas", width='stretch', key="btn_my_stats"):
                                st.query_params.clear()
                                st.session_state["route"] = "my_stats"
                                st.rerun()

                            # st.divider()

                        # -------------------------
                        # ADMIN
                        # -------------------------
                        if u.get("role") == "ADMIN":
                            if st.button("🛠️ Admin", width='stretch', key="btn_admin"):
                                st.query_params.clear()
                                st.session_state["route"] = "admin"
                                st.rerun()

                            if st.button("📊 Analíticas", width='stretch', key="btn_admin_stats"):
                                st.query_params.clear()
                                st.session_state["route"] = "admin_stats"
                                st.rerun()

                         #    st.divider()

                        # -------------------------
                        # COMÚN A TODOS LOGUEADOS
                        # -------------------------
                        # if st.button("❤️ Favoritos", width='stretch', key="btn_favorites"):
                        #     st.session_state["route"] = "favorites"
                         #    st.rerun()

                        st.divider()
                        if st.button("🚪 Cerrar sesión", width='stretch', key="btn_logout"):
                            logout()
                            st.query_params.clear()
                            st.session_state.pop("user", None)
                            st.session_state.pop("_last_qp_sig", None)
                            st.session_state["route"] = "home"
                            st.rerun()


def _sync_route_from_query_params():
    qp = st.query_params

    page = qp.get("page", "")
    spid = qp.get("selected_product_id", "")
    spr = qp.get("selected_profile_id", "")

    current_qp_sig = f"{page}|{spid}|{spr}"
    last_qp_sig = st.session_state.get("_last_qp_sig", "")

    # Si no hay query params útiles, no hacemos nada
    if not page and not spid and not spr:
        return

    # Si ya procesamos exactamente esta misma URL, no volver a forzar ruta
    if current_qp_sig == last_qp_sig:
        return

    if page:
        st.session_state["route"] = page

    if spid:
        st.session_state["selected_product_id"] = spid

    if spr:
        st.session_state["selected_profile_id"] = spr

    st.session_state["_last_qp_sig"] = current_qp_sig




def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🛍️", layout="wide")
    _inject_css()

    db = seed_if_empty(load_db())

    # En linea con la nueva funcionalidad de presencia
    heartbeat(ttl_seconds=90)

    # ✅ 1) Primero sincronizamos la ruta desde la URL
    _sync_route_from_query_params()

    # ✅ 2) Luego pintamos topbar (ya con ruta/selecciones listas)
    _topbar(db)

    route = current_route("home")

    if route == "home":
        home.render(db)
    elif route == "product_detail":
        product_detail.render(db)
    elif route == "public_profile":
        public_profile.render(db)
    elif route == "favorites":
        favorites_page.render(db)
    elif route == "my_profile":
        my_profile.render(db)
    elif route == "login":
        login.render(db)
    elif route == "register":
        register.render(db)
    elif route == "admin":
        admin.render(db)
    elif route == "my_products":
        my_products.render(db)
    elif route == "admin_stats":
        admin_stats.render(db)
    elif route == "my_stats":
        my_stats.render(db)
    elif route == "force_change_password":
        force_change_password.render(db)    
    elif route == "directory":
        directory.render(db)  
    elif route == "feed":
        feed.render(db)
    else:
        st.session_state["route"] = "home"
        st.rerun()


if __name__ == "__main__":
    main()
