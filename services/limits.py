# services/limits.py
from __future__ import annotations


def get_publish_limit(user: dict) -> int:
    """
    Límite de publicaciones PUBLISHED por usuario.
    -1 = ilimitado
    0  = no puede publicar
    """
    try:
        v = user.get("max_published_products", 5)
        if v is None:
            return 5
        return int(v)
    except Exception:
        return 5


def count_published_products(db: dict, user_id: str, exclude_product_id: str | None = None) -> int:
    products = db.get("products", []) or []
    n = 0
    for p in products:
        if p.get("owner_user_id") != user_id:
            continue
        if exclude_product_id and p.get("id") == exclude_product_id:
            continue
        if (p.get("status") or "").upper() == "PUBLISHED":
            n += 1
    return n


def can_publish_more(db: dict, user: dict, exclude_product_id: str | None = None) -> bool:
    limit = get_publish_limit(user)
    if limit == -1:
        return True
    if limit <= 0:
        return False
    used = count_published_products(db, user.get("id"), exclude_product_id=exclude_product_id)
    return used < limit
