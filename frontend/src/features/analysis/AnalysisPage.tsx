import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { AnalysisApiError, getAnalysis } from './analysisApi'
import type { Analysis, AnalysisEvidence, AnalysisGap, AnalysisPaper } from './types'
import './AnalysisPage.css'

function titleLabel(value: string) {
  return value.replaceAll('_', ' ').replace(/^\w/, (character) => character.toUpperCase())
}

function evidenceLabel(item: AnalysisEvidence) {
  if (item.evidence_type === 'finding') return 'Reported finding'
  if (item.evidence_type === 'future_work') return 'Author-stated future work'
  if (item.evidence_type === 'outcome') return 'Evaluation outcome'
  return titleLabel(item.evidence_type)
}

function excerpt(text: string | null, fallback: string) {
  return text || fallback
}

function EvidenceExcerpt({ text }: { text: string }) {
  return <details className="evidence-excerpt"><summary>Show more</summary><q>{text}</q></details>
}

function EvidenceCard({ item, paper }: { item: AnalysisEvidence; paper?: AnalysisPaper }) {
  return <article className={`evidence-card evidence-${item.evidence_type}`}>
    <div className="evidence-card-top"><span className="evidence-kind">{evidenceLabel(item)}</span><span className="evidence-status">{item.evidence_status === 'finding' ? 'Result reported' : 'Text signal'}</span></div>
    <h3>{item.claim.replace(/^Detected [^:]+ signal: /, '')}</h3>
    <p className="evidence-interpretation">{item.interpretation || 'A research element was identified in the available text.'}</p>
    <p className="evidence-source"><strong>Source:</strong> {paper?.title || `Paper ${item.paper_id}`}</p>
    <EvidenceExcerpt text={excerpt(item.source_excerpt, item.claim)} />
    <small>Extraction confidence: {Math.round(item.confidence * 100)}% ({item.confidence_semantics === 'rule_match' ? 'rule-match confidence, not scientific certainty' : 'deterministic extraction'})</small>
  </article>
}

function PaperCard({ paper, evidence }: { paper: AnalysisPaper; evidence: AnalysisEvidence[] }) {
  const groups: Array<[string, string[]]> = [
    ['Detected topic evidence', ['topic', 'population_context']],
    ['Method / approach', ['methodology']],
    ['Dataset / corpus', ['dataset']],
    ['Evaluation / outcome', ['outcome', 'comparison', 'finding']],
    ['Reported finding', ['finding']],
    ['Limitation', ['limitation']],
    ['Author-stated future work', ['future_work']],
  ]
  return <article className="paper-card">
    <div className="paper-heading"><div><p className="eyebrow">Selected paper</p><h3>{paper.title || `Paper ${paper.paper_id}`}</h3><p className="paper-meta">{paper.authors.length > 0 ? paper.authors.join(', ') : 'Authors not identified'}{paper.publication_year ? ` · ${paper.publication_year}` : ''}</p></div><Link to={`/papers/${paper.paper_id}`} state={{ paper: { id: paper.paper_id, openalex_id: paper.openalex_id || String(paper.paper_id), title: paper.title || '', authors: paper.authors, publication_year: paper.publication_year, abstract: paper.abstract, doi: paper.doi || null, url: paper.url || null } }}>View paper</Link></div>
    <div className="paper-facts">{groups.map(([name, types]) => {
      const matches = evidence.filter((item) => types.includes(item.evidence_type))
      return <div className="paper-fact" key={name}><strong>{name}</strong>{matches.length > 0 ? matches.map((item) => <span className={item.evidence_type === 'topic' ? 'paper-topic-item' : 'paper-evidence-item'} key={item.id}>{item.claim.replace(/^Topic phrase: /, '')}</span>) : <span className="missing">Not identified in the available text.</span>}</div>
    })}</div><p className="paper-identity">OpenAlex: {paper.openalex_id || 'Not available'}{paper.doi ? ` · DOI: ${paper.doi}` : ''}</p><details className="raw-evidence"><summary>View source evidence</summary><p className="analysis-note">{paper.abstract || 'The original abstract is not available in this response.'}</p></details>
  </article>
}

