from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routers.research import get_db_session
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models.auth_token import AuthToken
from app.models.user import User


class AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_auth_secret = os.environ.get("AUTH_SECRET_KEY")
        self.previous_expiration = os.environ.get("AUTH_TOKEN_EXPIRE_MINUTES")
        os.environ["AUTH_SECRET_KEY"] = "x" * 32
        os.environ["AUTH_TOKEN_EXPIRE_MINUTES"] = "30"
        get_settings.cache_clear()
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        app.dependency_overrides[get_db_session] = self._get_db_session

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        if self.previous_auth_secret is None:
            os.environ.pop("AUTH_SECRET_KEY", None)
        else:
            os.environ["AUTH_SECRET_KEY"] = self.previous_auth_secret
        if self.previous_expiration is None:
            os.environ.pop("AUTH_TOKEN_EXPIRE_MINUTES", None)
        else:
            os.environ["AUTH_TOKEN_EXPIRE_MINUTES"] = self.previous_expiration
        get_settings.cache_clear()

    def _get_db_session(self):
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def test_register_login_and_current_user(self) -> None:
        settings = SimpleNamespace(auth_secret_key="test-secret", auth_token_expire_minutes=30)
        with patch("app.core.security.auth.get_settings", return_value=settings):
            with TestClient(app) as client:
                register = client.post(
                    "/api/v1/auth/register",
                    json={"email": "Ada@example.com", "password": "correct horse battery"},
                )
                # Simulate email verification for the newly registered user so login succeeds
                session = self.SessionLocal()
                try:
                    user = session.query(User).filter(User.email == "ada@example.com").one()
                    user.is_email_verified = True
                    session.commit()
                finally:
                    session.close()

                login = client.post(
                    "/api/v1/auth/login",
                    json={"email": "ada@example.com", "password": "correct horse battery"},
                )
                token = login.json().get('access_token')
                me = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {login.json()['access_token']}"},
                )

        self.assertEqual(register.status_code, 201)
        self.assertEqual(register.json()["email"], "ada@example.com")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "ada@example.com")
        self.assertNotIn("password_hash", register.json())

        session = self.SessionLocal()
        try:
            stored = session.query(User).filter(User.email == "ada@example.com").one()
        finally:
            session.close()
        self.assertNotEqual(stored.password_hash, "correct horse battery")
        self.assertTrue(stored.password_hash.startswith("$argon2"))

    def test_duplicate_email_and_invalid_login_are_rejected(self) -> None:
        settings = SimpleNamespace(auth_secret_key="test-secret", auth_token_expire_minutes=30)
        with patch("app.core.security.auth.get_settings", return_value=settings):
            with TestClient(app) as client:
                payload = {"email": "ada@example.com", "password": "correct horse battery"}
                first = client.post("/api/v1/auth/register", json=payload)
                duplicate = client.post("/api/v1/auth/register", json=payload)
                invalid = client.post(
                    "/api/v1/auth/login",
                    json={"email": payload["email"], "password": "wrong password"},
                )
                unknown = client.post(
                    "/api/v1/auth/login",
                    json={"email": "unknown@example.com", "password": payload["password"]},
                )
                missing_auth = client.get("/api/v1/auth/me")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(missing_auth.status_code, 401)

    def test_non_bearer_authorization_scheme_is_rejected(self) -> None:
        with patch("app.core.security.auth.get_settings", return_value=self._settings()):
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Basic {create_access_token('1')}"},
                )

        self.assertEqual(response.status_code, 401)

    def test_malformed_expired_and_invalid_subject_tokens_are_rejected(self) -> None:
        settings = self._settings()
        with patch("app.core.security.auth.get_settings", return_value=settings):
            expired_token = jwt.encode(
                {
                    "sub": "1",
                    "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                    "token_type": "access",
                },
                settings.auth_secret_key,
                algorithm="HS256",
            )
            invalid_subject_token = jwt.encode(
                {"sub": "not-an-integer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "token_type": "access"},
                settings.auth_secret_key,
                algorithm="HS256",
            )
            with TestClient(app) as client:
                malformed = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
                expired = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
                invalid_subject = client.get(
                    "/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_subject_token}"}
                )

        self.assertEqual(malformed.status_code, 401)
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(invalid_subject.status_code, 401)

    def test_malformed_stored_password_hash_fails_as_invalid_login(self) -> None:
        session = self.SessionLocal()
        try:
            session.add(User(email="broken@example.com", password_hash="not-a-valid-hash"))
            session.commit()
        finally:
            session.close()

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "broken@example.com", "password": "correct horse battery"},
            )

        self.assertEqual(response.status_code, 401)

    def test_token_without_access_claim_is_rejected(self) -> None:
        settings = self._settings()
        with patch("app.core.security.auth.get_settings", return_value=settings):
            token = jwt.encode(
                {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                settings.auth_secret_key,
                algorithm="HS256",
            )
            with TestClient(app) as client:
                response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)

    def test_invalid_token_expiration_configuration_is_rejected(self) -> None:
        for value in (None, "", "invalid", "0", "-1"):
            with patch.dict(os.environ, {"AUTH_SECRET_KEY": "x" * 32}, clear=False):
                if value is None:
                    os.environ.pop("AUTH_TOKEN_EXPIRE_MINUTES", None)
                else:
                    os.environ["AUTH_TOKEN_EXPIRE_MINUTES"] = value
                get_settings.cache_clear()
                with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_EXPIRE_MINUTES"):
                    get_settings()
        os.environ["AUTH_TOKEN_EXPIRE_MINUTES"] = "30"
        get_settings.cache_clear()

    def test_register_verify_login_flow(self) -> None:
        settings = SimpleNamespace(auth_secret_key="test-secret", auth_token_expire_minutes=30)
        with patch("app.core.security.auth.get_settings", return_value=settings):
            with TestClient(app) as client:
                # Register a new user
                register = client.post(
                    "/api/v1/auth/register",
                    json={"email": "flow@example.com", "password": "sufficient-password"},
                )
                self.assertEqual(register.status_code, 201)

                # Find the verification token in the DB
                session = self.SessionLocal()
                try:
                    user = session.query(User).filter(User.email == "flow@example.com").one()
                    from app.models.auth_token import AuthToken
                    token = session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.token_type == "verification").one()
                    token_value = token.token
                finally:
                    session.close()

                # Verify via the API
                verify = client.post("/api/v1/auth/verify-email", json={"token": token_value})
                self.assertEqual(verify.status_code, 200)

                # Now login should succeed
                login = client.post(
                    "/api/v1/auth/login",
                    json={"email": "flow@example.com", "password": "sufficient-password"},
                )
                self.assertEqual(login.status_code, 200)
                access_token = login.json().get("access_token")
                self.assertIsNotNone(access_token)

                # /me should accept the Bearer token
                me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json().get("email"), "flow@example.com")

    def test_reset_password_flow_is_single_use_and_updates_login(self) -> None:
                settings = self._settings()
                with patch("app.core.security.auth.get_settings", return_value=settings):
                    with TestClient(app) as client:
                        register = client.post(
                            "/api/v1/auth/register",
                            json={"email": "reset-flow@example.com", "password": "OldPass123!"},
                        )
                        self.assertEqual(register.status_code, 201)

                        session = self.SessionLocal()
                        try:
                            user = session.query(User).filter(User.email == "reset-flow@example.com").one()
                            user.is_email_verified = True
                            token = AuthToken(
                                token="reset-flow-token-123",
                                user_id=user.id,
                                token_type="password_reset",
                                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                            )
                            session.add(token)
                            session.commit()
                        finally:
                            session.close()

                        reset = client.post(
                            "/api/v1/auth/reset-password",
                            json={"token": "reset-flow-token-123", "new_password": "NewPass456!"},
                        )
                        self.assertEqual(reset.status_code, 200)

                        login = client.post(
                            "/api/v1/auth/login",
                            json={"email": "reset-flow@example.com", "password": "NewPass456!"},
                        )
                        self.assertEqual(login.status_code, 200)

                        replay = client.post(
                            "/api/v1/auth/reset-password",
                            json={"token": "reset-flow-token-123", "new_password": "NeverUsed123!"},
                        )
                        self.assertEqual(replay.status_code, 400)

                        old_password_login = client.post(
                            "/api/v1/auth/login",
                            json={"email": "reset-flow@example.com", "password": "OldPass123!"},
                        )
                        self.assertEqual(old_password_login.status_code, 401)

    @staticmethod
    def _settings() -> SimpleNamespace:
        return SimpleNamespace(auth_secret_key="x" * 32, auth_token_expire_minutes=30)
