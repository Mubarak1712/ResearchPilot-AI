from datetime import datetime, timedelta, timezone
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routers.research import get_db_session
from app.db.base import Base
from app.main import app
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.research_service import SavedPaperServiceError, list_saved_papers


class SavedPaperTests(unittest.TestCase):
    def setUp(self) -> None:
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

    def _get_db_session(self):
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def _insert_papers(self, count: int) -> None:
        session = self.SessionLocal()
        base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        try:
            for index in range(count):
                session.add(
                    Paper(
                        openalex_id=f"https://openalex.org/saved-paper-{index}",
                        title=f"Saved paper {index}",
                        authors=["Ada Lovelace"],
                        publication_year=2026,
                        abstract=f"Abstract {index}",
                        doi=None,
                        url=f"https://example.org/saved-paper-{index}",
                        is_saved=True,
                        created_at=base_time + timedelta(minutes=index),
                        updated_at=base_time + timedelta(minutes=index),
                    )
                )
            session.commit()
        finally:
            session.close()

    def test_first_page_returns_newest_papers(self) -> None:
        self._insert_papers(3)

        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers?page=1&limit=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 3)
        self.assertEqual(response.json()["pages"], 2)
        self.assertEqual(response.json()["page"], 1)
        self.assertEqual(response.json()["limit"], 2)
        self.assertEqual(
            [paper["title"] for paper in response.json()["items"]],
            ["Saved paper 2", "Saved paper 1"],
        )

    def test_pagination_returns_the_correct_subset(self) -> None:
        self._insert_papers(3)

        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers?page=2&limit=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 3)
        self.assertEqual([paper["title"] for paper in response.json()["items"]], ["Saved paper 0"])

    def test_empty_database_returns_empty_items(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "page": 1, "limit": 20, "total": 0, "pages": 0})

    def test_invalid_page_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers?page=0")

        self.assertEqual(response.status_code, 422)

    def test_invalid_limit_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers?limit=0")

        self.assertEqual(response.status_code, 422)

    def test_limit_above_100_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/papers?limit=101")

        self.assertEqual(response.status_code, 422)

    def test_repository_returns_deterministic_paginated_results(self) -> None:
        self._insert_papers(3)
        session: Session = self.SessionLocal()
        try:
            papers, total = PaperRepository(session).list_papers_page(limit=2, offset=1)
        finally:
            session.close()

        self.assertEqual(total, 3)
        self.assertEqual([paper.title for paper in papers], ["Saved paper 1", "Saved paper 0"])

    def test_service_returns_page_metadata_and_saved_papers(self) -> None:
        self._insert_papers(3)
        session: Session = self.SessionLocal()
        try:
            response = list_saved_papers(session=session, page=2, limit=2)
        finally:
            session.close()

        self.assertEqual(response.page, 2)
        self.assertEqual(response.limit, 2)
        self.assertEqual(response.total, 3)
        self.assertEqual(response.pages, 2)
        self.assertEqual([paper.title for paper in response.items], ["Saved paper 0"])

    def test_service_rejects_missing_database_session(self) -> None:
        with self.assertRaisesRegex(SavedPaperServiceError, "database is not configured"):
            list_saved_papers(session=None, page=1, limit=20)

    def test_paper_can_be_explicitly_saved(self) -> None:
        openalex_id = "https://openalex.org/unsaved-paper"
        session = self.SessionLocal()
        try:
            session.add(
                Paper(
                    openalex_id=openalex_id,
                    title="Unsaved paper",
                    authors=["Ada Lovelace"],
                    publication_year=2026,
                )
            )
            session.commit()
        finally:
            session.close()

        with TestClient(app) as client:
            before_save = client.get("/api/v1/research/papers")
            response = client.post(f"/api/v1/research/papers/{openalex_id}/save")
            after_save = client.get("/api/v1/research/papers")

        self.assertEqual(before_save.json()["total"], 0)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_saved"])
        self.assertEqual(after_save.json()["total"], 1)
        self.assertEqual(after_save.json()["items"][0]["openalex_id"], openalex_id)

    def test_save_unsave_save_keeps_one_paper_row(self) -> None:
        openalex_id = "https://openalex.org/save-unsave-paper"
        session = self.SessionLocal()
        try:
            session.add(
                Paper(
                    openalex_id=openalex_id,
                    title="Save lifecycle paper",
                    authors=["Ada Lovelace"],
                    publication_year=2026,
                )
            )
            session.commit()
        finally:
            session.close()

        with TestClient(app) as client:
            save_response = client.post(f"/api/v1/research/papers/{openalex_id}/save")
            unsave_response = client.delete(f"/api/v1/research/papers/{openalex_id}/save")
            saved_library = client.get("/api/v1/research/papers")
            save_again_response = client.post(f"/api/v1/research/papers/{openalex_id}/save")

        session = self.SessionLocal()
        try:
            stored = session.query(Paper).filter(Paper.openalex_id == openalex_id).all()
        finally:
            session.close()

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(unsave_response.status_code, 200)
        self.assertFalse(unsave_response.json()["is_saved"])
        self.assertEqual(saved_library.json()["total"], 0)
        self.assertEqual(save_again_response.status_code, 200)
        self.assertTrue(save_again_response.json()["is_saved"])
        self.assertEqual(len(stored), 1)