function ExecutiveSummary({ analysis }: { analysis: Analysis }) {
  const coherence = analysis.corpus_coherence
  const onePaper = analysis.paper_count === 1
  const hasGap = analysis.candidate_gaps.length > 0
  const text = hasGap
    ? 'The selected papers provide evidence supporting one or more candidate issues. These are corpus-limited assessments, not field-wide conclusions.'
    : onePaper
      ? 'The selected paper provides traceable evidence, but cross-paper gap assessment is unavailable because only one paper was selected.'
      : coherence?.status === 'low'
        ? 'The selected papers provide evidence from different research contexts. Their problems, methods, or evaluation settings are not sufficiently comparable for a defensible shared gap.'
        : 'The selected papers provide useful evidence, but no specific unresolved issue is supported by enough comparable evidence in this corpus.'
  return <section className="executive-summary"><p className="eyebrow">Executive summary</p><h2>What can be concluded?</h2><p>{text}</p>{analysis.research_question ? <div className="question-callout"><strong>Research question</strong><p>{analysis.research_question}</p><small>Lexical overlap detected; this does not establish semantic alignment.</small></div> : <p className="analysis-note">No research question was supplied. Gap assessment is therefore based on relationships among the selected papers rather than semantic alignment to a user-defined question.</p>}</section>
}

function FindingsSection({ analysis, papersById }: { analysis: Analysis; papersById: Map<number, AnalysisPaper> }) {
  const findings = analysis.evidence.filter((item) => item.evidence_type === 'finding')
  return <section className="analysis-section" aria-labelledby="findings-title"><p className="eyebrow">Results grounded in source text</p><h2 id="findings-title">What did the papers actually find?</h2><p className="section-intro">Only explicit reported results appear here. Measurements, methods, and topic mentions remain evidence signals rather than findings.</p>{findings.length > 0 ? <div className="finding-grid">{findings.map((item) => <EvidenceCard item={item} paper={papersById.get(item.paper_id)} key={item.id} />)}</div> : <div className="empty-panel"><h3>No findings extracted</h3><p>No available excerpt matched a clear reported-result rule. This does not prove that the papers contain no findings.</p></div>}</section>
}

function EvidenceSummary({ analysis, papersById }: { analysis: Analysis; papersById: Map<number, AnalysisPaper> }) {
  const categories: Array<[string, string[]]> = [['Detected topic evidence', ['topic', 'population_context']], ['Method', ['methodology']], ['Dataset / population', ['dataset', 'population_context']], ['Evaluation / outcome', ['outcome', 'comparison', 'finding']], ['Reported findings', ['finding']], ['Limitations', ['limitation']], ['Author-stated future work', ['future_work']]]
  return <section className="analysis-section" aria-labelledby="summary-title"><p className="eyebrow">Traceable evidence</p><h2 id="summary-title">Evidence summary</h2><div className="evidence-summary-grid">{categories.map(([name, types]) => {
    const items = analysis.evidence.filter((item) => types.includes(item.evidence_type))
    return <article className="summary-card" key={name}><h3>{name}</h3>{items.length > 0 ? items.slice(0, 4).map((item) => <div className="summary-item" key={item.id}><strong>{item.claim}</strong><span>{papersById.get(item.paper_id)?.title || `Paper ${item.paper_id}`}</span><EvidenceExcerpt text={excerpt(item.source_excerpt, item.claim)} /></div>) : <p className="missing">Not identified in the available text.</p>}</article>
  })}</div></section>
}

