from __future__ import annotations

import logging
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    if not settings.database_configured:
        raise RuntimeError("DATABASE_URL is not configured.")

    return create_engine(
        settings.database_url,
        echo=settings.sqlalchemy_echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session | None, None, None]:
    settings = get_settings()
    if not settings.database_configured:
        logger.warning("Database persistence is disabled because DATABASE_URL is not configured.")
        yield None
        return

    try:
        session_factory = get_session_factory()
    except (ArgumentError, RuntimeError, SQLAlchemyError) as error:
        logger.error(
            "Database persistence is unavailable; continuing without persistence (%s).",
            type(error).__name__,
        )
        yield None
        return

    session = session_factory()
    try:
        yield session
    finally:
        session.close()
