import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  getSavedPapers,
  ResearchApiError,
  ResearchRequestCancelled,
  savePaper,
  searchResearch,
} from './researchApi'
import { useAuth } from '../auth/useAuth'
import { useOwnership } from '../auth/useOwnership'
import { AnalysisApiError, createAnalysis } from '../analysis/analysisApi'
import type {
  ResearchPaper,
  ResearchSearchResponse,
  SavedPaper,
  SearchFilters,
  SortOption,
} from './types'
import './ResearchSearchPage.css'

type UrlSearchState = {
  query: string
  page: number
  sort: SortOption
  filters: SearchFilters
}

function readUrlSearchState(): UrlSearchState {
  const params = new URLSearchParams(window.location.search)
  const pageValue = Number(params.get('page'))
  const fromYearValue = params.get('from_year')
  const toYearValue = params.get('to_year')
  const fromYear = fromYearValue && /^\d{4}$/.test(fromYearValue) ? Number(fromYearValue) : undefined
  const toYear = toYearValue && /^\d{4}$/.test(toYearValue) ? Number(toYearValue) : undefined
  const sortValue = params.get('sort')
  const sort: SortOption = sortValue === 'cited' || sortValue === 'newest' || sortValue === 'oldest'
    ? sortValue
    : 'relevance'

  return {
    query: params.get('q')?.trim() ?? '',
    page: Number.isInteger(pageValue) && pageValue > 0 ? pageValue : 1,
    sort,
    filters: {
      from_year: fromYear,
      to_year: toYear,
      open_access: params.get('open_access') === 'true',
      has_doi: params.get('has_doi') === 'true',
    },
  }
}

function writeUrlSearchState(state: UrlSearchState, replace = false) {
  const params = new URLSearchParams()
  if (state.query) params.set('q', state.query)
  if (state.page > 1) params.set('page', String(state.page))
  if (state.sort !== 'relevance') params.set('sort', state.sort)
  if (state.filters.from_year !== undefined) params.set('from_year', String(state.filters.from_year))
  if (state.filters.to_year !== undefined) params.set('to_year', String(state.filters.to_year))
  if (state.filters.open_access) params.set('open_access', 'true')
  if (state.filters.has_doi) params.set('has_doi', 'true')

  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params}` : ''}${window.location.hash}`
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
  if (nextUrl === currentUrl) {
    return
  }
  window.history[replace ? 'replaceState' : 'pushState']({}, '', nextUrl)
}

function isValidYearInput(value: string) {
  const year = Number(value)
  return /^\d{4}$/.test(value) && Number.isInteger(year) && year >= 1000 && year <= 9999
}

function formatAuthorPreview(authors: string[]) {
  if (authors.length === 0) {
    return 'Authors unavailable'
  }
  if (authors.length <= 3) {
    return authors.join(', ')
  }
  return `${authors.slice(0, 3).join(', ')}, and ${authors.length - 3} more`
}

function formatAbstractPreview(abstract: string | null) {
  if (!abstract) {
    return null
  }
  const previewLength = 280
  return abstract.length > previewLength
    ? `${abstract.slice(0, previewLength).trimEnd()}…`
    : abstract
}

