export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'

export type EvidenceType =
  | 'paper_metadata'
  | 'abstract'
  | 'limitation'
  | 'future_work'
  | 'methodology'
  | 'population_context'
  | 'outcome'
  | 'comparison'
  | 'dataset'
  | 'temporal'
  | 'contradiction'
  | 'topic'
  | 'finding'

export type GapCategory =
  | 'topic_underrepresentation'
  | 'population_context'
  | 'methodology'
  | 'dataset'
  | 'temporal'
  | 'missing_comparison'
  | 'missing_outcome'
  | 'conflicting_evidence'
  | 'future_work'
  | 'replication'
  | 'other'
  | 'insufficient_evidence'
  | 'imprecise_evidence'
  | 'methodological_limitation'
  | 'inconsistent_evidence'
  | 'population_gap'
  | 'intervention_or_method_gap'
  | 'comparison_gap'
  | 'outcome_gap'
  | 'setting_or_context_gap'
  | 'validation_gap'

export type AnalysisEvidence = {
  id: number
  paper_id: number
  evidence_type: EvidenceType
  claim: string
  source_excerpt: string | null
  source_field: string | null
  confidence: number
  extraction_method: string
  confidence_semantics?: string
  evidence_status?: string
  interpretation?: string
}

export type AnalysisGap = {
  id: string
  category: GapCategory
  statement: string
  observed_evidence: string[]
  pattern?: string
  inference: string
  confidence: number
  confidence_breakdown?: {
    explicit_evidence?: number
    independent_papers?: number
    cross_paper_consistency?: number
    specificity?: number
    inference_penalty?: number
    corpus_size_penalty?: number
  }
  supporting_paper_ids: number[]
  limitations: { items: string[] }
}

export type LlmInterpretation =
  | {
      status: 'completed'
      provider: string
      model: string
      prompt_version: string
      interpretations: Array<{
        gap_id: string
        interpretation: string
        rationale: string
        confidence: number
        supporting_paper_ids: number[]
        evidence_claims: string[]
        limitations: string[]
      }>
      reason: string | null
    }
  | {
      status: 'unavailable'
      provider?: string
      model?: string
      prompt_version?: string
      interpretations: []
      reason: string
    }

export type Analysis = {
  analysis_id: number
  status: AnalysisStatus
  methodology_version: string
  paper_count: number
  paper_ids: number[]
  papers?: AnalysisPaper[]
  research_question?: string | null
  evidence: AnalysisEvidence[]
  candidate_gaps: AnalysisGap[]
  limitations: { items: string[] }
  key_themes?: KeyTheme[]
  corpus_coherence?: CorpusCoherence | null
  llm_interpretation?: LlmInterpretation | null
}

export type AnalysisPaper = {
  paper_id: number
  openalex_id?: string | null
  title: string | null
  authors: string[]
  publication_year: number | null
  abstract: string | null
  doi?: string | null
  url?: string | null
}

export type KeyTheme = {
  phrase: string
  normalized_phrase: string
  supporting_paper_ids: number[]
  paper_count: number
  occurrence_count: number
  score: number
}

export type CorpusCoherence = {
  status: string
  summary: string
  dominant_cluster: string | null
}
