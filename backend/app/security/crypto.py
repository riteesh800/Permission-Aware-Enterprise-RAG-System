from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.config import Settings

logger = logging.getLogger(__name__)
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        logger.warning("password_verify_failed")
        return False


def password_meets_policy(password: str) -> bool:
    if len(password) < 6 or len(password) > 256:
        return False
    
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    
    return has_letter and has_number



def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_query(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()


def hash_ip(ip: str | None, secret: str) -> str | None:
    if not ip:
        return None
    return hmac.HMAC(secret.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()


def create_access_token(settings: Settings, user_id: str, app_role: str, token_version: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": app_role,
        "tv": token_version,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def decode_token(settings: Settings, token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def generate_unique_identifier(prefix: str) -> str:
    suffix = f"{secrets.randbelow(1_000_000):06d}"
    return f"{prefix}-{suffix}"
