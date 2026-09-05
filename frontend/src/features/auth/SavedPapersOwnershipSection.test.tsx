import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import SavedPapersOwnershipSection from './SavedPapersOwnershipSection'
import { useAuth } from './useAuth'
import { useOwnership } from './useOwnership'
import type { OwnershipState } from './useOwnership'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('./useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('./useOwnership', () => ({ useOwnership: vi.fn() }))

const paper = {
  id: 12,
  openalex_id: 'https://openalex.org/W12',
  title: 'Canonical saved paper',
  authors: ['Ada Lovelace'],
  publication_year: 2026,
  abstract: 'Canonical abstract',
  doi: 'https://doi.org/example',
  url: 'https://example.org/paper',
}

function authState(user: typeof paper | null = paper) {
  return {
    user: user ? { id: 1, email: 'ada@example.com', is_active: true, created_at: '', updated_at: '' } : null,
    accessToken: user ? 'token-a' : null,
    isInitializing: false,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }
}

function ownershipState(overrides: Partial<OwnershipState> = {}): OwnershipState {
  return { ...defaultOwnershipState(), ...overrides }
}

function defaultOwnershipState(): OwnershipState {
  return {
    savedPapers: [],
    isLoading: false,
    error: null,
    isPaperSaved: vi.fn(),
    checkPaperOwnership: vi.fn(),
    loadSavedPapers: vi.fn(),
    savePaper: vi.fn(),
    unsavePaper: vi.fn(),
  }
}

function render(user: typeof paper | null, ownership: ReturnType<typeof ownershipState>) {
  vi.mocked(useAuth).mockReturnValue(authState(user))
  vi.mocked(useOwnership).mockReturnValue(ownership)
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(createElement(MemoryRouter, null, createElement(SavedPapersOwnershipSection, { onSelect: vi.fn() }))))
  return { container, root }
}

describe('ownership-backed Saved Papers UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders the authenticated user list and canonical metadata', () => {
    const { container, root } = render(paper, ownershipState({ savedPapers: [paper] }))

    expect(container.textContent).toContain('Canonical saved paper')
    expect(container.textContent).toContain('Ada Lovelace')
    expect(container.textContent).toContain('Canonical abstract')
    expect(container.querySelector('a[href="https://doi.org/example"]')).not.toBeNull()
    act(() => root.unmount())
  })

  it('renders an explicit empty state', () => {
    const { container, root } = render(paper, ownershipState())

    expect(container.textContent).toContain('Papers you save will appear here.')
    act(() => root.unmount())
  })

  it('renders loading state', () => {
    const { container, root } = render(paper, ownershipState({ isLoading: true }))

    expect(container.textContent).toContain('Loading your saved papers…')
    act(() => root.unmount())
  })

  it('renders ownership API errors safely', () => {
    const { container, root } = render(paper, ownershipState({ error: new Error('Ownership unavailable') }))

    expect(container.querySelector('[role="alert"]')?.textContent).toBe('Ownership unavailable')
    act(() => root.unmount())
  })

  it('renders an unauthenticated state without ownership data', () => {
    const { container, root } = render(null, ownershipState({ savedPapers: [paper] }))

    expect(container.textContent).toContain('Sign in to view your saved papers.')
    expect(container.textContent).not.toContain('Canonical saved paper')
    act(() => root.unmount())
  })

  it('uses the ownership hook unsave action for the displayed paper', async () => {
    const unsavePaper = vi.fn().mockResolvedValue(undefined)
    const { container, root } = render(paper, ownershipState({ savedPapers: [paper], unsavePaper }))

    await act(async () => {
      container.querySelector('.save-button')?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(unsavePaper).toHaveBeenCalledWith(paper.id)
    act(() => root.unmount())
  })

  it('renders only the ownership list supplied for the authenticated user', () => {
    const { container, root } = render(paper, ownershipState({ savedPapers: [paper] }))

    expect(container.querySelectorAll('.paper-card')).toHaveLength(1)
    act(() => root.unmount())
  })
})
