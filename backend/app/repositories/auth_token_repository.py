from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken


class AuthTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, token: AuthToken) -> AuthToken:
        self.session.add(token)
        self.session.flush()
        return token

    def find_by_token(self, token_value: str) -> AuthToken | None:
        return self.session.scalar(select(AuthToken).where(AuthToken.token == token_value))

    def mark_used(self, token: AuthToken) -> None:
        token.used = True
        self.session.add(token)

    def delete_expired(self, now: datetime) -> None:
        self.session.execute(delete(AuthToken).where(AuthToken.expires_at < now))
