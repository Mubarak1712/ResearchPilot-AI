from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.paper import Paper
from app.models.user import User
from app.models.user_saved_paper import UserSavedPaper


class TestAnalysisApi:
    def setup_method(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        def get_test_session():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db_session] = get_test_session

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_user(self, email: str) -> User:
        session = self.session_factory()
        user = User(email=email, password_hash=hash_password("password-123"))
        session.add(user)
        session.commit()
        session.refresh(user)
        session.close()
        return user

    def create_paper(self, name: str, user: User) -> Paper:
        session = self.session_factory()
        paper = Paper(
            openalex_id=f"https://openalex.org/{name}",
            title="Robotics",
            authors=["Ada Lovelace"],
            publication_year=2026,
            abstract="A survey measures accuracy.",
            doi=None,
            url="https://example.org/paper",
        )
        session.add(paper)
        session.flush()
        session.add(UserSavedPaper(user_id=user.id, paper_id=paper.id))
        session.commit()
        session.refresh(paper)
        session.close()
        return paper

    def headers(self, user_id: int) -> dict[str, str]:
        settings = get_settings()
        with patch("app.core.security.auth.get_settings", return_value=settings):
            token = create_access_token(str(user_id))
        return {"Authorization": f"Bearer {token}"}

    def test_authenticated_creation_and_detail_endpoints(self) -> None:
        user = self.create_user("analysis-one@example.com")
        first = self.create_paper("W1", user)
        second = self.create_paper("W2", user)

        with TestClient(app) as client:
            created = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": [first.id, second.id]},
            )
            analysis_id = created.json()["analysis_id"]
            detail = client.get(f"/api/v1/analyses/{analysis_id}", headers=self.headers(user.id))
            evidence = client.get(
                f"/api/v1/analyses/{analysis_id}/evidence", headers=self.headers(user.id)
            )
            gaps = client.get(
                f"/api/v1/analyses/{analysis_id}/gaps", headers=self.headers(user.id)
            )

        assert created.status_code == 201
        assert created.json()["status"] == "completed"
        assert created.json()["paper_ids"] == [first.id, second.id]
        assert detail.status_code == 200
        assert detail.json()["papers"][0]["title"] == "Robotics"
        assert detail.json()["papers"][0]["abstract"] == "A survey measures accuracy."
        assert detail.json()["papers"][0]["openalex_id"] == first.openalex_id
        assert evidence.status_code == 200
        assert all(item["paper_id"] in [first.id, second.id] for item in evidence.json())
        assert gaps.status_code == 200
        assert all(0 <= item["confidence"] <= 1 for item in gaps.json())

    def test_current_paper_metadata_overrides_stale_analysis_snapshot(self) -> None:
        user = self.create_user("analysis-current-paper@example.com")
        paper = self.create_paper("W-current", user)
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": [paper.id]},
            )
            session = self.session_factory()
            current = session.get(Paper, paper.id)
            current.title = "Verified current title"
            current.authors = ["Current Author"]
            session.commit()
            session.close()
            detail = client.get(
                f"/api/v1/analyses/{created.json()['analysis_id']}",
                headers=self.headers(user.id),
            )
        assert detail.status_code == 200
        assert detail.json()["papers"][0]["title"] == "Verified current title"
        assert detail.json()["papers"][0]["authors"] == ["Current Author"]

    def test_optional_llm_is_unavailable_without_provider(self) -> None:
        user = self.create_user("analysis-llm@example.com")
        paper = self.create_paper("W-LLM", user)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={
                    "paper_ids": [paper.id],
                    "options": {"include_llm_interpretation": True},
                },
            )

        assert response.status_code == 201
        assert response.json()["status"] == "completed"
        assert response.json()["llm_interpretation"]["status"] == "unavailable"

    def test_unauthenticated_and_invalid_requests_are_rejected(self) -> None:
        user = self.create_user("analysis-two@example.com")
        paper = self.create_paper("W3", user)

        with TestClient(app) as client:
            assert client.post("/api/v1/analyses", json={"paper_ids": [paper.id]}).status_code == 401
            assert client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": []},
            ).status_code == 422
            assert client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": [paper.id, paper.id]},
            ).status_code == 422
            assert client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": [99999]},
            ).status_code == 404
            llm_response = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={
                    "paper_ids": [paper.id],
                    "options": {"include_llm_interpretation": True},
                },
            )
            assert llm_response.status_code == 201
            assert llm_response.json()["llm_interpretation"]["status"] == "unavailable"

    def test_corpus_limit_and_selection_ownership_are_enforced(self) -> None:
        user = self.create_user("analysis-three@example.com")
        other = self.create_user("analysis-four@example.com")
        paper = self.create_paper("W4", other)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": [paper.id]},
            )
            assert response.status_code == 404

            too_many = client.post(
                "/api/v1/analyses",
                headers=self.headers(user.id),
                json={"paper_ids": list(range(1, 22))},
            )
            assert too_many.status_code == 422

    def test_cross_user_analysis_access_does_not_leak(self) -> None:
        owner = self.create_user("analysis-five@example.com")
        other = self.create_user("analysis-six@example.com")
        paper = self.create_paper("W5", owner)

        with TestClient(app) as client:
            created = client.post(
                "/api/v1/analyses",
                headers=self.headers(owner.id),
                json={"paper_ids": [paper.id]},
            )
            analysis_id = created.json()["analysis_id"]
            for suffix in ("", "/evidence", "/gaps"):
                response = client.get(
                    f"/api/v1/analyses/{analysis_id}{suffix}",
                    headers=self.headers(other.id),
                )
                assert response.status_code == 404
