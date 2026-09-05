import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository


DATABASE_URL = os.getenv("TEST_DATABASE_URL") or get_settings().database_url


@unittest.skipUnless(
    DATABASE_URL,
    "PostgreSQL integration test requires TEST_DATABASE_URL or DATABASE_URL.",
)
class PostgreSQLPaperPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
            if cls.engine.dialect.name != "postgresql":
                raise unittest.SkipTest("Integration test requires a PostgreSQL database URL.")
            with cls.engine.connect() as connection:
                connection.execute(select(1))
                if not inspect(connection).has_table("papers"):
                    raise unittest.SkipTest("PostgreSQL papers table is not available.")
        except unittest.SkipTest:
            raise
        except SQLAlchemyError as error:
            raise unittest.SkipTest(
                f"PostgreSQL is unavailable ({type(error).__name__})."
            ) from error

        cls.SessionLocal = sessionmaker(
            bind=cls.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def test_upsert_persists_without_duplicates(self) -> None:
        session = self.SessionLocal()
        repository = PaperRepository(session)
        openalex_id = f"https://openalex.org/phase7a-{uuid4()}"

        try:
            repository.upsert_paper(
                openalex_id=openalex_id,
                title="Initial integration paper",
                authors=["Ada Lovelace"],
                publication_year=2026,
                abstract="Initial abstract",
                doi="https://doi.org/10.1000/phase7a",
                url="https://example.org/phase7a",
            )
            session.commit()

            repository.upsert_paper(
                openalex_id=openalex_id,
                title="Updated integration paper",
                authors=["Ada Lovelace", "Grace Hopper"],
                publication_year=2026,
                abstract="Updated abstract",
                doi="https://doi.org/10.1000/phase7a",
                url="https://example.org/phase7a-updated",
            )
            session.commit()

            stored = repository.find_by_openalex_id(openalex_id)
            count = session.scalar(
                select(func.count()).select_from(Paper).where(Paper.openalex_id == openalex_id)
            )

            self.assertIsNotNone(stored)
            self.assertEqual(stored.title, "Updated integration paper")
            self.assertEqual(stored.authors, ["Ada Lovelace", "Grace Hopper"])
            self.assertEqual(count, 1)
        finally:
            session.rollback()
            session.execute(delete(Paper).where(Paper.openalex_id == openalex_id))
            session.commit()
            session.close()

    def test_list_papers_page_returns_deterministic_paginated_results(self) -> None:
        session = self.SessionLocal()
        repository = PaperRepository(session)
        openalex_ids = [f"https://openalex.org/phase7b-{uuid4()}" for _ in range(3)]
        existing_total = session.scalar(
            select(func.count()).select_from(Paper).where(Paper.is_saved.is_(True))
        ) or 0
        created_at = datetime(9999, 1, 1, tzinfo=timezone.utc)

        try:
            for index, openalex_id in enumerate(openalex_ids):
                repository.create_paper(
                    Paper(
                        openalex_id=openalex_id,
                        title=f"Phase 7B paper {index}",
                        authors=["Ada Lovelace"],
                        publication_year=2026,
                        is_saved=True,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
            session.commit()

            papers, total = repository.list_papers_page(limit=2, offset=1)

            self.assertEqual(total, existing_total + 3)
            self.assertEqual(len(papers), 2)
            self.assertEqual(
                [paper.title for paper in papers],
                ["Phase 7B paper 1", "Phase 7B paper 0"],
            )
        finally:
            session.rollback()
            session.execute(delete(Paper).where(Paper.openalex_id.in_(openalex_ids)))
            session.commit()
            session.close()
