from __future__ import annotations

import os
import streamlit as st

from auth.session import get_user, logout
from db.repo_json import load_db, seed_if_empty
from views.router import current_route
from views import home, login, register, admin
from views import public_profile, favorites_page, my_profile
from views import product_detail, my_products
from views import admin_stats, my_stats


APP_NAME = "Marketplace de Emprendedores"


def _inject_css():
    css_path = os.path.join("assets", "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _topbar(db: dict):
    u = get_user()

    qp = st.query_params
    if "page" in qp:
        st.session_state["route"] = qp.get("page")
        # ejemplo: si viene pid
        if "selected_product_id" in qp:
            st.session_state["selected_product_id"] = qp.get("selected_product_id")
        if "selected_profile_id" in qp:
            st.session_state["selected_profile_id"] = qp.get("selected_profile_id")

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
                st.markdown(
                    f'<div class="session">Sesión: <b>{u.get("email","—")}</b> • {u.get("role","—")}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="session">Modo visitante</div>', unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="top-actions">', unsafe_allow_html=True)

            a1, a2 = st.columns([3, 1], vertical_alignment="center")
            with a1:
                if route != "home":
                    if st.button("🏠", key="btn_top_home", help="Ir al catálogo", use_container_width=True):
                        st.session_state["route"] = "home"
                        st.rerun()

            with a2:
                if not u:
                    if st.button("👤", key="btn_top_login", help="Ingresar", use_container_width=True):
                        st.session_state["route"] = "login"
                        st.rerun()
                else:
                    with st.popover("👤", help="Cuenta"):
                        # -------------------------
                        # EMPRENDEDOR
                        # -------------------------
                        if u.get("role") == "EMPRENDEDOR":
                            if st.button("🏪 Mi perfil", use_container_width=True, key="btn_my_profile"):
                                st.session_state["route"] = "my_profile"
                                st.rerun()

                            if st.button("📦 Mis productos", use_container_width=True, key="btn_my_products"):
                                st.session_state["route"] = "my_products"
                                st.rerun()

                            if st.button("📊 Mis estadísticas", use_container_width=True, key="btn_my_stats"):
                                st.session_state["route"] = "my_stats"
                                st.rerun()

                            # st.divider()

                        # -------------------------
                        # ADMIN
                        # -------------------------
                        if u.get("role") == "ADMIN":
                            if st.button("🛠️ Admin", use_container_width=True, key="btn_admin"):
                                st.session_state["route"] = "admin"
                                st.rerun()

                            if st.button("📊 Analíticas", use_container_width=True, key="btn_admin_stats"):
                                st.session_state["route"] = "admin_stats"
                                st.rerun()

                         #    st.divider()

                        # -------------------------
                        # COMÚN A TODOS LOGUEADOS
                        # -------------------------
                        # if st.button("❤️ Favoritos", use_container_width=True, key="btn_favorites"):
                        #     st.session_state["route"] = "favorites"
                         #    st.rerun()

                        st.divider()
                        if st.button("⎋ Cerrar sesión", use_container_width=True, key="btn_logout"):
                            logout()
                            # ✅ extra: limpia lo que pudo quedar en session_state
                            st.session_state.pop("user", None)
                            st.session_state["route"] = "home"
                            st.rerun()


def _sync_route_from_query_params():
    
    qp = st.query_params  # Streamlit >= 1.30

    page = qp.get("page")
    if page:
        st.session_state["route"] = page

    spid = qp.get("selected_product_id")
    if spid:
        st.session_state["selected_product_id"] = spid

    spr = qp.get("selected_profile_id")
    if spr:
        st.session_state["selected_profile_id"] = spr




def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🛍️", layout="wide")
    _inject_css()

    db = seed_if_empty(load_db())

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
    else:
        st.session_state["route"] = "home"
        st.rerun()


if __name__ == "__main__":
    main()
