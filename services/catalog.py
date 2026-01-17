# services/catalog.py
from __future__ import annotations

from typing import Any
import unicodedata


def _norm_text(s: str) -> str:
    """
    Normaliza texto para búsquedas:
    - lower()
    - elimina tildes/diacríticos
    - trim
    """
    s = (s or "").strip().lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return s


def _match_query(haystack: str, needle: str) -> bool:
    """
    Match tolerante:
    - ignora tildes y mayúsculas
    - múltiples palabras (AND): todas deben aparecer
    Ej: "café aurora" matchea "CAFE" y "Auróra"
    """
    n = _norm_text(needle)
    if not n:
        return True

    h = _norm_text(haystack)
    terms = [t for t in n.split() if t]
    return all(t in h for t in terms)


def format_price(price_type: str | None, price_value: Any) -> str:
    pt = (price_type or "FIXED").upper()
    pv = price_value

    if pt == "AGREE":
        return "A convenir"
    if pt == "FROM":
        return f"Desde ${int(pv or 0):,}".replace(",", ".")
    return f"${int(pv or 0):,}".replace(",", ".")


def filter_products(
    db: dict,
    q: str,
    category: str,
    city: str,
    tag: str,
    price_range: tuple[int, int],
    sort_by: str,
) -> list[dict]:
    """
    Retorna productos publicados + _profile embebido.
    Búsqueda avanzada (tildes/mayúsculas) aplicada a:
    - name, description, category, tags
    - business_name, city
    - (opcional) email del dueño si existe en db["users"]
    """
    products = db.get("products", []) or []
    profiles = db.get("profiles", []) or []
    users = db.get("users", []) or []

    profiles_by_id = {p.get("id"): p for p in profiles}
    users_by_id = {u.get("id"): u for u in users}

    q = (q or "").strip()
    want_cat = (category or "Todas")
    want_city = (city or "Todas")
    want_tag = (tag or "Todos")

    pr_min, pr_max = price_range if price_range else (0, 10**9)

    rows: list[dict] = []

    for p in products:
        if (p.get("status") or "").upper() != "PUBLISHED":
            continue

        prof = profiles_by_id.get(p.get("profile_id")) or {}
        if not prof.get("is_approved", False):
            # solo perfiles aprobados publican en el home
            continue

        # ----- filtros exactos (categoría / ciudad) -----
        p_cat = p.get("category") or ""
        if want_cat != "Todas" and p_cat != want_cat:
            continue

        prof_city = prof.get("city") or ""
        if want_city != "Todas" and prof_city != want_city:
            continue

        # ----- filtro tag (normalizado) -----
        p_tags = p.get("tags") or []
        if want_tag != "Todos":
            want_tag_n = _norm_text(want_tag)
            tags_n = [_norm_text(t) for t in p_tags]
            if want_tag_n not in tags_n:
                continue

        # ----- filtro precio -----
        pv = p.get("price_value")
        if isinstance(pv, (int, float)):
            pv_i = int(pv)
            if pv_i < int(pr_min) or pv_i > int(pr_max):
                continue
        # si price_type=AGREE (None), lo dejamos pasar

        # ----- búsqueda avanzada -----
        if q:
            owner = users_by_id.get(p.get("owner_user_id")) or {}
            hay = " ".join([
                p.get("name") or "",
                p.get("description") or "",
                p.get("category") or "",
                " ".join(p_tags) if p_tags else "",
                prof.get("business_name") or "",
                prof.get("city") or "",
                owner.get("email") or "",
            ])
            if not _match_query(hay, q):
                continue

        # embebemos perfil (como ya usas en home)
        out = dict(p)
        out["_profile"] = prof
        rows.append(out)

    # ----- orden -----
    sort_by = (sort_by or "Relevancia").strip()

    if sort_by == "Más recientes":
        rows.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return rows

    if sort_by == "Precio ↑":
        rows.sort(key=lambda x: int(x.get("price_value") or 10**18))
        return rows

    if sort_by == "Precio ↓":
        rows.sort(key=lambda x: int(x.get("price_value") or 0), reverse=True)
        return rows

    # Relevancia (simple y efectiva):
    # - si hay query, prioriza coincidencias en nombre y luego en descripción
    if q:
        terms = [t for t in _norm_text(q).split() if t]

        def _score(x: dict) -> tuple[int, str]:
            name = _norm_text(x.get("name") or "")
            desc = _norm_text(x.get("description") or "")
            # score más alto = mejor
            s = 0
            for t in terms:
                if t in name:
                    s += 5
                if t in desc:
                    s += 2
            # desempate por reciente
            ts = x.get("updated_at") or x.get("created_at") or ""
            return (s, ts)

        rows.sort(key=_score, reverse=True)
    else:
        rows.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)

    return rows
