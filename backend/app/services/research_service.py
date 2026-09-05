from typing import Any

import httpx
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.paper_repository import PaperRepository
from app.schemas.research import (
    ResearchResult,
    ResearchSearchResponse,
    SavedPaper,
    SavedPaperListResponse,
    SortOption,
)


logger = logging.getLogger(__name__)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_RESULT_LIMIT = 10
OPENALEX_SORTS: dict[SortOption, str] = {
    "relevance": "relevance_score:desc",
    "cited": "cited_by_count:desc",
    "newest": "publication_date:desc",
    "oldest": "publication_date:asc",
}


class ResearchServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SavedPaperServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SavePaperServiceError(Exception):
    def __init__(self, message: str, status_code: int = 404) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_persisted_paper(*, session: Session | None, identifier: str) -> SavedPaper:
    if session is None:
        raise SavedPaperServiceError("Paper details are unavailable because the database is not configured.")
    try:
        paper = PaperRepository(session).find_by_id_or_openalex_id(identifier)
    except (SQLAlchemyError, ValueError) as error:
        session.rollback()
        logger.exception("Paper detail lookup failed.")
        raise SavedPaperServiceError("Paper details are temporarily unavailable.") from error
    if paper is None:
        raise SavedPaperServiceError("Paper was not found.", 404)
    return SavedPaper.model_validate(paper)


async def search_research_papers(
    query: str,
    *,
    page: int = 1,
    sort: SortOption = "relevance",
    from_year: int | None = None,
    to_year: int | None = None,
    open_access: bool = False,
    has_doi: bool = False,
    client: httpx.AsyncClient | None = None,
    session: Session | None = None,
) -> ResearchSearchResponse:
    """Retrieve and normalize up to ten relevant works from OpenAlex."""
    params = {
        "search": query,
        "page": page,
        "per-page": DEFAULT_RESULT_LIMIT,
        "sort": OPENALEX_SORTS[sort],
    }
    filters = []
    if from_year is not None:
        filters.append(f"from_publication_date:{from_year}-01-01")
    if to_year is not None:
        filters.append(f"to_publication_date:{to_year}-12-31")
    if open_access:
        filters.append("is_oa:true")
    if has_doi:
        filters.append("has_doi:true")
    if filters:
        params["filter"] = ",".join(filters)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as api_client:
                response = await api_client.get(OPENALEX_WORKS_URL, params=params)
        else:
            response = await client.get(OPENALEX_WORKS_URL, params=params)
        response.raise_for_status()
    except httpx.TimeoutException as error:
        logger.warning("OpenAlex request timed out after %.1f seconds.", REQUEST_TIMEOUT_SECONDS)
        raise ResearchServiceError("Research provider timed out.", status_code=504) from error
    except httpx.HTTPStatusError as error:
        logger.warning("OpenAlex request returned HTTP status %s.", error.response.status_code)
        raise ResearchServiceError("Research provider request failed.") from error
    except httpx.RequestError as error:
        logger.warning("OpenAlex request failed due to %s.", type(error).__name__)
        raise ResearchServiceError("Research provider request failed.") from error

    try:
        payload = response.json()
    except ValueError as error:
        logger.warning("OpenAlex response could not be decoded as JSON.")
        raise ResearchServiceError("Research provider returned an invalid response.") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        logger.warning("OpenAlex response did not contain a results list.")
        raise ResearchServiceError("Research provider returned a malformed response.")

    results = [
        _normalize_work(work)
        for work in payload["results"]
        if isinstance(work, dict)
    ]

    if session is not None:
        try:
            _persist_research_papers(session, results)
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Paper persistence failed; the transaction was rolled back.")

    return ResearchSearchResponse(
        query=query,
        total=_provider_total(payload.get("meta"), fallback=len(results)),
        results=results,
        page=page,
        limit=DEFAULT_RESULT_LIMIT,
        sort=sort,
    )


