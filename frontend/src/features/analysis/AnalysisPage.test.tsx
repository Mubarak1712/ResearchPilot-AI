import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AnalysisPage from './AnalysisPage'
import { getAnalysis } from './analysisApi'
import { useAuth } from '../auth/useAuth'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('./analysisApi', () => ({ AnalysisApiError: class extends Error {}, getAnalysis: vi.fn() }))

const authState = {
  user: { id: 1, email: 'researcher@example.com', is_active: true, created_at: '', updated_at: '' },
  accessToken: 'token',
  isInitializing: false,
  error: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

const baseAnalysis = {
  analysis_id: 5,
  status: 'completed' as const,
  methodology_version: '5C-5E-deterministic-v1',
  paper_count: 2,
  paper_ids: [206, 215],
  evidence: [
    { id: 1, paper_id: 206, evidence_type: 'methodology' as const, claim: 'Explicit methodology signal: E prover', source_excerpt: 'A very long supporting excerpt '.repeat(30), source_field: 'abstract', confidence: 0.95, extraction_method: 'deterministic_rule' },
    { id: 2, paper_id: 206, evidence_type: 'topic' as const, claim: 'Topic phrase: automated prover', source_excerpt: 'Topic excerpt', source_field: 'abstract', confidence: 0.82, extraction_method: 'deterministic_rule' },
  ],
  candidate_gaps: [],
  limitations: { items: ['Analysis is based on the selected corpus only.'] },
  key_themes: [{ phrase: 'automated prover are', normalized_phrase: 'automated prover are', supporting_paper_ids: [206], paper_count: 1, occurrence_count: 1, score: 1 }],
  corpus_coherence: { status: 'low', summary: 'The selected papers investigate substantially different research problems, methods, and outcomes.', dominant_cluster: 'automated prover' },
}

function mount() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(createElement(
    MemoryRouter,
    { initialEntries: ['/analysis/5'] },
    createElement(Routes, null, createElement(Route, { path: '/analysis/:id', element: createElement(AnalysisPage) })),
  )))
  return { container, root }
}

async function settle() {
  await act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, 0))
  })
}

describe('research analysis presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(authState)
    vi.mocked(getAnalysis).mockResolvedValue(baseAnalysis)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows a calm zero-gap summary for a low-coherence corpus', async () => {
    const { container, root } = mount()
    await settle()
    expect(container.textContent).toContain('No research gap could be established')
    expect(container.textContent).toContain('Low')
    expect(container.textContent).toContain('different research problems')
    root.unmount()
  })

  it('keeps topic phrases out of the primary per-paper evidence view', async () => {
    const { container, root } = mount()
    await settle()
    const evidenceItem = container.querySelector('.paper-evidence-item')
    expect(evidenceItem).not.toBeNull()
    expect(evidenceItem?.textContent ?? '').toContain('E prover')
    expect(evidenceItem?.textContent ?? '').not.toContain('Topic phrase')
    expect(container.textContent).toContain('No meaningful cross-paper recurring themes were identified.')
    root.unmount()
  })

  it('keeps methodology collapsed and evidence expandable by default', async () => {
    const { container, root } = mount()
    await settle()
    expect(container.querySelector('.methodology-details')).not.toBeNull()
    expect(container.querySelector('.methodology-details')?.hasAttribute('open')).toBe(false)
    expect(container.querySelector('.raw-evidence')?.hasAttribute('open')).toBe(false)
    expect(container.querySelector('.evidence-excerpt')?.hasAttribute('open')).toBe(false)
    expect(container.textContent).toContain('Show more')
    root.unmount()
  })

  it('renders defensible gap candidates with confidence reasoning and evidence', async () => {
    vi.mocked(getAnalysis).mockResolvedValue({
      ...baseAnalysis,
      candidate_gaps: [{
        id: 'gap-1',
        category: 'validation_gap',
        statement: 'Validation remains unresolved across the selected papers.',
        observed_evidence: ['Explicit limitation: validation was limited.'],
        pattern: 'Multiple papers report limited validation.',
        inference: 'The selected evidence does not establish robust validation.',
        confidence: 0.72,
        confidence_breakdown: { explicit_evidence: 1, independent_papers: 1, cross_paper_consistency: 1, specificity: 0.8, inference_penalty: 0, corpus_size_penalty: 0.1 },
        supporting_paper_ids: [206],
        limitations: { items: [] },
      }],
      evidence: [{ ...baseAnalysis.evidence[0], claim: 'Explicit limitation: validation was limited.' }],
    })
    const { container, root } = mount()
    await settle()
    expect(container.textContent).toContain('Potential research gap')
    expect(container.textContent).toContain('72%')
    expect(container.textContent).toContain('View confidence reasoning')
    expect(container.textContent).toContain('View supporting evidence')
    root.unmount()
  })
})
