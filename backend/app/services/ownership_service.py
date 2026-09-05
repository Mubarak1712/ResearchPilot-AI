from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.user import User
from app.models.user_saved_paper import UserSavedPaper
from app.repositories.user_saved_paper_repository import UserSavedPaperRepository


class OwnershipServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def save_paper_for_user(
    *, session: Session | None, user: User, paper_id: int
) -> UserSavedPaper:
    repository = _get_repository(session, user)
    paper = _get_paper(session, paper_id)
    existing = repository.find(user_id=user.id, paper_id=paper.id)
    if existing is not None:
        return existing

    try:
        association = repository.create(user_id=user.id, paper_id=paper.id)
        session.commit()
        session.refresh(association)
        return association
    except IntegrityError:
        session.rollback()
        existing = repository.find(user_id=user.id, paper_id=paper.id)
        if existing is not None:
            return existing
        raise OwnershipServiceError("Paper could not be saved for this user.", 503) from None
    except SQLAlchemyError as error:
        session.rollback()
        raise OwnershipServiceError("Paper could not be saved for this user.", 503) from error


def unsave_paper_for_user(
    *, session: Session | None, user: User, paper_id: int
) -> bool:
    repository = _get_repository(session, user)
    _get_paper(session, paper_id)

    try:
        deleted = repository.delete(user_id=user.id, paper_id=paper_id)
        session.commit()
        return deleted
    except SQLAlchemyError as error:
        session.rollback()
        raise OwnershipServiceError("Paper could not be unsaved for this user.", 503) from error


def is_paper_saved_for_user(
    *, session: Session | None, user: User, paper_id: int
) -> bool:
    repository = _get_repository(session, user)
    _get_paper(session, paper_id)
    return repository.find(user_id=user.id, paper_id=paper_id) is not None


def list_papers_saved_by_user(*, session: Session | None, user: User) -> list[Paper]:
    repository = _get_repository(session, user)
    papers = []
    for association in repository.list_for_user(user_id=user.id):
        paper = session.get(Paper, association.paper_id)
        if paper is not None:
            papers.append(paper)
    return papers


def _get_repository(session: Session | None, user: User) -> UserSavedPaperRepository:
    if session is None:
        raise OwnershipServiceError(
            "Ownership is unavailable because the database is not configured.", 503
        )

    stored_user = session.get(User, user.id)
    if stored_user is None:
        raise OwnershipServiceError("User was not found.", 404)
    if not stored_user.is_active:
        raise OwnershipServiceError("User account is unavailable.", 401)
    return UserSavedPaperRepository(session)


def _get_paper(session: Session | None, paper_id: int) -> Paper:
    if session is None:
        raise OwnershipServiceError(
            "Ownership is unavailable because the database is not configured.", 503
        )

    paper = session.get(Paper, paper_id)
    if paper is None:
        raise OwnershipServiceError("Paper was not found.", 404)
    return paper