def _normalize_work(work: dict[str, Any]) -> ResearchResult:
    primary_location = work.get("primary_location")
    landing_page_url = (
        primary_location.get("landing_page_url")
        if isinstance(primary_location, dict)
        else None
    )
    source_name = (
        primary_location.get("source", {}).get("display_name")
        if isinstance(primary_location, dict)
        and isinstance(primary_location.get("source"), dict)
        else None
    )

    return ResearchResult(
        id=str(work.get("id") or ""),
        title=str(work.get("title") or ""),
        authors=_extract_authors(work.get("authorships")),
        publication_year=_as_year(work.get("publication_year")),
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        doi=_as_optional_string(work.get("doi")),
        url=_as_optional_string(landing_page_url)
        or _as_optional_string(work.get("doi"))
        or _as_optional_string(work.get("id")),
        publication_date=_as_optional_string(work.get("publication_date")),
        citation_count=_as_optional_int(work.get("cited_by_count")),
        source_name=_as_optional_string(source_name),
    )


def _extract_authors(authorships: Any) -> list[str]:
    if not isinstance(authorships, list):
        return []

    authors: list[str] = []
    for authorship in authorships:
        if not isinstance(authorship, dict) or not isinstance(authorship.get("author"), dict):
            continue
        name = _as_optional_string(authorship["author"].get("display_name"))
        if name:
            authors.append(name)
    return authors


def _reconstruct_abstract(inverted_index: Any) -> str | None:
    if not isinstance(inverted_index, dict):
        return None

    tokens_by_position: dict[int, str] = {}
    for token, positions in inverted_index.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int) and position >= 0:
                tokens_by_position[position] = token

    if not tokens_by_position:
        return None
    return " ".join(tokens_by_position[position] for position in sorted(tokens_by_position))


def _as_year(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _as_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _provider_total(metadata: Any, *, fallback: int) -> int:
    if isinstance(metadata, dict):
        count = metadata.get("count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            return count
    return fallback


def _persist_research_papers(session: Session, results: list[ResearchResult]) -> None:
    repository = PaperRepository(session)

    for result in results:
        if not result.id:
            continue

        repository.upsert_paper(
            openalex_id=result.id,
            title=result.title,
            authors=result.authors,
            publication_year=result.publication_year,
            abstract=result.abstract,
            doi=result.doi,
            url=result.url,
        )

    session.commit()


def list_saved_papers(
    *, session: Session | None, page: int, limit: int
) -> SavedPaperListResponse:
    if session is None:
        logger.warning("Saved paper retrieval is unavailable because no database session exists.")
        raise SavedPaperServiceError("Saved papers are unavailable because the database is not configured.")

    try:
        items, total = PaperRepository(session).list_papers_page(
            limit=limit,
            offset=(page - 1) * limit,
        )
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Saved paper retrieval failed; the transaction was rolled back.")
        raise SavedPaperServiceError("Saved papers are temporarily unavailable.") from error

    return SavedPaperListResponse(
        items=[SavedPaper.model_validate(paper) for paper in items],
        page=page,
        limit=limit,
        total=total,
        pages=(total + limit - 1) // limit,
    )


def save_research_paper(*, session: Session | None, openalex_id: str) -> SavedPaper:
    if session is None:
        raise SavePaperServiceError(
            "Papers cannot be saved because the database is not configured.",
            503,
        )

    try:
        paper = PaperRepository(session).save_paper(openalex_id)
        if paper is None:
            raise SavePaperServiceError("Paper was not found.")
        session.commit()
        session.refresh(paper)
    except SavePaperServiceError:
        raise
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Saving paper failed; the transaction was rolled back.")
        raise SavePaperServiceError("Paper could not be saved.", 503) from error

    return SavedPaper.model_validate(paper)


def unsave_research_paper(*, session: Session | None, openalex_id: str) -> SavedPaper:
    if session is None:
        raise SavePaperServiceError(
            "Papers cannot be unsaved because the database is not configured.",
            503,
        )

    try:
        paper = PaperRepository(session).unsave_paper(openalex_id)
        if paper is None:
            raise SavePaperServiceError("Paper was not found.")
        session.commit()
        session.refresh(paper)
    except SavePaperServiceError:
        raise
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Unsaving paper failed; the transaction was rolled back.")
        raise SavePaperServiceError("Paper could not be unsaved.", 503) from error

    return SavedPaper.model_validate(paper)
