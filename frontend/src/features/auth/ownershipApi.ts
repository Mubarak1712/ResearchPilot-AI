import { authenticatedFetch } from './authApi'

export type UserSavedPaperOwnership = {
  id: number
  paper_id: number
  created_at: string
}

export type PaperOwnership = {
  paper_id: number
  is_saved: boolean
}

export type SavedPaperOwnership = {
  id: number
  openalex_id: string
  title: string
  authors: string[]
  publication_year: number | null
  abstract: string | null
  doi: string | null
  url: string | null
}

export class OwnershipApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function ownershipRequest<T>(
  token: string,
  path: string,
  init?: RequestInit,
  isValid?: (value: unknown) => value is T,
): Promise<T> {
  let response: Response
  try {
    response = await authenticatedFetch(token, path, init)
  } catch {
    throw new OwnershipApiError('Unable to reach the ownership service. Please try again.', 0)
  }

  if (!response.ok) {
    throw new OwnershipApiError('The ownership service rejected the request.', response.status)
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new OwnershipApiError('The ownership service returned an invalid response.', response.status)
  }

  if (!isValid || !isValid(payload)) {
    throw new OwnershipApiError('The ownership service returned an invalid response.', response.status)
  }

  return payload
}

export function savePaperOwnership(token: string, paperId: number): Promise<UserSavedPaperOwnership> {
  return ownershipRequest(
    token,
    `/api/v1/ownership/papers/${paperId}`,
    { method: 'POST' },
    isUserSavedPaperOwnership,
  )
}

export function unsavePaperOwnership(token: string, paperId: number): Promise<PaperOwnership> {
  return ownershipRequest(
    token,
    `/api/v1/ownership/papers/${paperId}`,
    { method: 'DELETE' },
    isPaperOwnership,
  )
}

export function getPaperOwnership(token: string, paperId: number): Promise<PaperOwnership> {
  return ownershipRequest(
    token,
    `/api/v1/ownership/papers/${paperId}`,
    undefined,
    isPaperOwnership,
  )
}

export function getSavedPaperOwnership(token: string): Promise<SavedPaperOwnership[]> {
  return ownershipRequest(
    token,
    '/api/v1/ownership/papers',
    undefined,
    isSavedPaperOwnershipList,
  )
}

function isUserSavedPaperOwnership(value: unknown): value is UserSavedPaperOwnership {
  return isRecord(value) && typeof value.id === 'number' && typeof value.paper_id === 'number' && typeof value.created_at === 'string'
}

function isPaperOwnership(value: unknown): value is PaperOwnership {
  return isRecord(value) && typeof value.paper_id === 'number' && typeof value.is_saved === 'boolean'
}

function isSavedPaperOwnership(value: unknown): value is SavedPaperOwnership {
  return (
    isRecord(value) &&
    typeof value.id === 'number' &&
    typeof value.openalex_id === 'string' &&
    typeof value.title === 'string' &&
    Array.isArray(value.authors) &&
    value.authors.every((author) => typeof author === 'string') &&
    (typeof value.publication_year === 'number' || value.publication_year === null) &&
    (typeof value.abstract === 'string' || value.abstract === null) &&
    (typeof value.doi === 'string' || value.doi === null) &&
    (typeof value.url === 'string' || value.url === null)
  )
}

function isSavedPaperOwnershipList(value: unknown): value is SavedPaperOwnership[] {
  return Array.isArray(value) && value.every(isSavedPaperOwnership)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
