import unittest
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, select
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.schemas.research import ResearchSearchResponse
from app.services.research_service import (
    ResearchServiceError,
    _normalize_work,
    search_research_papers,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.last_params: dict | None = None

    async def get(self, url: str, *, params: dict) -> FakeResponse:
        self.last_params = params
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ResearchSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_page_one_sends_openalex_page_and_limit(self) -> None:
        client = FakeClient(FakeResponse({"meta": {"count": 25}, "results": []}))

        result = await search_research_papers("AI", page=1, client=client)

        self.assertEqual(
            client.last_params,
            {"search": "AI", "page": 1, "per-page": 10, "sort": "relevance_score:desc"},
        )
        self.assertEqual(result.page, 1)
        self.assertEqual(result.limit, 10)
        self.assertEqual(result.total, 25)
        self.assertEqual(result.sort, "relevance")

    async def test_search_page_two_uses_provider_total(self) -> None:
        client = FakeClient(FakeResponse({"meta": {"count": 25}, "results": []}))

        result = await search_research_papers("AI", page=2, client=client)

        self.assertEqual(
            client.last_params,
            {"search": "AI", "page": 2, "per-page": 10, "sort": "relevance_score:desc"},
        )
        self.assertEqual(result.page, 2)
        self.assertEqual(result.total, 25)

    async def test_supported_sort_options_map_to_openalex_sort_values(self) -> None:
        expected = {
            "relevance": "relevance_score:desc",
            "cited": "cited_by_count:desc",
            "newest": "publication_date:desc",
            "oldest": "publication_date:asc",
        }

        for sort, provider_sort in expected.items():
            client = FakeClient(FakeResponse({"meta": {"count": 25}, "results": []}))
            result = await search_research_papers("AI", page=2, sort=sort, client=client)

            self.assertEqual(client.last_params["sort"], provider_sort)
            self.assertEqual(result.sort, sort)

    async def test_each_search_filter_maps_to_openalex_filter(self) -> None:
        cases = (
            ({"from_year": 2015}, "from_publication_date:2015-01-01"),
            ({"to_year": 2025}, "to_publication_date:2025-12-31"),
            ({"open_access": True}, "is_oa:true"),
            ({"has_doi": True}, "has_doi:true"),
        )

        for filter_kwargs, expected_filter in cases:
            client = FakeClient(FakeResponse({"meta": {"count": 10}, "results": []}))
            await search_research_papers("AI", client=client, **filter_kwargs)

            self.assertEqual(client.last_params["filter"], expected_filter)

    async def test_combined_filters_preserve_page_and_sort(self) -> None:
        client = FakeClient(FakeResponse({"meta": {"count": 25}, "results": []}))

        result = await search_research_papers(
            "AI",
            page=2,
            sort="oldest",
            from_year=2015,
            to_year=2025,
            open_access=True,
            has_doi=True,
            client=client,
        )

        self.assertEqual(
            client.last_params,
            {
                "search": "AI",
                "page": 2,
                "per-page": 10,
                "sort": "publication_date:asc",
                "filter": "from_publication_date:2015-01-01,to_publication_date:2025-12-31,is_oa:true,has_doi:true",
            },
        )
        self.assertEqual(result.total, 25)
        self.assertEqual(result.page, 2)
        self.assertEqual(result.sort, "oldest")

    async def test_search_uses_result_count_when_provider_metadata_is_missing_or_malformed(self) -> None:
        for metadata in (None, {}, {"count": "25"}, {"count": -1}):
            result = await search_research_papers(
                "AI",
                client=FakeClient(FakeResponse({"meta": metadata, "results": [{"id": "W1"}]})),
            )
            self.assertEqual(result.total, 1)

    async def test_successful_search_normalizes_openalex_response(self) -> None:
        response = FakeResponse(
            {
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "title": "AI in agriculture",
                        "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                        "publication_year": 2025,
                        "abstract_inverted_index": {"Agriculture": [1], "AI": [0]},
                        "doi": "https://doi.org/10.1000/example",
                        "primary_location": {"landing_page_url": "https://example.org/paper"},
                    }
                ]
            }
        )

        result = await search_research_papers("AI in agriculture", client=FakeClient(response))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.results[0].authors, ["Ada Lovelace"])
        self.assertEqual(result.results[0].abstract, "AI Agriculture")
        self.assertEqual(result.results[0].url, "https://example.org/paper")

    async def test_search_normalizes_research_metadata(self) -> None:
        result = await search_research_papers(
            "AI in agriculture",
            client=FakeClient(
                FakeResponse(
                    {
                        "results": [
                            {
                                "id": "https://openalex.org/W1",
                                "title": "AI in agriculture",
                                "authorships": [],
                                "publication_year": 2025,
                                "publication_date": "2025-04-12",
                                "cited_by_count": 42,
                                "primary_location": {
                                    "source": {"display_name": "Research Journal"}
                                },
                            }
                        ]
                    }
                )
            ),
        )

        normalized = result.results[0]
        self.assertEqual(normalized.publication_date, "2025-04-12")
        self.assertEqual(normalized.citation_count, 42)
        self.assertEqual(normalized.source_name, "Research Journal")

    async def test_search_metadata_handles_missing_fields_and_locations(self) -> None:
        missing_date = _normalize_work(
            {"id": "https://openalex.org/W1", "title": "Missing date"}
        )
        missing_citations = _normalize_work(
            {"id": "https://openalex.org/W2", "title": "Missing citations"}
        )
        missing_source = _normalize_work(
            {
                "id": "https://openalex.org/W3",
                "title": "Missing source",
                "primary_location": {},
            }
        )
        malformed_location = _normalize_work(
            {
                "id": "https://openalex.org/W4",
                "title": "Malformed location",
                "primary_location": "not-an-object",
            }
        )

        self.assertIsNone(missing_date.publication_date)
        self.assertIsNone(missing_citations.citation_count)
        self.assertIsNone(missing_source.source_name)
        self.assertIsNone(malformed_location.source_name)

    async def test_external_api_failure_raises_service_error(self) -> None:
        request = httpx.Request("GET", "https://api.openalex.org/works")
        response = httpx.Response(503, request=request)
        error = httpx.HTTPStatusError("Service unavailable", request=request, response=response)

        with self.assertRaises(ResearchServiceError) as context:
            await search_research_papers("AI in agriculture", client=FakeClient(error))

        self.assertEqual(context.exception.status_code, 502)


