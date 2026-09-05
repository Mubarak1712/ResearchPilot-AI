from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.ownership import OwnedPaperResponse, SaveStatusResponse, UserSavedPaperResponse
from app.services.ownership_service import (
    OwnershipServiceError,
    is_paper_saved_for_user,
    list_papers_saved_by_user,
    save_paper_for_user,
    unsave_paper_for_user,
)


router = APIRouter(prefix="/api/v1/ownership", tags=["ownership"])


@router.post("/papers/{paper_id}", response_model=UserSavedPaperResponse, status_code=status.HTTP_201_CREATED)
def save_paper(
    paper_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> UserSavedPaperResponse:
    try:
        association = save_paper_for_user(
            session=db_session, user=current_user, paper_id=paper_id
        )
        return UserSavedPaperResponse.model_validate(association)
    except OwnershipServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.delete("/papers/{paper_id}", response_model=SaveStatusResponse)
def unsave_paper(
    paper_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> SaveStatusResponse:
    try:
        unsave_paper_for_user(session=db_session, user=current_user, paper_id=paper_id)
        return SaveStatusResponse(paper_id=paper_id, is_saved=False)
    except OwnershipServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/papers/{paper_id}", response_model=SaveStatusResponse)
def get_save_status(
    paper_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> SaveStatusResponse:
    try:
        is_saved = is_paper_saved_for_user(
            session=db_session, user=current_user, paper_id=paper_id
        )
        return SaveStatusResponse(paper_id=paper_id, is_saved=is_saved)
    except OwnershipServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/papers", response_model=list[OwnedPaperResponse])
def list_saved_papers(
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> list[OwnedPaperResponse]:
    try:
        papers = list_papers_saved_by_user(session=db_session, user=current_user)
        return [OwnedPaperResponse.model_validate(paper) for paper in papers]
    except OwnershipServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
