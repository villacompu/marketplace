from __future__ import annotations
from typing import Dict, Any, List, Optional
import streamlit as st
from db.repo_json import save_db, new_id, now_iso
from auth.session import get_user


def _visitor_favs_key() -> str:
    return "visitor_favorites"


def _get_owner() -> tuple[str, str]:
    """
    owner_type:
      - USER: persistente en JSON
      - VISITOR: session_state
    """
    u = get_user()
    if u:
        return ("USER", u["id"])
    # VISITOR: id "virtual" solo para identificar en session (no se escribe a db)
    return ("VISITOR", "session")


def list_favorites(db: Dict[str, Any]) -> List[str]:
    owner_type, owner_id = _get_owner()

    if owner_type == "VISITOR":
        return list(st.session_state.get(_visitor_favs_key(), set()))

    favs = db.get("favorites", [])
    return [f["product_id"] for f in favs if f.get("owner_type") == "USER" and f.get("owner_id") == owner_id]


def is_favorite(db: Dict[str, Any], product_id: str) -> bool:
    return product_id in set(list_favorites(db))


def toggle_favorite(db: Dict[str, Any], product_id: str) -> None:
    owner_type, owner_id = _get_owner()

    if owner_type == "VISITOR":
        current = st.session_state.get(_visitor_favs_key())
        if current is None:
            current = set()
        else:
            current = set(current)

        if product_id in current:
            current.remove(product_id)
        else:
            current.add(product_id)

        st.session_state[_visitor_favs_key()] = current
        return

    # USER persistente
    db.setdefault("favorites", [])
    favs = db["favorites"]

    # si ya existe, eliminar
    for i, f in enumerate(favs):
        if f.get("owner_type") == "USER" and f.get("owner_id") == owner_id and f.get("product_id") == product_id:
            favs.pop(i)
            save_db(db)
            return

    # si no existe, crear
    favs.append({
        "id": new_id(),
        "owner_type": "USER",
        "owner_id": owner_id,
        "product_id": product_id,
        "created_at": now_iso(),
    })
    save_db(db)