function GapAssessment({ analysis, papersById }: { analysis: Analysis; papersById: Map<number, AnalysisPaper> }) {
  const onePaper = analysis.paper_count === 1
  return <section className="analysis-section" aria-labelledby="gaps-title"><p className="eyebrow">Conservative synthesis</p><h2 id="gaps-title">Research-gap assessment</h2>{analysis.candidate_gaps.length === 0 ? <div className="gap-state"><span className="state-badge">{onePaper ? 'Insufficient evidence' : 'No defensible research gap established'}</span><h3>{onePaper ? 'Cross-paper gap assessment unavailable' : 'No research gap could be established'}</h3><p>{onePaper ? 'Insufficient cross-paper evidence to establish a research gap.' : 'The selected papers do not provide sufficiently comparable evidence to identify a specific unresolved research question.'}</p><p className="analysis-note">{onePaper ? 'Add papers addressing the same research problem to enable cross-paper comparison.' : 'This does not mean that no gap exists in the broader literature.'}</p></div> : <div className="gap-list">{analysis.candidate_gaps.map((gap) => <GapCard gap={gap} evidence={analysis.evidence} papersById={papersById} key={gap.id} />)}</div>}</section>
}

function ContradictionsSection({ analysis, papersById }: { analysis: Analysis; papersById: Map<number, AnalysisPaper> }) {
  const contradictions = analysis.evidence.filter((item) => item.evidence_type === 'contradiction')
  return <section className="analysis-section" aria-labelledby="contradictions-title"><p className="eyebrow">Evidence check</p><h2 id="contradictions-title">Contradictions</h2>{contradictions.length > 0 ? <div className="finding-grid">{contradictions.map((item) => <EvidenceCard item={item} paper={papersById.get(item.paper_id)} key={item.id} />)}</div> : <div className="empty-panel"><p>No contradiction identified in the available evidence.</p></div>}</section>
}

function GapCard({ gap, evidence, papersById }: { gap: AnalysisGap; evidence: AnalysisEvidence[]; papersById: Map<number, AnalysisPaper> }) {
  const supporting = evidence.filter((item) => gap.supporting_paper_ids.includes(item.paper_id) && gap.observed_evidence.includes(item.claim))
  return <article className="gap-card"><div className="gap-card-top"><span className="state-badge">Potential research gap</span><span className="heuristic-score">Heuristic gap score: {Math.round(gap.confidence * 100)}%</span></div><h3>{gap.statement}</h3><p><strong>Why it appears:</strong> {gap.inference}</p><p><strong>Pattern:</strong> {gap.pattern || 'Not available in this response.'}</p><details><summary>View supporting evidence ({supporting.length})</summary>{supporting.length > 0 ? <ul>{supporting.map((item) => <li key={item.id}><strong>{papersById.get(item.paper_id)?.title || `Paper ${item.paper_id}`}</strong><EvidenceExcerpt text={excerpt(item.source_excerpt, item.claim)} /></li>)}</ul> : <p className="analysis-note">Supporting excerpts are not available.</p>}</details><details><summary>View confidence reasoning</summary><p className="analysis-note">This is a heuristic gap score based on explicit evidence, independent papers, consistency, and specificity; it is not a probability.</p></details></article>
}

function WhyConclusion({ analysis, papersById }: { analysis: Analysis; papersById: Map<number, AnalysisPaper> }) {
  return <section className="analysis-section" aria-labelledby="why-title"><p className="eyebrow">Reasoning trail</p><h2 id="why-title">Why this conclusion?</h2><div className="trail">{analysis.paper_ids.map((paperId) => {
    const paperEvidence = analysis.evidence.filter((item) => item.paper_id === paperId).filter((item) => item.evidence_type !== 'topic').slice(0, 3)
    return <article key={paperId}><strong>{papersById.get(paperId)?.title || `Paper ${paperId}`}</strong>{paperEvidence.length > 0 ? paperEvidence.map((item) => <span key={item.id}>→ {item.claim}</span>) : <span>→ No structured evidence identified</span>}</article>
  })}<p className="trail-conclusion">Therefore → {analysis.candidate_gaps.length > 0 ? 'the selected evidence supports a candidate issue, subject to its stated limitations.' : 'the available evidence is insufficient for a defensible shared research-gap conclusion.'}</p></div></section>
}

