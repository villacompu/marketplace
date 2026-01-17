from __future__ import annotations
from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__rounds=290000,
)

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False
