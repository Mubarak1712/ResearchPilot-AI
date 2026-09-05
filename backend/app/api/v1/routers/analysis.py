from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.analysis_api import (
    AnalysisCreateRequest,
    AnalysisEvidenceResponse,
    AnalysisGapResponse,
    AnalysisResponse,
)
from app.services.analysis_service import (
    AnalysisServiceError,
    create_analysis,
    get_analysis,
    get_analysis_evidence,
    get_analysis_gaps,
)


router = APIRouter(prefix="/api/v1/analyses", tags=["analysis"])


def _raise(error: AnalysisServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("", response_model=AnalysisResponse, status_code=201)
def create(
    request: AnalysisCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> AnalysisResponse:
    try:
        return create_analysis(session=db_session, user=current_user, request=request)
    except AnalysisServiceError as error:
        _raise(error)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def read(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> AnalysisResponse:
    try:
        return get_analysis(session=db_session, user=current_user, analysis_id=analysis_id)
    except AnalysisServiceError as error:
        _raise(error)


@router.get("/{analysis_id}/evidence", response_model=list[AnalysisEvidenceResponse])
def read_evidence(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> list[AnalysisEvidenceResponse]:
    try:
        return get_analysis_evidence(session=db_session, user=current_user, analysis_id=analysis_id)
    except AnalysisServiceError as error:
        _raise(error)


@router.get("/{analysis_id}/gaps", response_model=list[AnalysisGapResponse])
def read_gaps(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[Session | None, Depends(get_db_session)],
) -> list[AnalysisGapResponse]:
    try:
        return get_analysis_gaps(session=db_session, user=current_user, analysis_id=analysis_id)
    except AnalysisServiceError as error:
        _raise(error)
