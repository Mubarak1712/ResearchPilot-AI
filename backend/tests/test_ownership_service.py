import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.paper import Paper
from app.models.user import User
from app.services.ownership_service import (
    OwnershipServiceError,
    is_paper_saved_for_user,
    list_papers_saved_by_user,
    save_paper_for_user,
    unsave_paper_for_user,
)


class OwnershipServiceTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, session, email: str) -> User:
        user = User(email=email, password_hash="stored-hash")
        session.add(user)
        session.flush()
        return user

    def _paper(self, session, name: str) -> Paper:
        paper = Paper(openalex_id=f"https://openalex.org/{name}", title=name, authors=[])
        session.add(paper)
        session.flush()
        return paper

    def test_user_can_save_and_unsave_a_paper_without_changing_canonical_paper(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._user(session, "one@example.com")
            paper = self._paper(session, "W1")
            association = save_paper_for_user(session=session, user=user, paper_id=paper.id)

            self.assertTrue(is_paper_saved_for_user(session=session, user=user, paper_id=paper.id))
            self.assertEqual(association.paper_id, paper.id)
            self.assertTrue(unsave_paper_for_user(session=session, user=user, paper_id=paper.id))
            self.assertFalse(is_paper_saved_for_user(session=session, user=user, paper_id=paper.id))
            stored = session.get(Paper, paper.id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.title, "W1")
            self.assertFalse(stored.is_saved)
        finally:
            session.close()

    def test_repeated_save_is_idempotent(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._user(session, "one@example.com")
            paper = self._paper(session, "W1")
            first = save_paper_for_user(session=session, user=user, paper_id=paper.id)
            second = save_paper_for_user(session=session, user=user, paper_id=paper.id)
            self.assertEqual(first.id, second.id)
            self.assertEqual(len(list_papers_saved_by_user(session=session, user=user)), 1)
        finally:
            session.close()

    def test_user_cannot_unsave_another_users_relationship(self) -> None:
        session = self.SessionLocal()
        try:
            first_user = self._user(session, "one@example.com")
            second_user = self._user(session, "two@example.com")
            paper = self._paper(session, "W1")
            save_paper_for_user(session=session, user=second_user, paper_id=paper.id)
            self.assertFalse(unsave_paper_for_user(session=session, user=first_user, paper_id=paper.id))
            self.assertTrue(is_paper_saved_for_user(session=session, user=second_user, paper_id=paper.id))
        finally:
            session.close()

    def test_saved_lists_are_user_scoped_and_same_paper_can_be_saved_independently(self) -> None:
        session = self.SessionLocal()
        try:
            first_user = self._user(session, "one@example.com")
            second_user = self._user(session, "two@example.com")
            first_paper = self._paper(session, "W1")
            second_paper = self._paper(session, "W2")
            save_paper_for_user(session=session, user=first_user, paper_id=first_paper.id)
            save_paper_for_user(session=session, user=second_user, paper_id=first_paper.id)
            save_paper_for_user(session=session, user=first_user, paper_id=second_paper.id)

            self.assertEqual({paper.id for paper in list_papers_saved_by_user(session=session, user=first_user)}, {first_paper.id, second_paper.id})
            self.assertEqual({paper.id for paper in list_papers_saved_by_user(session=session, user=second_user)}, {first_paper.id})
        finally:
            session.close()

    def test_missing_user_and_paper_follow_service_conventions(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._user(session, "one@example.com")
            missing_user = User(id=999, email="missing@example.com", password_hash="stored-hash")
            with self.assertRaisesRegex(OwnershipServiceError, "User was not found"):
                save_paper_for_user(session=session, user=missing_user, paper_id=999)
            with self.assertRaisesRegex(OwnershipServiceError, "Paper was not found"):
                save_paper_for_user(session=session, user=user, paper_id=999)
            self.assertEqual(OwnershipServiceError, type(OwnershipServiceError("x", 404)))
        finally:
            session.close()
