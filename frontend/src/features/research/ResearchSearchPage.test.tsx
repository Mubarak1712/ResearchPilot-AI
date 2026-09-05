import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import ResearchSearchPage from './ResearchSearchPage'
import { useAuth } from '../auth/useAuth'
import { useOwnership } from '../auth/useOwnership'
import { savePaper as saveLegacyPaper, searchResearch, unsavePaper as unsaveLegacyPaper } from './researchApi'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../auth/useOwnership', () => ({ useOwnership: vi.fn() }))
vi.mock('./researchApi', async () => {
  const actual = await vi.importActual<typeof import('./researchApi')>('./researchApi')
  return {
    ...actual,
    searchResearch: vi.fn(),
    savePaper: vi.fn(),
    unsavePaper: vi.fn(),
  }
})

const paper = {
  id: 'https://openalex.org/W12',
  title: 'Canonical research result',
  authors: ['Ada Lovelace'],
  publication_year: 2026,
  abstract: 'Canonical abstract',
  doi: 'https://doi.org/example',
  url: 'https://example.org/paper',
  publication_date: '2026-01-01',
  citation_count: 7,
  source_name: 'OpenAlex',
}

const authState = {
  user: { id: 1, email: 'ada@example.com', is_active: true, created_at: '', updated_at: '' },
  accessToken: 'token-a',
  isInitializing: false,
  error: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function mount() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(createElement(MemoryRouter, null, createElement(ResearchSearchPage))))
  return { container, root }
}

async function settle() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('research result save/unsave ownership integration', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '?q=ai')
    vi.clearAllMocks()
    vi.mocked(searchResearch).mockResolvedValue({
      query: 'ai',
      total: 1,
      page: 1,
      limit: 10,
      sort: 'relevance',
      results: [paper],
    })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('saves a research result through the authenticated ownership hook using the canonical numeric paper id', async () => {
    const ownershipSave = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({ ...authState })
    const loadSaved = vi.fn()
    vi.mocked(useOwnership).mockReturnValue({
      savedPapers: [],
      isLoading: false,
      error: null,
      isPaperSaved: vi.fn().mockReturnValue(false),
      checkPaperOwnership: vi.fn(),
      loadSavedPapers: loadSaved,
      savePaper: ownershipSave,
      unsavePaper: vi.fn(),
    })
    vi.mocked(saveLegacyPaper).mockResolvedValue({
      id: 42,
      openalex_id: paper.id,
      title: paper.title,
      authors: paper.authors,
      publication_year: paper.publication_year,
      abstract: paper.abstract,
      doi: paper.doi,
      url: paper.url,
      created_at: '2026-08-23T00:00:00Z',
      updated_at: '2026-08-23T00:00:00Z',
    })

    const { container, root } = mount()
    await settle()

    const button = container.querySelector('.save-button')
    expect(button).not.toBeNull()
    await act(async () => {
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(saveLegacyPaper).toHaveBeenCalledWith(paper.id)
    expect(ownershipSave).toHaveBeenCalledWith(42)
    expect(loadSaved).toHaveBeenCalled()
    act(() => root.unmount())
  })

  it('unsaves a research result through the authenticated ownership hook using the canonical numeric paper id', async () => {
    const ownershipUnsave = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({ ...authState })
    const loadSaved2 = vi.fn()
    vi.mocked(useOwnership).mockReturnValue({
      savedPapers: [{
        id: 42,
        openalex_id: paper.id,
        title: paper.title,
        authors: paper.authors,
        publication_year: paper.publication_year,
        abstract: paper.abstract,
        doi: paper.doi,
        url: paper.url,
      }],
      isLoading: false,
      error: null,
      isPaperSaved: vi.fn().mockReturnValue(true),
      checkPaperOwnership: vi.fn(),
      loadSavedPapers: loadSaved2,
      savePaper: vi.fn(),
      unsavePaper: ownershipUnsave,
    })

    const { container, root } = mount()
    await settle()

    const button = container.querySelector('.save-button')
    expect(button).not.toBeNull()
    await act(async () => {
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(ownershipUnsave).toHaveBeenCalledWith(42)
    expect(loadSaved2).toHaveBeenCalled()
    expect(unsaveLegacyPaper).not.toHaveBeenCalled()
    act(() => root.unmount())
  })

  it('does not call ownership actions while unauthenticated', async () => {
    const ownershipSave = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({
      ...authState,
      accessToken: null,
      user: null,
    })
    const loadSaved3 = vi.fn()
    vi.mocked(useOwnership).mockReturnValue({
      savedPapers: [],
      isLoading: false,
      error: null,
      isPaperSaved: vi.fn().mockReturnValue(false),
      checkPaperOwnership: vi.fn(),
      loadSavedPapers: loadSaved3,
      savePaper: ownershipSave,
      unsavePaper: vi.fn(),
    })

    const { container, root } = mount()
    await settle()

    const button = container.querySelector('.save-button')
    expect(button).not.toBeNull()
    expect(button instanceof HTMLButtonElement ? button.disabled : false).toBe(true)
    await act(async () => {
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(ownershipSave).not.toHaveBeenCalled()
    expect(saveLegacyPaper).not.toHaveBeenCalled()
    act(() => root.unmount())
  })

  it('renders search results without regressing the legacy search flow', async () => {
    vi.mocked(useAuth).mockReturnValue({ ...authState })
    vi.mocked(useOwnership).mockReturnValue({
      savedPapers: [],
      isLoading: false,
      error: null,
      isPaperSaved: vi.fn().mockReturnValue(false),
      checkPaperOwnership: vi.fn(),
      loadSavedPapers: vi.fn(),
      savePaper: vi.fn(),
      unsavePaper: vi.fn(),
    })

    const { container, root } = mount()
    await settle()

    expect(container.textContent).toContain('Canonical research result')
    expect(searchResearch).toHaveBeenCalled()
    act(() => root.unmount())
  })
})
