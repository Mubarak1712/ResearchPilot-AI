from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.models.paper import Paper


class PaperRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_openalex_id(self, openalex_id: str) -> Paper | None:
        statement = select(Paper).where(Paper.openalex_id == openalex_id)
        return self.session.scalar(statement)

    def find_by_id_or_openalex_id(self, identifier: str) -> Paper | None:
        statement = select(Paper).where(
            (Paper.openalex_id == identifier)
            | (Paper.id == int(identifier) if identifier.isdigit() else False)
        )
        return self.session.scalar(statement)

    def list_papers(
        self, limit: int = 100, offset: int = 0, *, saved_only: bool = False
    ) -> list[Paper]:
        statement = select(Paper)
        if saved_only:
            statement = statement.where(Paper.is_saved.is_(True))
        statement = statement.order_by(Paper.created_at.desc(), Paper.id.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def list_papers_page(self, *, limit: int, offset: int) -> tuple[list[Paper], int]:
        total = self.session.scalar(
            select(func.count()).select_from(Paper).where(Paper.is_saved.is_(True))
        ) or 0
        return self.list_papers(limit=limit, offset=offset, saved_only=True), total

    def save_paper(self, openalex_id: str) -> Paper | None:
        paper = self.find_by_openalex_id(openalex_id)
        if paper is None:
            return None
        paper.is_saved = True
        return paper

    def unsave_paper(self, openalex_id: str) -> Paper | None:
        paper = self.find_by_openalex_id(openalex_id)
        if paper is None:
            return None
        paper.is_saved = False
        return paper

    def create_paper(self, paper: Paper) -> Paper:
        self.session.add(paper)
        return paper

    def upsert_paper(
        self,
        *,
        openalex_id: str,
        title: str,
        authors: list[str],
        publication_year: int | None,
        abstract: str | None,
        doi: str | None,
        url: str | None,
    ) -> Paper:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            return self._upsert_postgresql(
                openalex_id=openalex_id,
                title=title,
                authors=authors,
                publication_year=publication_year,
                abstract=abstract,
                doi=doi,
                url=url,
            )

        paper = self.find_by_openalex_id(openalex_id)
        if paper is None:
            paper = Paper(
                openalex_id=openalex_id,
                title=title,
                authors=authors,
                publication_year=publication_year,
                abstract=abstract,
                doi=doi,
                url=url,
            )
            self.session.add(paper)
            return paper

        paper.title = title
        paper.authors = authors
        paper.publication_year = publication_year
        paper.abstract = abstract
        paper.doi = doi
        paper.url = url
        return paper

    def _upsert_postgresql(
        self,
        *,
        openalex_id: str,
        title: str,
        authors: list[str],
        publication_year: int | None,
        abstract: str | None,
        doi: str | None,
        url: str | None,
    ) -> Paper:
        values = {
            "openalex_id": openalex_id,
            "title": title,
            "authors": authors,
            "publication_year": publication_year,
            "abstract": abstract,
            "doi": doi,
            "url": url,
        }
        insert_statement = postgresql_insert(Paper).values(**values)
        statement = insert_statement.on_conflict_do_update(
            index_elements=[Paper.openalex_id],
            set_={
                "title": insert_statement.excluded.title,
                "authors": insert_statement.excluded.authors,
                "publication_year": insert_statement.excluded.publication_year,
                "abstract": insert_statement.excluded.abstract,
                "doi": insert_statement.excluded.doi,
                "url": insert_statement.excluded.url,
                "updated_at": func.now(),
            },
        ).returning(Paper)
        return self.session.execute(
            statement.execution_options(populate_existing=True)
        ).scalar_one()
