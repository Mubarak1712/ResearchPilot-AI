from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyTokenRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
import logging
from app.services.auth_service import (
    AuthServiceError,
    login_user,
    register_user,
    verify_email_token,
    resend_verification,
    create_password_reset_token,
    reset_password,
)
from app.services.email_service import send_email
from app.core.config import get_settings

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    payload: UserCreate,
    db_session: Annotated[Session | None, Depends(get_db_session)],
    response: Response,
) -> UserResponse:
    try:
        from app.services.auth_service import register_user

        user_obj, token_value = register_user(session=db_session, payload=payload)
        # Attempt to send verification email now so we can inform the client via a header.
        # When SMTP is not configured, expose a development-only verification URL instead of
        # pretending an email was delivered.
        email_sent = False
        verification_url = None
        if token_value:
            settings = get_settings()
            if settings.frontend_base_url:
                verification_url = f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={token_value}"
            else:
                verification_url = f"/api/v1/auth/verify-email?token={token_value}"

            try:
                send_email(
                    subject="Verify your ResearchPilot account",
                    recipient=user_obj.email,
                    body=(
                        f"Please verify your email by visiting: {verification_url}\n\n"
                        "If you did not create this account, please ignore this message."
                    ),
                )
                email_sent = True
            except Exception as exc:
                logger.exception("Verification email send failed: %s", exc)
                email_sent = False

        response.headers["X-Verification-Email-Sent"] = "true" if email_sent else "false"
        if verification_url is not None and not email_sent:
            response.headers["X-Verification-URL"] = verification_url
        return user_obj
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> TokenResponse:
    try:
        return login_user(session=db_session, payload=payload)
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/verify-email", status_code=200)
def verify_email(
    payload: VerifyTokenRequest,
    db_session: Annotated[Session | None, Depends(get_db_session)],
):
    try:
        verify_email_token(session=db_session, token_value=payload.token)
        return {"status": "ok"}
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/resend-verification", status_code=200)
def resend_verification_endpoint(
    payload: ResendVerificationRequest,
    db_session: Annotated[Session | None, Depends(get_db_session)],
    response: Response,
):
    try:
        token_value = resend_verification(session=db_session, email=str(payload.email))
        email_sent = False
        verification_url = None
        if token_value:
            settings = get_settings()
            if settings.frontend_base_url:
                verification_url = f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={token_value}"
            else:
                verification_url = f"/api/v1/auth/verify-email?token={token_value}"
            try:
                send_email(
                    subject="Verify your ResearchPilot account",
                    recipient=str(payload.email),
                    body=(
                        f"Please verify your email by visiting: {verification_url}\n\n"
                        "If you did not request this, please ignore."
                    ),
                )
                email_sent = True
            except Exception as exc:
                logger.exception("Resend verification email failed: %s", exc)
                email_sent = False
        response.headers["X-Verification-Email-Sent"] = "true" if email_sent else "false"
        if verification_url is not None and not email_sent:
            response.headers["X-Verification-URL"] = verification_url
        return {"status": "ok"}
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/forgot-password", status_code=200)
def forgot_password_endpoint(
    payload: ForgotPasswordRequest,
    db_session: Annotated[Session | None, Depends(get_db_session)],
    response: Response,
):
    try:
        token_value = create_password_reset_token(session=db_session, email=str(payload.email))
        email_sent = False
        reset_url = None
        if token_value:
            settings = get_settings()
            if settings.frontend_base_url:
                reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token_value}"
            else:
                reset_url = f"/api/v1/auth/reset-password?token={token_value}"
            try:
                send_email(
                    subject="Reset your ResearchPilot password",
                    recipient=str(payload.email),
                    body=(
                        f"Reset your password by visiting: {reset_url}\n\n"
                        "If you did not request this, please ignore."
                    ),
                )
                email_sent = True
            except Exception as exc:
                logger.exception("Reset password email failed: %s", exc)
                email_sent = False
        response.headers["X-Reset-Email-Sent"] = "true" if email_sent else "false"
        if reset_url is not None and not email_sent:
            response.headers["X-Reset-URL"] = reset_url
        # Always return a generic success response
        return {"status": "ok"}
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/reset-password", status_code=200)
def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db_session: Annotated[Session | None, Depends(get_db_session)],
):
    try:
        reset_password(session=db_session, token_value=payload.token, new_password=payload.new_password)
        return {"status": "ok"}
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
