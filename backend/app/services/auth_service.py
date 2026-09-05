from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from pwdlib.exceptions import UnknownHashError

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.auth_token_repository import AuthTokenRepository
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.email_service import send_email
from app.core.config import get_settings
from app.models.auth_token import AuthToken
from datetime import datetime, timedelta, timezone
import secrets


class AuthServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


from typing import Tuple, Optional

def register_user(*, session: Session | None, payload: UserCreate) -> Tuple[UserResponse, Optional[str]]:
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)

    email = str(payload.email).lower()
    repository = UserRepository(session)
    if repository.find_by_email(email) is not None:
        raise AuthServiceError("An account with this email already exists.", 409)

    try:
        user = repository.create(
            User(email=email, password_hash=hash_password(payload.password), is_email_verified=False)
        )
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise AuthServiceError("An account with this email already exists.", 409) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise AuthServiceError("The account could not be created.", 503) from error

    # Create a verification token and send verification email
    settings = get_settings()
    token_repo = AuthTokenRepository(session)
    token_value = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.verification_token_expire_minutes)
    token = AuthToken(token=token_value, user_id=user.id, token_type="verification", expires_at=expires_at)
    try:
        token_repo.create(token)
        session.commit()
    except Exception:
        session.rollback()
        # If token persistence fails, continue without blocking account creation
    # Send email (best-effort) — do not fail registration if email cannot be sent
    try:
        settings = get_settings()
        if settings.frontend_base_url:
            verification_url = f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={token_value}"
        else:
            verification_url = f"/api/v1/auth/verify-email?token={token_value}"

        send_email(
            subject="Verify your ResearchPilot account",
            recipient=user.email,
            body=(f"Please verify your email by visiting: {verification_url}\n\n" "If you did not create this account, please ignore this message."),
        )
    except Exception as exc:
        # Best-effort only; do not abort registration — but ensure the error is logged by send_email
        pass

    # Return the created user and the verification token value (token may be None if persistence failed)
    return UserResponse.model_validate(user), token_value


def login_user(*, session: Session | None, payload: UserLogin) -> TokenResponse:
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)

    user = UserRepository(session).find_by_email(str(payload.email).lower())
    try:
        password_matches = user is not None and verify_password(
            payload.password, user.password_hash
        )
    except (UnknownHashError, TypeError, ValueError):
        password_matches = False

    # If the user exists but is not verified, give an explicit message so the client can prompt verification
    if user is not None and not getattr(user, 'is_email_verified', False):
        raise AuthServiceError("Please verify your email before signing in.", 401)

    if user is None or not password_matches or not user.is_active:
        # Generic invalid credentials message for nonexistent/wrong-password/inactive
        raise AuthServiceError("Invalid email or password.", 401)

    try:
        return TokenResponse(access_token=create_access_token(str(user.id)))
    except RuntimeError as error:
        raise AuthServiceError("Authentication is not configured.", 503) from error


def get_user_by_id(*, session: Session | None, user_id: int) -> UserResponse:
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)

    try:
        user = session.get(User, user_id)
    except SQLAlchemyError as error:
        raise AuthServiceError("Authentication is temporarily unavailable.", 503) from error

    if user is None or not user.is_active:
        raise AuthServiceError("User account is unavailable.", 401)
    return UserResponse.model_validate(user)


# Token & verification helpers
def _consume_token(session: Session, token_value: str, expected_type: str):
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)

    token_repo = AuthTokenRepository(session)
    token = token_repo.find_by_token(token_value)
    if token is None or token.token_type != expected_type:
        raise AuthServiceError("Invalid or expired token.", 400)

    if token.used:
        raise AuthServiceError("Invalid or expired token.", 400)

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise AuthServiceError("Invalid or expired token.", 400)

    return token


def verify_email_token(*, session: Session | None, token_value: str) -> None:
    token = _consume_token(session, token_value, "verification")
    user = session.get(User, token.user_id)
    if user is None:
        raise AuthServiceError("User account is unavailable.", 400)

    try:
        user.is_email_verified = True
        token.used = True
        session.add(user)
        session.add(token)
        session.commit()
    except Exception:
        session.rollback()
        raise AuthServiceError("Unable to verify email.", 503)


def resend_verification(*, session: Session | None, email: str) -> Optional[str]:
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)
    user = UserRepository(session).find_by_email(email.lower())
    # Always return success to avoid user enumeration; if user exists and not verified, send email
    if user and not getattr(user, "is_email_verified", False):
        settings = get_settings()
        token_repo = AuthTokenRepository(session)
        token_value = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.verification_token_expire_minutes)
        token = AuthToken(token=token_value, user_id=user.id, token_type="verification", expires_at=expires_at)
        try:
            token_repo.create(token)
            session.commit()
        except Exception:
            session.rollback()
        return token_value
    return None


def create_password_reset_token(*, session: Session | None, email: str) -> Optional[str]:
    if session is None:
        raise AuthServiceError("Authentication is unavailable because the database is not configured.", 503)
    user = UserRepository(session).find_by_email(email.lower())
    # Always respond success; only send email if user exists
    if user:
        settings = get_settings()
        token_repo = AuthTokenRepository(session)
        token_value = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes)
        token = AuthToken(token=token_value, user_id=user.id, token_type="password_reset", expires_at=expires_at)
        try:
            token_repo.create(token)
            session.commit()
        except Exception:
            session.rollback()
        return token_value
    return None


def reset_password(*, session: Session | None, token_value: str, new_password: str) -> None:
    token = _consume_token(session, token_value, "password_reset")
    user = session.get(User, token.user_id)
    if user is None:
        raise AuthServiceError("User account is unavailable.", 400)
    try:
        user.password_hash = hash_password(new_password)
        token.used = True
        session.add(user)
        session.add(token)
        session.commit()
    except Exception:
        session.rollback()
        raise AuthServiceError("Unable to reset password.", 503)
