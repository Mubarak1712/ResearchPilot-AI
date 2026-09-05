import type { ResearchPaper, SavedPaper } from './types'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { savePaper as createSavedPaper } from './researchApi'
import { useAuth } from '../auth/useAuth'
import { useOwnership } from '../auth/useOwnership'

type DetailPaper = ResearchPaper | SavedPaper

type PaperDetailsPageProps = {
  paper: DetailPaper
  onBack: () => void
}

function formatPublishedValue(paper: DetailPaper) {
  return paper.publication_date || paper.publication_year?.toString() || null
}

function PaperDetailsPage({ paper, onBack }: PaperDetailsPageProps) {
  const doiUrl = paper.doi ? normalizeDoiUrl(paper.doi) : null
  const { accessToken } = useAuth()
  const { savedPapers, isPaperSaved, savePaper, unsavePaper, loadSavedPapers } = useOwnership()
  const [isSaving, setIsSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const openAlexId = 'openalex_id' in paper ? paper.openalex_id : paper.id
  const ownedPaper = savedPapers.find((saved) => saved.openalex_id === openAlexId)
  const isSaved = ownedPaper ? isPaperSaved(ownedPaper.id) : false

  async function handleSaveToggle() {
    if (!accessToken || isSaving) return
    setIsSaving(true)
    setActionError(null)
    try {
      if (isSaved && ownedPaper) {
        await unsavePaper(ownedPaper.id)
      } else {
        const paperId = ownedPaper?.id ?? (await createSavedPaper(openAlexId)).id
        await savePaper(paperId)
      }
      await loadSavedPapers()
    } catch {
      setActionError(isSaved ? 'Could not remove this paper. Please try again.' : 'Could not save this paper. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="research-page details-page">
      <section className="research-hero details-hero" aria-labelledby="paper-details-title">
        <div className="details-shell">
          <button className="back-button" type="button" onClick={onBack}>
            <span aria-hidden="true">←</span> Back to research
          </button>
          <p className="brand">ResearchPilot</p>
          <p className="eyebrow">Paper details</p>
          <h1 id="paper-details-title">{paper.title || 'Untitled research paper'}</h1>
          {accessToken && (
            <button className="save-button details-save-button" type="button" onClick={() => void handleSaveToggle()} disabled={isSaving}>
              {isSaving ? (isSaved ? 'Removing…' : 'Saving…') : isSaved ? 'Saved — remove' : 'Save paper'}
            </button>
          )}
          {actionError && <p className="status-message status-error" role="alert">{actionError}</p>}
        </div>
      </section>

      <section className="paper-details" aria-label="Paper information">
        <div className="detail-grid">
          <div className="detail-main">
            <DetailField label="Authors">
              {paper.authors.length > 0 ? paper.authors.join(', ') : 'Authors unavailable'}
            </DetailField>
            <DetailField label="Publication year">
              {formatPublishedValue(paper) || 'Publication date unavailable'}
            </DetailField>
            <DetailField label="Research metadata">
              <div className="detail-meta">
                {formatPublishedValue(paper) && (
                  <span>Published: {formatPublishedValue(paper)}</span>
                )}
                {paper.citation_count !== null && paper.citation_count !== undefined && (
                  <span>Citations: {paper.citation_count.toLocaleString()}</span>
                )}
                {paper.source_name && <span>Source: {paper.source_name}</span>}
                {!formatPublishedValue(paper) && paper.citation_count == null && !paper.source_name && (
                  <span>Additional metadata unavailable.</span>
                )}
              </div>
            </DetailField>
            <DetailField label="Abstract">
              {paper.abstract || 'No abstract is available for this paper.'}
            </DetailField>
          </div>

          <aside className="detail-sidebar" aria-label="Paper links">
            <p className="eyebrow">Sources</p>
            {doiUrl ? (
              <a className="source-link" href={doiUrl} target="_blank" rel="noreferrer">
                DOI
                <span>{paper.doi}</span>
              </a>
            ) : (
              <p className="missing-detail">DOI unavailable</p>
            )}
            {paper.url ? (
              <a className="source-link" href={paper.url} target="_blank" rel="noreferrer">
                OpenAlex / source
                <span>{paper.url}</span>
              </a>
            ) : (
              <p className="missing-detail">Source URL unavailable</p>
            )}
          </aside>
        </div>
      </section>
    </main>
  )
}

function DetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="detail-field">
      <p className="eyebrow">{label}</p>
      <div className="detail-value">{children}</div>
    </div>
  )
}

function normalizeDoiUrl(doi: string) {
  return doi.startsWith('http') ? doi : `https://doi.org/${doi}`
}

export default PaperDetailsPage
