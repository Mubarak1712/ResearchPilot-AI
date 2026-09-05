import { authenticatedFetch } from '../auth/authApi'
import type { Analysis } from './types'

export class AnalysisApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }
}

export type CreateAnalysisRequest = {
  paper_ids: number[]
  research_question?: string
  framework?: string
  options?: {
    include_llm_interpretation?: boolean
    minimum_confidence?: number
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = 'Unable to load the analysis. Please try again.'
    try {
      const body: unknown = await response.json()
      if (typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // Use the safe status-specific fallback.
    }
    if (response.status === 401) detail = 'Your session has expired. Please sign in again.'
    if (response.status === 403) detail = 'You do not have access to this analysis.'
    if (response.status === 404) detail = 'Analysis not found.'
    throw new AnalysisApiError(detail, response.status)
  }
  try {
    return (await response.json()) as T
  } catch {
    throw new AnalysisApiError('The analysis service returned an invalid response.', response.status)
  }
}

export async function createAnalysis(token: string, request: CreateAnalysisRequest): Promise<Analysis> {
  try {
    const response = await authenticatedFetch(token, '/api/v1/analyses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    return await parseResponse<Analysis>(response)
  } catch (error) {
    if (error instanceof AnalysisApiError) throw error
    throw new AnalysisApiError('Unable to reach the analysis service. Please try again.')
  }
}

export async function getAnalysis(token: string, analysisId: string): Promise<Analysis> {
  try {
    return await parseResponse<Analysis>(
      await authenticatedFetch(token, `/api/v1/analyses/${encodeURIComponent(analysisId)}`),
    )
  } catch (error) {
    if (error instanceof AnalysisApiError) throw error
    throw new AnalysisApiError('Unable to reach the analysis service. Please try again.')
  }
}
