from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.user_saved_paper import UserSavedPaper


class UserSavedPaperRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, user_id: int, paper_id: int) -> UserSavedPaper:
        association = UserSavedPaper(user_id=user_id, paper_id=paper_id)
        self.session.add(association)
        self.session.flush()
        return association

    def find(self, *, user_id: int, paper_id: int) -> UserSavedPaper | None:
        statement = select(UserSavedPaper).where(
            UserSavedPaper.user_id == user_id,
            UserSavedPaper.paper_id == paper_id,
        )
        return self.session.scalar(statement)

    def delete(self, *, user_id: int, paper_id: int) -> bool:
        association = self.find(user_id=user_id, paper_id=paper_id)
        if association is None:
            return False
        self.session.delete(association)
        self.session.flush()
        return True

    def list_for_user(self, *, user_id: int) -> list[UserSavedPaper]:
        statement = (
            select(UserSavedPaper)
            .where(UserSavedPaper.user_id == user_id)
            .order_by(UserSavedPaper.created_at.desc(), UserSavedPaper.id.desc())
        )
        return list(self.session.scalars(statement).all())
