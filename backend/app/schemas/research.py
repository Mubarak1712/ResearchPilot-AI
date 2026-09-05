from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


SortOption = Literal["relevance", "cited", "newest", "oldest"]


class ResearchResult(BaseModel):
    id: str
    title: str
    authors: list[str]
    publication_year: int | None
    abstract: str | None
    doi: str | None
    url: str | None
    publication_date: str | None = None
    citation_count: int | None = None
    source_name: str | None = None


class ResearchSearchResponse(BaseModel):
    query: str
    total: int
    results: list[ResearchResult]
    page: int = 1
    limit: int = 10
    sort: SortOption = "relevance"


class SavedPaper(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    openalex_id: str
    title: str
    authors: list[str]
    publication_year: int | None
    abstract: str | None
    doi: str | None
    url: str | None
    created_at: datetime
    updated_at: datetime
    is_saved: bool


class SavedPaperListResponse(BaseModel):
    items: list[SavedPaper]
    page: int
    limit: int
    total: int
    pages: int
