import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.paper import Paper
from app.models.user import User
from app.repositories.user_saved_paper_repository import UserSavedPaperRepository


class UserSavedPaperRepositoryTests(unittest.TestCase):
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

    def _create_user(self, session, email: str) -> User:
        user = User(email=email, password_hash="stored-hash")
        session.add(user)
        session.flush()
        return user

    def _create_paper(self, session, openalex_id: str) -> Paper:
        paper = Paper(openalex_id=openalex_id, title=openalex_id, authors=[])
        session.add(paper)
        session.flush()
        return paper

    def test_user_can_be_associated_with_a_paper(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._create_user(session, "one@example.com")
            paper = self._create_paper(session, "https://openalex.org/W1")
            association = UserSavedPaperRepository(session).create(user_id=user.id, paper_id=paper.id)
            session.commit()

            self.assertEqual(association.user_id, user.id)
            self.assertEqual(association.paper_id, paper.id)
            self.assertIsNotNone(UserSavedPaperRepository(session).find(user_id=user.id, paper_id=paper.id))
        finally:
            session.close()

    def test_same_user_cannot_associate_same_paper_twice(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._create_user(session, "one@example.com")
            paper = self._create_paper(session, "https://openalex.org/W1")
            repository = UserSavedPaperRepository(session)
            repository.create(user_id=user.id, paper_id=paper.id)
            with self.assertRaises(IntegrityError):
                repository.create(user_id=user.id, paper_id=paper.id)
            session.rollback()
        finally:
            session.close()

    def test_different_users_can_associate_with_same_paper(self) -> None:
        session = self.SessionLocal()
        try:
            first_user = self._create_user(session, "one@example.com")
            second_user = self._create_user(session, "two@example.com")
            paper = self._create_paper(session, "https://openalex.org/W1")
            repository = UserSavedPaperRepository(session)
            repository.create(user_id=first_user.id, paper_id=paper.id)
            repository.create(user_id=second_user.id, paper_id=paper.id)
            session.commit()

            self.assertEqual(len(repository.list_for_user(user_id=first_user.id)), 1)
            self.assertEqual(len(repository.list_for_user(user_id=second_user.id)), 1)
        finally:
            session.close()

    def test_user_can_have_multiple_distinct_saved_papers(self) -> None:
        session = self.SessionLocal()
        try:
            user = self._create_user(session, "one@example.com")
            first_paper = self._create_paper(session, "https://openalex.org/W1")
            second_paper = self._create_paper(session, "https://openalex.org/W2")
            repository = UserSavedPaperRepository(session)
            repository.create(user_id=user.id, paper_id=first_paper.id)
            repository.create(user_id=user.id, paper_id=second_paper.id)
            session.commit()

            self.assertEqual({item.paper_id for item in repository.list_for_user(user_id=user.id)}, {first_paper.id, second_paper.id})
        finally:
            session.close()

    def test_relationships_remain_distinct_and_delete_preserves_parents(self) -> None:
        session = self.SessionLocal()
        try:
            first_user = self._create_user(session, "one@example.com")
            second_user = self._create_user(session, "two@example.com")
            paper = self._create_paper(session, "https://openalex.org/W1")
            repository = UserSavedPaperRepository(session)
            repository.create(user_id=first_user.id, paper_id=paper.id)
            repository.create(user_id=second_user.id, paper_id=paper.id)
            session.commit()

            self.assertTrue(repository.delete(user_id=first_user.id, paper_id=paper.id))
            session.commit()
            self.assertEqual(repository.list_for_user(user_id=first_user.id), [])
            self.assertEqual(len(repository.list_for_user(user_id=second_user.id)), 1)
            self.assertIsNotNone(session.get(User, first_user.id))
            self.assertIsNotNone(session.get(Paper, paper.id))
        finally:
            session.close()

    def test_foreign_keys_are_enforced(self) -> None:
        session = self.SessionLocal()
        try:
            repository = UserSavedPaperRepository(session)
            with self.assertRaises(IntegrityError):
                repository.create(user_id=999, paper_id=999)
            session.rollback()
        finally:
            session.close()
