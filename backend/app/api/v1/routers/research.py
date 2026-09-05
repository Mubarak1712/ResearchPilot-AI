from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.research import ResearchSearchResponse, SavedPaper, SavedPaperListResponse, SortOption
from app.services.research_service import (
    ResearchServiceError,
    SavePaperServiceError,
    SavedPaperServiceError,
    save_research_paper,
    list_saved_papers,
    search_research_papers,
    unsave_research_paper,
    get_persisted_paper,
)


router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.get("/search", response_model=ResearchSearchResponse)
async def search_research(
    q: Annotated[str, Query(description="Research topic to search for")],
    db_session: Annotated[Session | None, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    sort: Annotated[SortOption, Query()] = "relevance",
    from_year: Annotated[int | None, Query(ge=1000, le=9999)] = None,
    to_year: Annotated[int | None, Query(ge=1000, le=9999)] = None,
    open_access: Annotated[bool, Query()] = False,
    has_doi: Annotated[bool, Query()] = False,
) -> ResearchSearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query parameter 'q' must not be empty.")
    if from_year is not None and to_year is not None and from_year > to_year:
        raise HTTPException(status_code=422, detail="from_year must not be greater than to_year.")

    try:
        return await search_research_papers(
            query,
            page=page,
            sort=sort,
            from_year=from_year,
            to_year=to_year,
            open_access=open_access,
            has_doi=has_doi,
            session=db_session,
        )
    except ResearchServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/papers", response_model=SavedPaperListResponse)
def get_saved_papers(
    db_session: Annotated[Session | None, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SavedPaperListResponse:
    try:
        return list_saved_papers(session=db_session, page=page, limit=limit)
    except SavedPaperServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/papers/{identifier:path}", response_model=SavedPaper)
def get_paper_details(
    identifier: str,
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> SavedPaper:
    try:
        return get_persisted_paper(session=db_session, identifier=identifier)
    except SavedPaperServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/papers/{openalex_id:path}/save", response_model=SavedPaper)
def save_paper(
    openalex_id: str,
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> SavedPaper:
    try:
        return save_research_paper(session=db_session, openalex_id=openalex_id)
    except SavePaperServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.delete("/papers/{openalex_id:path}/save", response_model=SavedPaper)
def unsave_paper(
    openalex_id: str,
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> SavedPaper:
    try:
        return unsave_research_paper(session=db_session, openalex_id=openalex_id)
    except SavePaperServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
