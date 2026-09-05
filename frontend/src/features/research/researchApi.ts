import type {
  ResearchPaper,
  ResearchSearchResponse,
  SavedPaper,
  SavedPapersResponse,
  SortOption,
  SearchFilters,
} from './types'

export class ResearchApiError extends Error {}
export class ResearchRequestCancelled extends Error {}

export async function searchResearch(
  query: string,
  page = 1,
  sort: SortOption = 'relevance',
  filters: SearchFilters = { open_access: false, has_doi: false },
  signal?: AbortSignal,
): Promise<ResearchSearchResponse> {
  try {
    const params = new URLSearchParams({ q: query, page: String(page), sort })
    if (filters.from_year !== undefined) params.set('from_year', String(filters.from_year))
    if (filters.to_year !== undefined) params.set('to_year', String(filters.to_year))
    if (filters.open_access) params.set('open_access', 'true')
    if (filters.has_doi) params.set('has_doi', 'true')
    const response = await fetch(
      `/api/v1/research/search?${params.toString()}`,
      { signal },
    )

    if (!response.ok) {
      throw new ResearchApiError('Unable to search for research papers. Please try again.')
    }

    const payload: unknown = await response.json()
    if (!isResearchSearchResponse(payload)) {
      throw new ResearchApiError('The research service returned an invalid response.')
    }

    return payload
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ResearchRequestCancelled()
    }
    if (error instanceof ResearchApiError) {
      throw error
    }

    throw new ResearchApiError('Unable to reach the research service. Please try again.')
  }
}

export async function getSavedPapers(): Promise<SavedPapersResponse> {
  try {
    const response = await fetch('/api/v1/research/papers?page=1&limit=10')

    if (!response.ok) {
      throw new ResearchApiError('Unable to load saved papers. Please try again.')
    }

    const payload: unknown = await response.json()
    if (!isSavedPapersResponse(payload)) {
      throw new ResearchApiError('The saved papers service returned an invalid response.')
    }

    return payload
  } catch (error) {
    if (error instanceof ResearchApiError) {
      throw error
    }

    throw new ResearchApiError('Unable to reach the saved papers service. Please try again.')
  }
}

export async function getPaper(identifier: string): Promise<SavedPaper> {
  try {
    const response = await fetch(`/api/v1/research/papers/${encodeURIComponent(identifier)}`)
    if (!response.ok) {
      throw new ResearchApiError('Unable to load this paper. Please try again.')
    }
    const payload: unknown = await response.json()
    if (!isSavedPaper(payload)) {
      throw new ResearchApiError('The paper details service returned an invalid response.')
    }
    return payload
  } catch (error) {
    if (error instanceof ResearchApiError) throw error
    throw new ResearchApiError('Unable to reach the paper details service. Please try again.')
  }
}

export async function savePaper(openalexId: string): Promise<SavedPaper> {
  try {
    const response = await fetch(
      `/api/v1/research/papers/${encodeURIComponent(openalexId)}/save`,
      { method: 'POST' },
    )

    if (!response.ok) {
      throw new ResearchApiError('Unable to save this paper. Please try again.')
    }

    const payload: unknown = await response.json()
    if (!isSavedPaper(payload)) {
      throw new ResearchApiError('The save paper service returned an invalid response.')
    }

    return payload
  } catch (error) {
    if (error instanceof ResearchApiError) {
      throw error
    }

    throw new ResearchApiError('Unable to reach the save paper service. Please try again.')
  }
}

export async function unsavePaper(openalexId: string): Promise<SavedPaper> {
  try {
    const response = await fetch(
      `/api/v1/research/papers/${encodeURIComponent(openalexId)}/save`,
      { method: 'DELETE' },
    )

    if (!response.ok) {
      throw new ResearchApiError('Unable to unsave this paper. Please try again.')
    }

    const payload: unknown = await response.json()
    if (!isSavedPaper(payload)) {
      throw new ResearchApiError('The unsave paper service returned an invalid response.')
    }

    return payload
  } catch (error) {
    if (error instanceof ResearchApiError) {
      throw error
    }

    throw new ResearchApiError('Unable to reach the unsave paper service. Please try again.')
  }
}

function isResearchSearchResponse(value: unknown): value is ResearchSearchResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.query === 'string' &&
    typeof value.total === 'number' &&
    typeof value.page === 'number' &&
    typeof value.limit === 'number' &&
    isSortOption(value.sort) &&
    Array.isArray(value.results) &&
    value.results.every(isResearchPaper)
  )
}

function isSortOption(value: unknown): value is SortOption {
  return value === 'relevance' || value === 'cited' || value === 'newest' || value === 'oldest'
}

function isResearchPaper(value: unknown): value is ResearchPaper {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.id === 'string' &&
    isResearchPaperFields(value)
  )
}

function isResearchPaperFields(value: Record<string, unknown>): boolean {
  return (
    typeof value.title === 'string' &&
    Array.isArray(value.authors) &&
    value.authors.every((author) => typeof author === 'string') &&
    isNullableNumber(value.publication_year) &&
    isNullableString(value.abstract) &&
    isNullableString(value.doi) &&
    isNullableString(value.url) &&
    isOptionalNullableString(value.publication_date) &&
    isOptionalNullableNumber(value.citation_count) &&
    isOptionalNullableString(value.source_name)
  )
}

function isSavedPapersResponse(value: unknown): value is SavedPapersResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.page === 'number' &&
    typeof value.limit === 'number' &&
    typeof value.total === 'number' &&
    typeof value.pages === 'number' &&
    Array.isArray(value.items) &&
    value.items.every(isSavedPaper)
  )
}

function isSavedPaper(value: unknown): value is SavedPaper {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.id === 'number' &&
    isResearchPaperFields(value) &&
    typeof value.openalex_id === 'string' &&
    typeof value.created_at === 'string' &&
    typeof value.updated_at === 'string'
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === 'string' || value === null
}

function isNullableNumber(value: unknown): value is number | null {
  return typeof value === 'number' || value === null
}

function isOptionalNullableString(value: unknown): value is string | null | undefined {
  return value === undefined || isNullableString(value)
}

function isOptionalNullableNumber(value: unknown): value is number | null | undefined {
  return value === undefined || isNullableNumber(value)
}
