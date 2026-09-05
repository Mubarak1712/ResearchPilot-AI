from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.analysis.models import (
    PaperEvidence,
    ResearchAnalysis,
    ResearchAnalysisPaper,
    ResearchGap,
    ResearchGapSupport,
)
from app.analysis.repository import AnalysisRepository, paper_snapshot
from app.analysis.schemas import CandidateResearchGap, EvidenceCategory, EvidenceItem, GapCategory
from app.db.base import Base
from app.models.paper import Paper
from app.models.user import User
from app.models.user_saved_paper import UserSavedPaper


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


def make_paper() -> Paper:
    return Paper(
        openalex_id="https://openalex.org/W-test",
        title="Original title",
        authors=["Ada Lovelace"],
        publication_year=2026,
        abstract="Original abstract",
        doi="https://doi.org/10.1000/test",
        url="https://example.org/test",
    )


def make_evidence() -> EvidenceItem:
    return EvidenceItem(
        paper_id=1,
        evidence_type=EvidenceCategory.METHODOLOGY,
        claim="Explicit methodology signal: survey",
        source_excerpt="A survey was conducted.",
        source_field="abstract",
        confidence=0.95,
    )


def make_gap() -> CandidateResearchGap:
    return CandidateResearchGap(
        id="gap-1",
        category=GapCategory.METHODOLOGY,
        statement="Methods vary across the selected papers.",
        observed_evidence=["Survey evidence"],
        pattern="Different methods are reported.",
        inference="A methodological pattern may exist.",
        confidence=0.7,
        supporting_paper_ids=[1],
    )


def create_base_records(session):
    user_one = User(email="one@example.com", password_hash="hash")
    user_two = User(email="two@example.com", password_hash="hash")
    paper = make_paper()
    session.add_all([user_one, user_two, paper])
    session.flush()
    return user_one, user_two, paper


def test_analysis_snapshot_evidence_and_ownership(session) -> None:
    user, _, paper = create_base_records(session)
    repository = AnalysisRepository(session)
    analysis = repository.create_analysis(
        user_id=user.id, status="pending", methodology_version="deterministic-v1"
    )
    snapshot = repository.create_analysis_paper_snapshot(
        analysis_id=analysis.id, paper_id=paper.id, input_order=0, paper=paper
    )
    evidence = repository.create_evidence(analysis_paper_id=snapshot.id, item=make_evidence())
    session.commit()

    stored = repository.get_analysis(analysis_id=analysis.id, user_id=user.id)
    assert stored is not None
    assert stored.user_id == user.id
    assert session.get(PaperEvidence, evidence.id).analysis_paper_id == snapshot.id
    assert session.get(ResearchAnalysisPaper, snapshot.id).paper_snapshot["title"] == "Original title"


def test_snapshot_is_independent_of_live_paper(session) -> None:
    user, _, paper = create_base_records(session)
    repository = AnalysisRepository(session)
    analysis = repository.create_analysis(
        user_id=user.id, status="completed", methodology_version="v1"
    )
    snapshot = repository.create_analysis_paper_snapshot(
        analysis_id=analysis.id, paper_id=paper.id, input_order=0, paper=paper
    )
    paper.title = "Changed title"
    session.commit()

    assert session.get(ResearchAnalysisPaper, snapshot.id).paper_snapshot["title"] == "Original title"


def test_constraints_reject_duplicates_and_invalid_confidence(session) -> None:
    user, _, paper = create_base_records(session)
    repository = AnalysisRepository(session)
    analysis = repository.create_analysis(
        user_id=user.id, status="pending", methodology_version="v1"
    )
    analysis_paper = repository.create_analysis_paper_snapshot(
        analysis_id=analysis.id, paper_id=paper.id, input_order=0, paper=paper
    )
    session.commit()
    with pytest.raises(IntegrityError):
        repository.create_analysis_paper_snapshot(
            analysis_id=analysis.id, paper_id=paper.id, input_order=0, paper=paper
        )
    session.rollback()

    invalid = PaperEvidence(
        analysis_paper_id=analysis_paper.id,
        evidence_type="methodology",
        claim_text="invalid",
        confidence=1.1,
        extraction_method="deterministic_rule",
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_gap_support_and_cross_analysis_relationships(session) -> None:
    user, _, paper = create_base_records(session)
    repository = AnalysisRepository(session)
    first = repository.create_analysis(user_id=user.id, status="completed", methodology_version="v1")
    second = repository.create_analysis(user_id=user.id, status="completed", methodology_version="v1")
    first_paper = repository.create_analysis_paper_snapshot(
        analysis_id=first.id, paper_id=paper.id, input_order=0, paper=paper
    )
    second_paper = repository.create_analysis_paper_snapshot(
        analysis_id=second.id, paper_id=paper.id, input_order=0, paper=paper
    )
    first_evidence = repository.create_evidence(analysis_paper_id=first_paper.id, item=make_evidence())
    gap = repository.create_gap(analysis_id=first.id, gap=make_gap())
    repository.create_gap_support(
        analysis_id=first.id,
        gap_id=gap.id,
        analysis_paper_id=first_paper.id,
        evidence_id=first_evidence.id,
        support_type="observed",
    )
    session.commit()

    invalid_support = ResearchGapSupport(
        analysis_id=first.id,
        gap_id=gap.id,
        analysis_paper_id=second_paper.id,
        evidence_id=first_evidence.id,
        support_type="observed",
    )
    session.add(invalid_support)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_analysis_cascades_without_removing_saved_paper(session) -> None:
    user, _, paper = create_base_records(session)
    session.add(UserSavedPaper(user_id=user.id, paper_id=paper.id))
    repository = AnalysisRepository(session)
    analysis = repository.create_analysis(user_id=user.id, status="completed", methodology_version="v1")
    analysis_paper = repository.create_analysis_paper_snapshot(
        analysis_id=analysis.id, paper_id=paper.id, input_order=0, paper=paper
    )
    repository.create_evidence(analysis_paper_id=analysis_paper.id, item=make_evidence())
    repository.create_gap(analysis_id=analysis.id, gap=make_gap())
    session.commit()
    session.delete(analysis)
    session.commit()

    assert session.scalar(select(ResearchAnalysis).where(ResearchAnalysis.id == analysis.id)) is None
    assert session.scalar(select(ResearchAnalysisPaper).where(ResearchAnalysisPaper.analysis_id == analysis.id)) is None
    assert session.scalar(select(Paper).where(Paper.id == paper.id)) is not None
    assert session.scalar(select(UserSavedPaper).where(UserSavedPaper.user_id == user.id)) is not None


def test_snapshot_builder_explicitly_selects_supported_fields() -> None:
    source = SimpleNamespace(
        openalex_id="W1", title="Title", authors=["Author"], publication_year=2026,
        abstract="Abstract", doi="doi", url="url", citation_count=3, source_name="Journal",
        secret="must not persist",
    )

    snapshot = paper_snapshot(source)

    assert snapshot["source_name"] == "Journal"
    assert "secret" not in snapshot
