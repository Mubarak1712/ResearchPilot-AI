import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getPaperOwnership,
  getSavedPaperOwnership,
  OwnershipApiError,
  savePaperOwnership,
  unsavePaperOwnership,
} from './ownershipApi'

const ownership = { id: 3, paper_id: 12, created_at: '2026-08-23T00:00:00Z' }
const status = { paper_id: 12, is_saved: true }
const paper = {
  id: 12,
  openalex_id: 'https://openalex.org/W12',
  title: 'Canonical paper',
  authors: ['Ada Lovelace'],
  publication_year: 2026,
  abstract: 'Abstract',
  doi: null,
  url: 'https://example.org/paper',
}

function mockResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('ownership API adapter', () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.restoreAllMocks())

  it('saves with the authenticated bearer token and no user id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse(ownership))

    const result = await savePaperOwnership('token-a', 12)

    expect(result).toEqual(ownership)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ownership/papers/12', {
      method: 'POST',
      headers: { Authorization: 'Bearer token-a' },
    })
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain('user_id')
  })

  it('unsaves with the authenticated bearer token', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse({ ...status, is_saved: false }))

    await expect(unsavePaperOwnership('token-a', 12)).resolves.toEqual({ paper_id: 12, is_saved: false })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/ownership/papers/12')
    expect(fetchMock.mock.calls[0][1]).toEqual({ method: 'DELETE', headers: { Authorization: 'Bearer token-a' } })
  })

  it('checks ownership and maps the response contract', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse(status))

    await expect(getPaperOwnership('token-a', 12)).resolves.toEqual(status)
    expect(fetchMock.mock.calls[0][1]).toEqual({ headers: { Authorization: 'Bearer token-a' } })
  })

  it('lists canonical saved-paper metadata for the authenticated user', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse([paper]))

    await expect(getSavedPaperOwnership('token-a')).resolves.toEqual([paper])
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ownership/papers', {
      headers: { Authorization: 'Bearer token-a' },
    })
  })

  it('preserves server 401 and 404 statuses', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(mockResponse({ detail: 'unauthorized' }, 401))
      .mockResolvedValueOnce(mockResponse({ detail: 'missing' }, 404))

    await expect(getSavedPaperOwnership('token-a')).rejects.toMatchObject({ status: 401 })
    await expect(getPaperOwnership('token-a', 999)).rejects.toMatchObject({ status: 404 })
  })

  it('rejects malformed ownership responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse({ paper_id: '12', is_saved: true }))

    await expect(getPaperOwnership('token-a', 12)).rejects.toBeInstanceOf(OwnershipApiError)
  })
})
