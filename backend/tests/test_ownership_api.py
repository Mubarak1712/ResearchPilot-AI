import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models.paper import Paper
from app.models.user import User


class OwnershipApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        self.override_database()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def override_database(self) -> None:
        from app.api.v1.routers.research import get_db_session

        def get_test_session():
            session = self.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db_session] = get_test_session

    def _create_user(self, email: str) -> User:
        session = self.SessionLocal()
        try:
            user = User(email=email, password_hash=hash_password("password-123"))
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        finally:
            session.close()

    def _create_paper(self, name: str) -> Paper:
        session = self.SessionLocal()
        try:
            paper = Paper(
                openalex_id=f"https://openalex.org/{name}",
                title=f"Paper {name}",
                authors=["Ada Lovelace"],
                publication_year=2026,
                abstract="Canonical abstract",
                doi="https://doi.org/example",
                url="https://example.org/paper",
            )
            session.add(paper)
            session.commit()
            session.refresh(paper)
            return paper
        finally:
            session.close()

    def _headers(self, user_id: int) -> dict[str, str]:
        settings = get_settings()
        with patch("app.core.security.auth.get_settings", return_value=settings):
            token = create_access_token(str(user_id))
        return {"Authorization": f"Bearer {token}"}

    def test_authenticated_user_can_save_check_unsave_and_list_canonical_paper(self) -> None:
        user = self._create_user("one@example.com")
        paper = self._create_paper("W1")
        with TestClient(app) as client:
            save = client.post(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(user.id))
            repeated = client.post(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(user.id))
            check = client.get(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(user.id))
            listed = client.get("/api/v1/ownership/papers", headers=self._headers(user.id))
            unsave = client.delete(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(user.id))

        self.assertEqual(save.status_code, 201)
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(save.json()["paper_id"], paper.id)
        self.assertEqual(check.json(), {"paper_id": paper.id, "is_saved": True})
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["openalex_id"], paper.openalex_id)
        self.assertEqual(listed.json()[0]["title"], paper.title)
        self.assertEqual(unsave.json(), {"paper_id": paper.id, "is_saved": False})

        session = self.SessionLocal()
        try:
            self.assertIsNotNone(session.get(Paper, paper.id))
            self.assertEqual(session.query(User).count(), 1)
        finally:
            session.close()

    def test_unauthenticated_requests_are_rejected(self) -> None:
        paper = self._create_paper("W1")
        with TestClient(app) as client:
            response = client.get(f"/api/v1/ownership/papers/{paper.id}")
        self.assertEqual(response.status_code, 401)

    def test_users_cannot_see_or_manipulate_each_others_relationships(self) -> None:
        first_user = self._create_user("one@example.com")
        second_user = self._create_user("two@example.com")
        paper = self._create_paper("W1")
        with TestClient(app) as client:
            saved = client.post(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(second_user.id))
            first_list = client.get("/api/v1/ownership/papers", headers=self._headers(first_user.id))
            first_check = client.get(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(first_user.id))
            first_delete = client.delete(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(first_user.id))
            second_check = client.get(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(second_user.id))

        self.assertEqual(saved.status_code, 201)
        self.assertEqual(first_list.json(), [])
        self.assertEqual(first_check.json(), {"paper_id": paper.id, "is_saved": False})
        self.assertEqual(first_delete.json(), {"paper_id": paper.id, "is_saved": False})
        self.assertEqual(second_check.json(), {"paper_id": paper.id, "is_saved": True})

    def test_user_id_cannot_override_authenticated_identity(self) -> None:
        first_user = self._create_user("one@example.com")
        second_user = self._create_user("two@example.com")
        paper = self._create_paper("W1")
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/ownership/papers/{paper.id}?user_id={second_user.id}",
                headers=self._headers(first_user.id),
                json={"user_id": second_user.id},
            )
            first_check = client.get(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(first_user.id))
            second_check = client.get(f"/api/v1/ownership/papers/{paper.id}", headers=self._headers(second_user.id))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(first_check.json(), {"paper_id": paper.id, "is_saved": True})
        self.assertEqual(second_check.json(), {"paper_id": paper.id, "is_saved": False})

    def test_missing_paper_returns_not_found(self) -> None:
        user = self._create_user("one@example.com")
        with TestClient(app) as client:
            response = client.post("/api/v1/ownership/papers/999", headers=self._headers(user.id))
        self.assertEqual(response.status_code, 404)
