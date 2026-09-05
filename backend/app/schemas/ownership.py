from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserSavedPaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paper_id: int
    created_at: datetime


class SaveStatusResponse(BaseModel):
    paper_id: int
    is_saved: bool


class OwnedPaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    openalex_id: str
    title: str
    authors: list[str]
    publication_year: int | None
    abstract: str | None
    doi: str | None
    url: str | None
