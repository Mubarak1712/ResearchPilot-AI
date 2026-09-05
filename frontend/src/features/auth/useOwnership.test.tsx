import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext } from './context'
import { OwnershipApiError } from './ownershipApi'
import {
  getPaperOwnership,
  getSavedPaperOwnership,
  savePaperOwnership,
  unsavePaperOwnership,
} from './ownershipApi'
import { useOwnership } from './useOwnership'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('./ownershipApi', async () => {
  const actual = await vi.importActual<typeof import('./ownershipApi')>('./ownershipApi')
  return {
    ...actual,
    getPaperOwnership: vi.fn(),
    getSavedPaperOwnership: vi.fn(),
    savePaperOwnership: vi.fn(),
    unsavePaperOwnership: vi.fn(),
  }
})

const user = {
  id: 1,
  email: 'ada@example.com',
  is_active: true,
  created_at: '2026-08-23T00:00:00Z',
  updated_at: '2026-08-23T00:00:00Z',
}
const savedPaper = {
  id: 12,
  openalex_id: 'https://openalex.org/W12',
  title: 'Saved paper',
  authors: ['Ada Lovelace'],
  publication_year: 2026,
  abstract: 'Abstract',
  doi: null,
  url: null,
}
const secondSavedPaper = { ...savedPaper, id: 24, openalex_id: 'https://openalex.org/W24' }

function authValue(accessToken: string | null) {
  return {
    user: accessToken ? user : null,
    accessToken,
    isInitializing: false,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }
}

function Probe({ onState }: { onState: (state: ReturnType<typeof useOwnership>) => void }) {
  onState(useOwnership())
  return null
}

function mount(accessToken: string | null, onState: (state: ReturnType<typeof useOwnership>) => void) {
  const container = document.createElement('div')
  const root = createRoot(container)
  function render(nextAccessToken: string | null) {
    act(() => {
      root.render(createElement(AuthContext.Provider, { value: authValue(nextAccessToken) }, createElement(Probe, { onState })))
    })
  }
  render(accessToken)
  return { root, container, render }
}

async function settle() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('ownership state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSavedPaperOwnership).mockResolvedValue([])
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('loads the authenticated saved-paper list and exposes ownership checks', async () => {
    vi.mocked(getSavedPaperOwnership).mockResolvedValue([savedPaper])
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })
    await settle()

    expect(state.savedPapers).toEqual([savedPaper])
    expect(state.isPaperSaved(12)).toBe(true)
    expect(getSavedPaperOwnership).toHaveBeenCalledWith('token-a')
    act(() => root.unmount())
  })

  it('checks ownership through the authenticated adapter', async () => {
    vi.mocked(getPaperOwnership).mockResolvedValue({ paper_id: 12, is_saved: true })
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })
    await settle()

    await act(async () => { await expect(state.checkPaperOwnership(12)).resolves.toBe(true) })
    expect(getPaperOwnership).toHaveBeenCalledWith('token-a', 12)
    expect(state.isPaperSaved(12)).toBe(true)
    act(() => root.unmount())
  })

  it('saves and updates ownership state', async () => {
    vi.mocked(savePaperOwnership).mockResolvedValue({ id: 4, paper_id: 12, created_at: '2026-08-23T00:00:00Z' })
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })
    await settle()

    await act(async () => { await state.savePaper(12) })
    expect(savePaperOwnership).toHaveBeenCalledWith('token-a', 12)
    expect(state.isPaperSaved(12)).toBe(true)
    act(() => root.unmount())
  })

  it('unsaves and updates ownership state', async () => {
    vi.mocked(getSavedPaperOwnership).mockResolvedValue([savedPaper])
    vi.mocked(unsavePaperOwnership).mockResolvedValue({ paper_id: 12, is_saved: false })
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })
    await settle()

    await act(async () => { await state.unsavePaper(12) })
    expect(unsavePaperOwnership).toHaveBeenCalledWith('token-a', 12)
    expect(state.isPaperSaved(12)).toBe(false)
    expect(state.savedPapers).toEqual([])
    act(() => root.unmount())
  })

  it('keeps unauthenticated state empty and makes no ownership requests', async () => {
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount(null, (nextState) => { state = nextState })
    await settle()

    expect(state.savedPapers).toEqual([])
    expect(state.isPaperSaved(12)).toBe(false)
    await expect(state.checkPaperOwnership(12)).resolves.toBe(false)
    expect(getSavedPaperOwnership).not.toHaveBeenCalled()
    expect(getPaperOwnership).not.toHaveBeenCalled()
    act(() => root.unmount())
  })

  it('exposes loading while the saved-paper list is pending', async () => {
    let resolveList!: (papers: typeof savedPaper[]) => void
    vi.mocked(getSavedPaperOwnership).mockReturnValue(new Promise((resolve) => { resolveList = resolve }))
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })

    await act(async () => { await Promise.resolve() })
    expect(state.isLoading).toBe(true)
    await act(async () => { resolveList([]); await Promise.resolve() })
    expect(state.isLoading).toBe(false)
    act(() => root.unmount())
  })

  it('propagates API errors and records them', async () => {
    const error = new OwnershipApiError('Unauthorized', 401)
    vi.mocked(getSavedPaperOwnership).mockRejectedValue(error)
    let state!: ReturnType<typeof useOwnership>
    const { root } = mount('token-a', (nextState) => { state = nextState })

    await expect(settle()).resolves.toBeUndefined()
    expect(state.error).toBe(error)
    await expect(state.loadSavedPapers()).rejects.toBe(error)
    act(() => root.unmount())
  })

  it('hides prior identity state and ignores a late previous-user list response', async () => {
    let resolveFirst!: (papers: typeof savedPaper[]) => void
    let resolveSecond!: (papers: typeof savedPaper[]) => void
    vi.mocked(getSavedPaperOwnership)
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecond = resolve }))
    let state!: ReturnType<typeof useOwnership>
    const { root, render } = mount('token-a', (nextState) => { state = nextState })

    await act(async () => { await Promise.resolve() })
    render('token-b')
    expect(state.savedPapers).toEqual([])
    expect(state.isPaperSaved(12)).toBe(false)

    await act(async () => { resolveSecond([secondSavedPaper]); await Promise.resolve() })
    expect(state.savedPapers).toEqual([secondSavedPaper])
    resolveFirst([savedPaper])
    await settle()
    expect(state.savedPapers).toEqual([secondSavedPaper])
    expect(state.isPaperSaved(12)).toBe(false)
    act(() => root.unmount())
  })
})
