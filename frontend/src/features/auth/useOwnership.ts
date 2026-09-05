import { useCallback, useEffect, useRef, useState } from 'react'

import { useAuth } from './useAuth'
import {
  getPaperOwnership,
  getSavedPaperOwnership,
  OwnershipApiError,
  savePaperOwnership,
  type SavedPaperOwnership,
  unsavePaperOwnership,
} from './ownershipApi'

export class OwnershipStateError extends Error {}

export type OwnershipState = {
  savedPapers: SavedPaperOwnership[]
  isLoading: boolean
  error: OwnershipApiError | OwnershipStateError | null
  isPaperSaved: (paperId: number) => boolean
  checkPaperOwnership: (paperId: number) => Promise<boolean>
  loadSavedPapers: () => Promise<SavedPaperOwnership[]>
  savePaper: (paperId: number) => Promise<void>
  unsavePaper: (paperId: number) => Promise<void>
}

export function useOwnership(): OwnershipState {
  const { accessToken, isInitializing } = useAuth()
  const [savedPapers, setSavedPapers] = useState<SavedPaperOwnership[]>([])
  const [savedPaperIds, setSavedPaperIds] = useState<Set<number>>(() => new Set())
  const [stateToken, setStateToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<OwnershipApiError | OwnershipStateError | null>(null)
  const activeToken = useRef(accessToken)
  const requestSequence = useRef(0)
  activeToken.current = accessToken

  function isCurrentRequest(sequence: number, token: string) {
    return sequence === requestSequence.current && token === activeToken.current
  }

  const loadSavedPapers = useCallback(async () => {
    if (!accessToken) {
      setSavedPapers([])
      setSavedPaperIds(new Set())
      setStateToken(null)
      return []
    }

    const sequence = ++requestSequence.current
    setStateToken(accessToken)
    setIsLoading(true)
    setError(null)
    try {
      const papers = await getSavedPaperOwnership(accessToken)
      if (isCurrentRequest(sequence, accessToken)) {
        setSavedPapers(papers)
        setSavedPaperIds(new Set(papers.map((paper) => paper.id)))
      }
      return papers
    } catch (caughtError) {
      const normalizedError = normalizeError(caughtError)
      if (isCurrentRequest(sequence, accessToken)) {
        setError(normalizedError)
      }
      throw caughtError
    } finally {
      if (isCurrentRequest(sequence, accessToken)) {
        setIsLoading(false)
      }
    }
  }, [accessToken])

  useEffect(() => {
    if (isInitializing) {
      return
    }

    if (!accessToken) {
      ++requestSequence.current
      setSavedPapers([])
      setSavedPaperIds(new Set())
      setStateToken(null)
      setIsLoading(false)
      setError(null)
      return
    }

    void loadSavedPapers().catch(() => undefined)
  }, [accessToken, isInitializing, loadSavedPapers])

  async function checkPaperOwnership(paperId: number) {
    if (!accessToken) {
      setError(null)
      return false
    }

    setIsLoading(true)
    setError(null)
    try {
      const ownership = await getPaperOwnership(accessToken, paperId)
      updateSavedPaperId(paperId, ownership.is_saved, accessToken)
      return ownership.is_saved
    } catch (caughtError) {
      const normalizedError = normalizeError(caughtError)
      setError(normalizedError)
      throw caughtError
    } finally {
      setIsLoading(false)
    }
  }

  async function savePaper(paperId: number) {
    if (!accessToken) {
      const unauthenticatedError = new OwnershipStateError('Authentication is required to save a paper.')
      setError(unauthenticatedError)
      throw unauthenticatedError
    }

    setIsLoading(true)
    setError(null)
    try {
      await savePaperOwnership(accessToken, paperId)
      updateSavedPaperId(paperId, true, accessToken)
    } catch (caughtError) {
      const normalizedError = normalizeError(caughtError)
      setError(normalizedError)
      throw caughtError
    } finally {
      setIsLoading(false)
    }
  }

  async function unsavePaper(paperId: number) {
    if (!accessToken) {
      const unauthenticatedError = new OwnershipStateError('Authentication is required to unsave a paper.')
      setError(unauthenticatedError)
      throw unauthenticatedError
    }

    setIsLoading(true)
    setError(null)
    try {
      await unsavePaperOwnership(accessToken, paperId)
      updateSavedPaperId(paperId, false, accessToken)
    } catch (caughtError) {
      const normalizedError = normalizeError(caughtError)
      setError(normalizedError)
      throw caughtError
    } finally {
      setIsLoading(false)
    }
  }

  function updateSavedPaperId(paperId: number, isSaved: boolean, token: string) {
    if (activeToken.current !== token) {
      return
    }
    setSavedPaperIds((current) => {
      const next = new Set(current)
      if (isSaved) {
        next.add(paperId)
      } else {
        next.delete(paperId)
      }
      return next
    })
    if (!isSaved) {
      setSavedPapers((current) => current.filter((paper) => paper.id !== paperId))
    }
  }

  return {
    savedPapers: stateToken === accessToken ? savedPapers : [],
    isLoading,
    error,
    isPaperSaved: (paperId) => stateToken === accessToken && savedPaperIds.has(paperId),
    checkPaperOwnership,
    loadSavedPapers,
    savePaper,
    unsavePaper,
  }
}

function normalizeError(caughtError: unknown): OwnershipApiError | OwnershipStateError {
  return caughtError instanceof OwnershipApiError
    ? caughtError
    : new OwnershipStateError('Unable to update paper ownership.')
}