function CorpusOverview({ analysis }: { analysis: Analysis }) {
  const coherence = analysis.corpus_coherence
  const recurringThemes = (analysis.key_themes ?? []).filter((theme) => theme.paper_count > 1)
  return <section className="analysis-section"><p className="eyebrow">Descriptive only</p><h2>Corpus overview</h2><div className="overview-grid"><article><strong>Corpus size</strong><p>{analysis.paper_count} selected {analysis.paper_count === 1 ? 'paper' : 'papers'}</p></article><article><strong>Lexical/topic coherence</strong><p>{coherence ? titleLabel(coherence.status) : 'Not assessed'}</p><small>{coherence?.summary || 'Not identified in the available text.'}</small></article><article><strong>Evidence coverage</strong><p>{analysis.evidence.length} extracted items</p><small>Extraction is based on available paper text.</small></article><article><strong>Recurring themes</strong><p>{recurringThemes.length > 0 ? `${recurringThemes.length} shared themes` : 'None identified'}</p><small>{recurringThemes.length > 0 ? 'Topic overlap is descriptive only.' : 'No meaningful cross-paper recurring themes were identified.'}</small></article></div></section>
}

export default function AnalysisPage() {
  const { accessToken } = useAuth()
  const { id } = useParams()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    if (!accessToken || !id) return
    let current = true
    void getAnalysis(accessToken, id).then((result) => { if (current) setAnalysis(result) }).catch((caught) => { if (current) setError(caught instanceof AnalysisApiError ? caught.message : 'Unable to load this analysis.') }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [accessToken, id])
  const papersById = useMemo(() => new Map((analysis?.papers ?? []).map((paper) => [paper.paper_id, paper])), [analysis?.papers])
  if (loading) return <main className="analysis-page"><div className="analysis-shell"><p className="status-message">Loading analysis...</p></div></main>
  if (error) return <main className="analysis-page"><div className="analysis-shell"><div className="empty-state"><h1>Analysis unavailable</h1><p>{error}</p><Link to="/research">Back to research</Link></div></div></main>
  if (!analysis) return null
  return <main className="analysis-page">
    <header className="analysis-hero"><div className="analysis-shell"><Link className="analysis-back" to="/research">← Back to research</Link><p className="eyebrow">Research workspace</p><h1>Research Analysis</h1><div className="analysis-summary"><span>Status: <strong>{titleLabel(analysis.status)}</strong></span><span><strong>{analysis.paper_count} selected {analysis.paper_count === 1 ? 'paper' : 'papers'}</strong></span>{analysis.research_question && <span>Question supplied</span>}</div><details className="methodology-details"><summary>Analysis methodology</summary><p>{analysis.methodology_version}</p><p>Deterministic evidence extraction and conservative cross-paper synthesis.</p></details></div></header>
    <div className="analysis-shell analysis-content"><ExecutiveSummary analysis={analysis} /><section className="analysis-section" aria-labelledby="studied-title"><p className="eyebrow">Paper-by-paper view</p><h2 id="studied-title">What did these papers study?</h2><p className="section-intro">Fields are filled only when the available extracted evidence supports them.</p><div className="paper-grid">{(analysis.papers ?? analysis.paper_ids.map((paper_id) => ({ paper_id, title: null, authors: [], publication_year: null, abstract: null }))).map((paper) => <PaperCard paper={paper} evidence={analysis.evidence.filter((item) => item.paper_id === paper.paper_id)} key={paper.paper_id} />)}</div></section><FindingsSection analysis={analysis} papersById={papersById} /><EvidenceSummary analysis={analysis} papersById={papersById} /><CorpusOverview analysis={analysis} /><GapAssessment analysis={analysis} papersById={papersById} /><ContradictionsSection analysis={analysis} papersById={papersById} /><WhyConclusion analysis={analysis} papersById={papersById} /><section className="analysis-limitations" aria-labelledby="limitations-title"><h2 id="limitations-title">Scope &amp; limitations</h2><ul>{analysis.limitations.items.map((item) => <li key={item}>{item}</li>)}<li>Keyword and topic matching is not semantic understanding.</li><li>Absence of a detected signal does not prove absence from the paper.</li><li>Extraction confidence is rule-match confidence, not scientific certainty.</li><li>A candidate gap is not proof that no prior research exists.</li><li>A comprehensive literature review requires broader searching.</li></ul></section></div>
  </main>
}
