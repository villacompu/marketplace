from __future__ import annotations
import json, os, uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from filelock import FileLock

from auth.hashing import hash_password
from services.validators import normalize_email

DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "db.json")
DB_LOCK = os.path.join(DATA_DIR, "db.json.lock")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def new_id() -> str:
    return str(uuid.uuid4())

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def default_db() -> Dict[str, Any]:
    return {"meta":{"version":1,"created_at":now_iso()},"users":[],"profiles":[],"products":[],"favorites":[],"events":[]}

def load_db() -> Dict[str, Any]:
    ensure_dirs()
    if not os.path.exists(DB_PATH):
        with FileLock(DB_LOCK):
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(default_db(), f, ensure_ascii=False, indent=2)
    with FileLock(DB_LOCK):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

def save_db(db: Dict[str, Any]) -> None:
    ensure_dirs()
    with FileLock(DB_LOCK):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

def find_user_by_email(db: Dict[str, Any], email: str) -> Optional[Dict[str, Any]]:
    email = normalize_email(email)
    for u in db["users"]:
        if u["email"] == email:
            return u
    return None

def user_profile(db: Dict[str, Any], owner_user_id: str) -> Optional[Dict[str, Any]]:
    for p in db["profiles"]:
        if p["owner_user_id"] == owner_user_id:
            return p
    return None

def seed_if_empty(db: Dict[str, Any]) -> Dict[str, Any]:
    if db["users"]:
        return db

    admin_id = new_id()
    emp_id = new_id()

    db["users"].append({
        "id": admin_id, "email": "admin@demo.com",
        "password_hash": hash_password("Admin123!"),
        "role":"ADMIN","status":"ACTIVE",
        "created_at": now_iso(),"updated_at": now_iso(),
        "reset_token": None,"reset_token_expires_at": None,
    })
    db["users"].append({
        "id": emp_id, "email": "emprendedor@demo.com",
        "password_hash": hash_password("Emprendedor123!"),
        "role":"EMPRENDEDOR","status":"ACTIVE",
        "created_at": now_iso(),"updated_at": now_iso(),
        "reset_token": None,"reset_token_expires_at": None,
    })

    profile_id = new_id()
    db["profiles"].append({
        "id": profile_id, "owner_user_id": emp_id,
        "business_name":"Café Aurora",
        "short_desc":"Café artesanal y postres hechos en casa.",
        "long_desc":"Somos un emprendimiento local de café y repostería. Hacemos envíos en la ciudad y ofrecemos catering para eventos pequeños.",
        "categories":["Comida","Bebidas"],
        "city":"Bogotá",
        "availability":"Lun-Sáb 8am–6pm",
        "links":{"instagram":"https://instagram.com","facebook":"","tiktok":"","whatsapp":"https://wa.me/573001112233","website":"","external_catalog":""},
        "logo_url":"","gallery_urls":[],
        "is_approved": True,
        "created_at": now_iso(),"updated_at": now_iso(),
    })

    demo_products = [
        {"name":"Caja de brownies x6","description":"Brownies húmedos con chocolate premium. Ideal para regalo.","price_type":"FIXED","price_value":32000,"category":"Comida","subcategory":"Postres","tags":["brownie","regalo","chocolate"]},
        {"name":"Café molido 250g","description":"Café de origen, tueste medio, notas a cacao y caramelo.","price_type":"FROM","price_value":28000,"category":"Bebidas","subcategory":"Café","tags":["café","origen","tostado"]},
        {"name":"Catering para eventos","description":"Servicio a convenir según cantidad de personas y menú.","price_type":"AGREE","price_value":None,"category":"Servicios","subcategory":"Eventos","tags":["catering","eventos"]},
    ]
    for pr in demo_products:
        db["products"].append({
            "id": new_id(),
            "owner_user_id": emp_id,
            "profile_id": profile_id,
            "name": pr["name"],
            "description": pr["description"],
            "price_type": pr["price_type"],
            "price_value": pr["price_value"],
            "category": pr["category"],
            "subcategory": pr["subcategory"],
            "tags": pr["tags"],
            "image_urls": [],
            "status": "PUBLISHED",
            "stock": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

    save_db(db)
    return db

def set_reset_token(db: Dict[str, Any], email: str, minutes: int = 30) -> Optional[str]:
    u = find_user_by_email(db, email)
    if not u:
        return None
    token = uuid.uuid4().hex[:10]
    u["reset_token"] = token
    u["reset_token_expires_at"] = (datetime.utcnow() + timedelta(minutes=minutes)).replace(microsecond=0).isoformat() + "Z"
    u["updated_at"] = now_iso()
    save_db(db)
    return token

def find_profile(db, profile_id: str):
    for p in db.get("profiles", []):
        if p.get("id") == profile_id:
            return p
    return None

def find_product(db, product_id: str):
    for p in db.get("products", []):
        if p.get("id") == product_id:
            return p
    return None