class ResearchRouterTests(unittest.TestCase):
    def test_missing_query_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/search")

        self.assertEqual(response.status_code, 422)

    def test_empty_query_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/search", params={"q": "   "})

        self.assertEqual(response.status_code, 422)

    def test_invalid_search_page_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/research/search", params={"q": "AI", "page": 0})

        self.assertEqual(response.status_code, 422)

    def test_successful_search_endpoint(self) -> None:
        expected = ResearchSearchResponse(query="AI in agriculture", total=0, results=[])
        with patch(
            "app.api.v1.routers.research.search_research_papers",
            new=AsyncMock(return_value=expected),
        ):
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/research/search", params={"q": "AI in agriculture"}
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected.model_dump())

    def test_unsupported_search_sort_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/research/search", params={"q": "AI", "sort": "popular"}
            )

        self.assertEqual(response.status_code, 422)

    def test_invalid_search_years_are_rejected(self) -> None:
        with TestClient(app) as client:
            short_year = client.get(
                "/api/v1/research/search", params={"q": "AI", "from_year": 99}
            )
            reversed_years = client.get(
                "/api/v1/research/search",
                params={"q": "AI", "from_year": 2025, "to_year": 2015},
            )

        self.assertEqual(short_year.status_code, 422)
        self.assertEqual(reversed_years.status_code, 422)


class DatabaseFoundationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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

    def test_repository_upsert_updates_existing_paper(self) -> None:
        session = self.SessionLocal()
        repository = PaperRepository(session)

        try:
            repository.upsert_paper(
                openalex_id="https://openalex.org/W1",
                title="Original title",
                authors=["Ada Lovelace"],
                publication_year=2025,
                abstract="Original abstract",
                doi="https://doi.org/10.1000/example",
                url="https://example.org/paper",
            )
            session.commit()

            repository.upsert_paper(
                openalex_id="https://openalex.org/W1",
                title="Updated title",
                authors=["Ada Lovelace", "Grace Hopper"],
                publication_year=2026,
                abstract="Updated abstract",
                doi="https://doi.org/10.1000/example",
                url="https://example.org/paper-updated",
            )
            session.commit()

            stored = repository.find_by_openalex_id("https://openalex.org/W1")
            self.assertIsNotNone(stored)
            self.assertEqual(stored.title, "Updated title")
            self.assertEqual(stored.authors, ["Ada Lovelace", "Grace Hopper"])
            self.assertEqual(len(repository.list_papers()), 1)

            stored.is_saved = True
            session.commit()
            repository.upsert_paper(
                openalex_id="https://openalex.org/W1",
                title="Updated again",
                authors=["Ada Lovelace"],
                publication_year=2027,
                abstract="Updated again",
                doi=None,
                url=None,
            )
            session.commit()
            self.assertTrue(repository.find_by_openalex_id("https://openalex.org/W1").is_saved)
        finally:
            session.close()

    def test_repository_keeps_two_openalex_records_identity_separate(self) -> None:
        session = self.SessionLocal()
        repository = PaperRepository(session)
        try:
            repository.upsert_paper(
                openalex_id="https://openalex.org/WA",
                title="Paper A",
                authors=["Author A"],
                publication_year=2024,
                abstract="Abstract A",
                doi="https://doi.org/a",
                url="https://example.org/a",
            )
            repository.upsert_paper(
                openalex_id="https://openalex.org/WB",
                title="Paper B",
                authors=["Author B"],
                publication_year=2025,
                abstract="Abstract B",
                doi="https://doi.org/b",
                url="https://example.org/b",
            )
            session.commit()
            paper_a = repository.find_by_openalex_id("https://openalex.org/WA")
            paper_b = repository.find_by_openalex_id("https://openalex.org/WB")
            self.assertEqual((paper_a.title, paper_a.abstract, paper_a.doi), ("Paper A", "Abstract A", "https://doi.org/a"))
            self.assertEqual((paper_b.title, paper_b.abstract, paper_b.doi), ("Paper B", "Abstract B", "https://doi.org/b"))
            self.assertEqual(repository.find_by_id_or_openalex_id(str(paper_a.id)).openalex_id, paper_a.openalex_id)
            self.assertEqual(repository.find_by_id_or_openalex_id(paper_b.openalex_id).id, paper_b.id)
        finally:
            session.close()

    async def test_search_persists_normalized_results_without_real_database(self) -> None:
        session = self.SessionLocal()
        try:
            response = FakeResponse(
                {
                    "results": [
                        {
                            "id": "https://openalex.org/W2",
                            "title": "AI in agriculture",
                            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                            "publication_year": 2025,
                            "abstract_inverted_index": {"Agriculture": [1], "AI": [0]},
                            "doi": "https://doi.org/10.1000/example",
                            "primary_location": {"landing_page_url": "https://example.org/paper"},
                        }
                    ]
                }
            )

            result = await search_research_papers(
                "AI in agriculture",
                client=FakeClient(response),
                session=session,
            )

            self.assertEqual(result.total, 1)
            stored = session.scalar(
                select(Paper).where(Paper.openalex_id == "https://openalex.org/W2")
            )
            self.assertIsNotNone(stored)
            self.assertEqual(stored.title, "AI in agriculture")
            self.assertEqual(stored.authors, ["Ada Lovelace"])
            self.assertEqual(stored.openalex_id, "https://openalex.org/W2")
            self.assertEqual(stored.doi, "https://doi.org/10.1000/example")
            self.assertEqual(stored.abstract, "AI Agriculture")
        finally:
            session.close()
