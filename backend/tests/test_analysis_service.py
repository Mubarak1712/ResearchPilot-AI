from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.analysis.models import ResearchAnalysis
from app.db.base import Base
from app.models.paper import Paper
from app.models.user import User
from app.models.user_saved_paper import UserSavedPaper
from app.schemas.analysis_api import AnalysisCreateRequest
from app.services import analysis_service
from app.services.analysis_service import AnalysisServiceError


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_processing_failure_rolls_back_analysis_and_dependents(session, monkeypatch) -> None:
    user = User(email="service@example.com", password_hash="hash")
    paper = Paper(
        openalex_id="W-service",
        title="Robotics",
        authors=[],
        publication_year=2026,
        abstract="A survey.",
    )
    session.add_all([user, paper])
    session.flush()
    session.add(UserSavedPaper(user_id=user.id, paper_id=paper.id))
    session.commit()

    def fail_extraction(_papers):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(analysis_service, "extract_evidence", fail_extraction)
    with pytest.raises(AnalysisServiceError) as error:
        analysis_service.create_analysis(
            session=session,
            user=user,
            request=AnalysisCreateRequest(paper_ids=[paper.id]),
        )

    assert error.value.status_code == 500
    assert session.scalar(select(ResearchAnalysis)) is None