function ResearchSearchPage() {
  const { accessToken } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const {
    savedPapers: ownedSavedPapers,
    isPaperSaved,
    loadSavedPapers,
    savePaper: saveOwnedPaper,
    unsavePaper: unsaveOwnedPaper,
  } = useOwnership()
  const [query, setQuery] = useState('')
  const [searchResult, setSearchResult] = useState<ResearchSearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [savedPapers, setSavedPapers] = useState<SavedPaper[]>([])
  const [savingPaperId, setSavingPaperId] = useState<string | null>(null)
  const [unsavingPaperId, setUnsavingPaperId] = useState<string | null>(null)
  const [selectedPaperIds, setSelectedPaperIds] = useState<number[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    open_access: false,
    has_doi: false,
  })
  const [fromYearInput, setFromYearInput] = useState('')
  const [toYearInput, setToYearInput] = useState('')
  const requestSequence = useRef(0)
  const activeController = useRef<AbortController | null>(null)
  const searchLocation = location.search || window.location.search
  const showResults = location.pathname === '/research/results' || Boolean(new URLSearchParams(searchLocation).get('q'))

  function beginSearchRequest() {
    activeController.current?.abort()
    const controller = new AbortController()
    activeController.current = controller
    const sequence = ++requestSequence.current
    setIsLoading(true)
    return { controller, sequence }
  }

  function isCurrentSearchRequest(sequence: number, controller: AbortController) {
    return requestSequence.current === sequence && activeController.current === controller
  }

  function resetActiveSearch(clearResults = false) {
    activeController.current?.abort()
    activeController.current = null
    requestSequence.current += 1
    setIsLoading(false)
    setError(null)
    if (clearResults) {
      setSearchResult(null)
    }
  }

  async function runUrlSearch(state: UrlSearchState) {
    if (!state.query) {
      resetActiveSearch(true)
      return
    }

    const { controller, sequence } = beginSearchRequest()
    setError(null)
    try {
      const result = await searchResearch(state.query, state.page, state.sort, state.filters, controller.signal)
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while restoring search results.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    const initialState = readUrlSearchState()
    setQuery(initialState.query)
    setSearchFilters(initialState.filters)
    setFromYearInput(initialState.filters.from_year?.toString() ?? '')
    setToYearInput(initialState.filters.to_year?.toString() ?? '')
    void runUrlSearch(initialState)

    function handlePopState() {
      const nextState = readUrlSearchState()
      setQuery(nextState.query)
      setSearchFilters(nextState.filters)
      setFromYearInput(nextState.filters.from_year?.toString() ?? '')
      setToYearInput(nextState.filters.to_year?.toString() ?? '')
      void runUrlSearch(nextState)
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    let isCurrent = true

    async function loadSavedPapers() {
      try {
        const result = await getSavedPapers()
        if (isCurrent) {
          setSavedPapers(result.items)
        }
      } catch {
        if (isCurrent) {
          setSavedPapers([])
        }
      }
    }

    void loadSavedPapers()
    return () => {
      isCurrent = false
    }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedQuery = query.trim()

    if (!trimmedQuery) {
      resetActiveSearch(true)
      writeUrlSearchState({ query: '', page: 1, sort: 'relevance', filters: searchFilters })
      return
    }

    if (location.pathname !== '/research/results') {
      writeUrlSearchState({ query: trimmedQuery, page: 1, sort: 'relevance', filters: searchFilters })
      navigate(`/research/results${window.location.search}`)
      return
    }

    setError(null)
    const { controller, sequence } = beginSearchRequest()

    try {
      const result = await searchResearch(trimmedQuery, 1, 'relevance', searchFilters, controller.signal)
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
        writeUrlSearchState({ query: trimmedQuery, page: 1, sort: 'relevance', filters: searchFilters })
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while searching for papers.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  async function handleSearchPageChange(nextPage: number) {
    const trimmedQuery = query.trim()
    if (!trimmedQuery || nextPage < 1) {
      return
    }

    setError(null)
    const { controller, sequence } = beginSearchRequest()
    try {
      const result = await searchResearch(
        trimmedQuery,
        nextPage,
        searchResult?.sort ?? 'relevance',
        searchFilters,
        controller.signal,
      )
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
        writeUrlSearchState({
          query: trimmedQuery,
          page: nextPage,
          sort: searchResult?.sort ?? 'relevance',
          filters: searchFilters,
        })
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while changing search pages.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  async function handleSortChange(nextSort: SortOption) {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      return
    }

    setError(null)
    const { controller, sequence } = beginSearchRequest()
    try {
      const result = await searchResearch(trimmedQuery, 1, nextSort, searchFilters, controller.signal)
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
        writeUrlSearchState({ query: trimmedQuery, page: 1, sort: nextSort, filters: searchFilters })
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while changing search sorting.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  async function handleFilterSubmit(
    event: FormEvent<HTMLFormElement>,
    filterOverrides: SearchFilters = searchFilters,
  ) {
    event.preventDefault()
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      return
    }

    const fromYear = fromYearInput ? Number(fromYearInput) : undefined
    const toYear = toYearInput ? Number(toYearInput) : undefined
    if (
      (fromYearInput && !isValidYearInput(fromYearInput)) ||
      (toYearInput && !isValidYearInput(toYearInput)) ||
      (fromYear !== undefined && toYear !== undefined && fromYear > toYear)
    ) {
      setError('Use four-digit years with a valid year range.')
      return
    }

    const nextFilters: SearchFilters = {
      from_year: fromYear,
      to_year: toYear,
      open_access: filterOverrides.open_access,
      has_doi: filterOverrides.has_doi,
    }
    setSearchFilters(nextFilters)
    setError(null)
    const { controller, sequence } = beginSearchRequest()
    try {
      const result = await searchResearch(trimmedQuery, 1, searchResult?.sort ?? 'relevance', nextFilters, controller.signal)
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
        writeUrlSearchState({
          query: trimmedQuery,
          page: 1,
          sort: searchResult?.sort ?? 'relevance',
          filters: nextFilters,
        })
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while filtering search results.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  async function handleClearFilters() {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      return
    }

    const clearedFilters: SearchFilters = { open_access: false, has_doi: false }
    setSearchFilters(clearedFilters)
    setFromYearInput('')
    setToYearInput('')
    setError(null)
    const { controller, sequence } = beginSearchRequest()
    try {
      const result = await searchResearch(trimmedQuery, 1, searchResult?.sort ?? 'relevance', clearedFilters, controller.signal)
      if (isCurrentSearchRequest(sequence, controller)) {
        setSearchResult(result)
        writeUrlSearchState({
          query: trimmedQuery,
          page: 1,
          sort: searchResult?.sort ?? 'relevance',
          filters: clearedFilters,
        })
      }
    } catch (caughtError) {
      if (isCurrentSearchRequest(sequence, controller) && !(caughtError instanceof ResearchRequestCancelled)) {
        setError(
          caughtError instanceof ResearchApiError
            ? caughtError.message
            : 'Something went wrong while clearing search filters.',
        )
      }
    } finally {
      if (isCurrentSearchRequest(sequence, controller)) {
        setIsLoading(false)
      }
    }
  }

  async function handleBooleanFilterChange(name: 'open_access' | 'has_doi', value: boolean) {
    const nextFilters = { ...searchFilters, [name]: value }
    setSearchFilters(nextFilters)
    const fakeEvent = { preventDefault: () => undefined } as FormEvent<HTMLFormElement>
    await handleFilterSubmit(fakeEvent, nextFilters)
  }

  function resolveOwnedPaperId(openalexId: string): number | null {
    const match = ownedSavedPapers.find((paper) => paper.openalex_id === openalexId)
    return match ? match.id : null
  }

  function toggleAnalysisSelection(paper: ResearchPaper) {
    const paperId = resolveOwnedPaperId(paper.id)
    if (paperId === null) {
      setError('Save this paper before selecting it for analysis.')
      return
    }
    setSelectedPaperIds((current) => current.includes(paperId)
      ? current.filter((id) => id !== paperId)
      : current.length >= 20 ? current : [...current, paperId])
  }

  async function handleAnalyzeSelected() {
    if (!accessToken || selectedPaperIds.length === 0 || isAnalyzing) return
    setIsAnalyzing(true)
    setError(null)
    try {
      const analysis = await createAnalysis(accessToken, { paper_ids: selectedPaperIds })
      navigate(`/analysis/${analysis.analysis_id}`)
    } catch (caughtError) {
      setError(caughtError instanceof AnalysisApiError ? caughtError.message : 'Unable to start the analysis.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  function isSavedByOwnership(paper: ResearchPaper | SavedPaper) {
    const openalexId = 'openalex_id' in paper ? paper.openalex_id : paper.id
    const ownedPaperId = resolveOwnedPaperId(openalexId)
    return ownedPaperId !== null && isPaperSaved(ownedPaperId)
  }

  async function handleSavePaper(paper: ResearchPaper) {
    if (!accessToken) {
      return
    }

    setSavingPaperId(paper.id)
    try {
      const ownedPaperId = resolveOwnedPaperId(paper.id)
      if (ownedPaperId !== null) {
        await saveOwnedPaper(ownedPaperId)
        try {
          await loadSavedPapers()
        } catch {
          // ignore load errors here – the save itself succeeded and will be present after refresh
        }
        return
      }

      const createdPaper = await savePaper(paper.id)
      await saveOwnedPaper(createdPaper.id)
      try {
        await loadSavedPapers()
      } catch {
        // ignore load errors here – the save itself succeeded and will be present after refresh
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof ResearchApiError
          ? caughtError.message
          : 'Something went wrong while saving this paper.',
      )
    } finally {
      setSavingPaperId(null)
    }
  }

  async function handleUnsavePaper(openalexId: string) {
    if (!accessToken) {
      return
    }

    const ownedPaperId = resolveOwnedPaperId(openalexId)
    if (ownedPaperId === null) {
      return
    }

    setUnsavingPaperId(openalexId)
    try {
      await unsaveOwnedPaper(ownedPaperId)
      try {
        await loadSavedPapers()
      } catch {
        // ignore load errors – unsave already updated local state where possible
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof ResearchApiError
          ? caughtError.message
          : 'Something went wrong while unsaving this paper.',
      )
    } finally {
      setUnsavingPaperId(null)
    }
  }

  return (
    <main className="research-page">
      <section className="research-hero" id="research" aria-labelledby="research-title">
        <p className="brand">ResearchPilot</p>
        <h1 id="research-title">Discover the research behind your next idea.</h1>
        <p className="hero-copy">
          Search scholarly work from OpenAlex and explore relevant papers in one focused place.
        </p>

        <form className="search-panel" onSubmit={handleSubmit} noValidate>
          <label htmlFor="research-query">Research topic</label>
          <div className="search-controls">
            <input
              id="research-query"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try: AI in agriculture"
              autoComplete="off"
              disabled={isLoading}
            />
            <button type="submit" disabled={isLoading}>
              {isLoading ? 'Searching…' : 'Search papers'}
            </button>
          </div>
        </form>
      </section>

      {showResults && <section className="research-results" aria-live="polite" aria-busy={isLoading}>
        {isLoading && <p className="status-message">Searching OpenAlex for relevant papers…</p>}

        {error && <p className="status-message status-error" role="alert">{error}</p>}

        {searchResult && searchResult.total === 0 && (
          <div className="empty-state">
            <h2>No papers found</h2>
            <p>Try a broader topic or different keywords.</p>
          </div>
        )}

        {searchResult && (
          <>
            <div className="results-heading">
              <p className="eyebrow">Search results</p>
              <div className="results-heading__row">
                {searchResult.total > 0 ? <h2>
                  {searchResult.total} {searchResult.total === 1 ? 'paper' : 'papers'} for “{searchResult.query}”
                </h2> : <span />}
                <label className="sort-control">
                  <span>Sort by</span>
                  <select
                    value={searchResult.sort}
                    onChange={(event) => void handleSortChange(event.target.value as SortOption)}
                    disabled={isLoading}
                  >
                    <option value="relevance">Relevance</option>
                    <option value="cited">Most cited</option>
                    <option value="newest">Newest</option>
                    <option value="oldest">Oldest</option>
                  </select>
                </label>
              </div>
              <div className="analysis-selection-summary">
                <span>{selectedPaperIds.length} papers selected</span>
                {selectedPaperIds.length >= 20 && <span>Maximum 20 papers can be analyzed at once.</span>}
                <button type="button" onClick={() => void handleAnalyzeSelected()} disabled={!accessToken || selectedPaperIds.length === 0 || isAnalyzing}>
                  {isAnalyzing ? 'Starting analysis…' : `Analyze ${selectedPaperIds.length} selected papers`}
                </button>
              </div>
            </div>
            <form className="filter-panel" onSubmit={handleFilterSubmit}>
              <label>
                From year
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={4}
                  value={fromYearInput}
                  onChange={(event) => setFromYearInput(event.target.value)}
                  placeholder="e.g. 2015"
                />
              </label>
              <label>
                To year
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={4}
                  value={toYearInput}
                  onChange={(event) => setToYearInput(event.target.value)}
                  placeholder="e.g. 2025"
                />
              </label>
              <label className="checkbox-filter">
                <input
                  type="checkbox"
                  checked={searchFilters.open_access}
                  onChange={(event) => void handleBooleanFilterChange('open_access', event.target.checked)}
                />
                Open access
              </label>
              <label className="checkbox-filter">
                <input
                  type="checkbox"
                  checked={searchFilters.has_doi}
                  onChange={(event) => void handleBooleanFilterChange('has_doi', event.target.checked)}
                />
                Has DOI
              </label>
              <button type="submit" disabled={isLoading}>Apply filters</button>
              <button className="clear-filter-button" type="button" onClick={() => void handleClearFilters()} disabled={isLoading}>
                Clear filters
              </button>
            </form>
            {searchResult.total > 0 && <div className="paper-list">
              {searchResult.results.map((paper) => (
                <ResearchPaperCard
                  key={paper.id}
                  paper={paper}
                  isSaved={accessToken ? isSavedByOwnership(paper) : savedPapers.some((savedPaper) => savedPaper.openalex_id === paper.id)}
                  isSaving={savingPaperId === paper.id}
                  isUnsaving={unsavingPaperId === paper.id}
                  saveDisabled={!accessToken}
                  unsaveDisabled={!accessToken}
                  onSelect={(paper) => navigate(`/papers/${encodeURIComponent(paper.id)}`, { state: { paper } })}
                  isSelected={(() => { const id = resolveOwnedPaperId(paper.id); return id !== null && selectedPaperIds.includes(id) })()}
                  canSelect={accessToken !== null && resolveOwnedPaperId(paper.id) !== null}
                  selectionDisabled={selectedPaperIds.length >= 20}
                  onToggleSelection={toggleAnalysisSelection}
                  onSave={handleSavePaper}
                  onUnsave={handleUnsavePaper}
                />
              ))}
            </div>}
            {searchResult.total > 0 && <div className="search-pagination" aria-label="Search result pages">
              <button
                type="button"
                onClick={() => void handleSearchPageChange(searchResult.page - 1)}
                disabled={isLoading || searchResult.page <= 1}
              >
                Previous
              </button>
              <span>Page {searchResult.page} of {Math.max(1, Math.ceil(searchResult.total / searchResult.limit))}</span>
              <button
                type="button"
                onClick={() => void handleSearchPageChange(searchResult.page + 1)}
                disabled={isLoading || searchResult.page >= Math.ceil(searchResult.total / searchResult.limit)}
              >
                Next
              </button>
            </div>}
          </>
        )}
      </section>}
    </main>
  )
}

function ResearchPaperCard({
  paper,
  isSaved,
  isSaving,
  isUnsaving,
  isSelected,
  canSelect,
  selectionDisabled,
  saveDisabled,
  unsaveDisabled,
  onSelect,
  onSave,
  onUnsave,
  onToggleSelection,
}: {
  paper: ResearchPaper
  isSaved: boolean
  isSaving: boolean
  isUnsaving: boolean
  isSelected: boolean
  canSelect: boolean
  selectionDisabled: boolean
  saveDisabled: boolean
  unsaveDisabled: boolean
  onSelect: (paper: ResearchPaper) => void
  onSave: (paper: ResearchPaper) => void
  onUnsave: (openalexId: string) => void
  onToggleSelection: (paper: ResearchPaper) => void
}) {
  const doiUrl = paper.doi
    ? paper.doi.startsWith('http')
      ? paper.doi
      : `https://doi.org/${paper.doi}`
    : null

  return (
    <article className="paper-card">
      <div className="paper-card__header">
        <button className="paper-title-button" type="button" onClick={() => onSelect(paper)}>
          {paper.title || 'Untitled research paper'}
        </button>
        {paper.publication_year && <span className="year-chip">{paper.publication_year}</span>}
      </div>
      <label className="analysis-select">
        <input
          type="checkbox"
          checked={isSelected}
          disabled={!canSelect || (selectionDisabled && !isSelected)}
          onChange={() => onToggleSelection(paper)}
        />
        {isSelected ? 'Selected for analysis' : canSelect ? 'Select for analysis' : 'Save to select for analysis'}
      </label>

      <p className="authors">
        {formatAuthorPreview(paper.authors)}
      </p>

      <div className="paper-meta">
        {(paper.publication_date || paper.publication_year) && (
          <span>Published: {paper.publication_date || paper.publication_year}</span>
        )}
        {paper.citation_count !== null && paper.citation_count !== undefined && (
          <span>Citations: {paper.citation_count.toLocaleString()}</span>
        )}
        {paper.source_name && <span>Source: {paper.source_name}</span>}
      </div>

      {formatAbstractPreview(paper.abstract) && (
        <p className="abstract">{formatAbstractPreview(paper.abstract)}</p>
      )}

      <div className="paper-links">
        {isSaved ? (
          <button
            className="save-button"
            type="button"
            onClick={() => onUnsave(paper.id)}
            disabled={unsaveDisabled || isUnsaving}
          >
            {isUnsaving ? 'Unsaving…' : 'Unsave paper'}
          </button>
        ) : (
          <button
            className="save-button"
            type="button"
            onClick={() => onSave(paper)}
            disabled={saveDisabled || isSaving}
          >
            {isSaving ? 'Saving…' : 'Save paper'}
          </button>
        )}
        {doiUrl && (
          <a href={doiUrl} target="_blank" rel="noreferrer">
            View DOI
          </a>
        )}
        {paper.url && (
          <a href={paper.url} target="_blank" rel="noreferrer">
            View paper
          </a>
        )}
      </div>
    </article>
  )
}

export default ResearchSearchPage
