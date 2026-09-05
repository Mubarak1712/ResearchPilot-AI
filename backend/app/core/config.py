from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]

# Environment variables supplied by the shell or deployment platform keep
# precedence over local development values in backend/.env.
load_dotenv(BACKEND_DIR / ".env", override=False)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_positive_int(value: str | None, name: str) -> int:
    if value is None or not value.strip():
        raise ValueError(f"{name} must be configured as a positive integer.")

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be configured as a positive integer.") from error

    if parsed <= 0:
        raise ValueError(f"{name} must be configured as a positive integer.")
    return parsed


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    auth_secret_key: str | None
    auth_token_expire_minutes: int
    sqlalchemy_echo: bool = False

    # Email / SMTP configuration (optional)
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    email_from: str | None = None

    # Verification and password reset tokens (in minutes)
    verification_token_expire_minutes: int = 60 * 24  # default 1 day
    password_reset_token_expire_minutes: int = 60  # default 1 hour

    # Frontend base URL for verification/reset links (optional)
    frontend_base_url: str | None = None

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = (os.getenv("DATABASE_URL") or "").strip() or None

    # Parse optional SMTP port
    smtp_port_str = (os.getenv("SMTP_PORT") or "").strip() or None
    smtp_port = int(smtp_port_str) if smtp_port_str is not None else None

    # Parse optional token expirations
    verification_token_expire_minutes = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_MINUTES") or 60 * 24)
    password_reset_token_expire_minutes = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES") or 60)

    return Settings(
        database_url=database_url,
        auth_secret_key=(os.getenv("AUTH_SECRET_KEY") or "").strip() or None,
        auth_token_expire_minutes=_parse_positive_int(
            os.getenv("AUTH_TOKEN_EXPIRE_MINUTES"), "AUTH_TOKEN_EXPIRE_MINUTES"
        ),
        sqlalchemy_echo=_parse_bool(os.getenv("SQLALCHEMY_ECHO")),
        smtp_host=(os.getenv("SMTP_HOST") or "").strip() or None,
        smtp_port=smtp_port,
        smtp_user=(os.getenv("SMTP_USER") or "").strip() or None,
        smtp_password=(os.getenv("SMTP_PASSWORD") or "").strip() or None,
        smtp_use_tls=_parse_bool(os.getenv("SMTP_USE_TLS")),
        email_from=(os.getenv("EMAIL_FROM") or "").strip() or None,
        verification_token_expire_minutes=verification_token_expire_minutes,
        password_reset_token_expire_minutes=password_reset_token_expire_minutes,
        frontend_base_url=(os.getenv("FRONTEND_BASE_URL") or "").strip() or None,
    )
