from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"
TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    if not settings.auth_secret_key:
        raise RuntimeError("AUTH_SECRET_KEY is not configured.")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.auth_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expires_at, "token_type": TOKEN_TYPE},
        settings.auth_secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    settings = get_settings()
    if not settings.auth_secret_key:
        raise RuntimeError("AUTH_SECRET_KEY is not configured.")
    payload = jwt.decode(token, settings.auth_secret_key, algorithms=[ALGORITHM])
    if payload.get("token_type") != TOKEN_TYPE:
        raise jwt.InvalidTokenError("Token type is invalid.")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise jwt.InvalidTokenError("Token subject is missing.")
    return subject
