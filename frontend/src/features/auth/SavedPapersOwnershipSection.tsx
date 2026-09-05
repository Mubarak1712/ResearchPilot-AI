import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ResearchPaper } from '../research/types'
import { useAuth } from './useAuth'
import { useOwnership } from './useOwnership'
import type { SavedPaperOwnership } from './ownershipApi'

function SavedPapersOwnershipSection({ onSelect }: { onSelect: (paper: ResearchPaper) => void }) {
  const { user, isInitializing: isAuthInitializing } = useAuth()
  const { savedPapers, isLoading, error, unsavePaper } = useOwnership()
  const [removingId, setRemovingId] = useState<number | null>(null)

  return (
    <section className="saved-papers" aria-labelledby="saved-papers-title">
      <div className="results-heading">
        <p className="eyebrow">Your library</p>
        <h2 id="saved-papers-title">Saved papers</h2>
        {!isAuthInitializing && user && !isLoading && !error && (
          <p className="paper-meta">{savedPapers.length} {savedPapers.length === 1 ? 'paper' : 'papers'} saved</p>
        )}
      </div>

      {isAuthInitializing && <p className="status-message">Checking your account…</p>}
      {!isAuthInitializing && !user && (
        <p className="status-message">Sign in to view your saved papers.</p>
      )}
      {!isAuthInitializing && user && isLoading && (
        <p className="status-message">Loading your saved papers…</p>
      )}
      {!isAuthInitializing && user && error && (
        <p className="status-message status-error" role="alert">{error.message}</p>
      )}
      {!isAuthInitializing && user && !isLoading && !error && savedPapers.length === 0 && (
        <div className="empty-state">
          <h3>No saved research yet</h3>
          <p>Papers you save will appear here. Save papers while exploring ResearchPilot and they will appear here.</p>
          <Link to="/research">Explore research</Link>
        </div>
      )}
      {!isAuthInitializing && user && !error && savedPapers.length > 0 && (
        <div className="paper-list">
          {savedPapers.map((paper) => (
            <article className="paper-card" key={paper.id}>
              <div className="paper-card__header">
                <button
                  className="paper-title-button"
                  type="button"
                  onClick={() => onSelect(toResearchPaper(paper))}
                >
                  {paper.title || 'Untitled research paper'}
                </button>
                {paper.publication_year && <span className="year-chip">{paper.publication_year}</span>}
              </div>
              <p className="authors">
                {paper.authors.length > 0 ? paper.authors.join(', ') : 'Authors unavailable'}
              </p>
              <div className="paper-meta">
                {paper.publication_year && <span>Published: {paper.publication_year}</span>}
              </div>
              {paper.abstract && <p className="abstract">{paper.abstract}</p>}
              <div className="paper-links">
                <button
                  className="save-button"
                  type="button"
                  onClick={() => {
                    setRemovingId(paper.id)
                    void unsavePaper(paper.id).finally(() => setRemovingId(null))
                  }}
                  disabled={removingId !== null}
                >
                  {removingId === paper.id ? 'Removing…' : 'Remove saved paper'}
                </button>
                {paper.doi && (
                  <a href={paper.doi} target="_blank" rel="noreferrer">View DOI</a>
                )}
                {paper.url && (
                  <a href={paper.url} target="_blank" rel="noreferrer">View paper</a>
                )}
                <button type="button" className="save-button" onClick={() => onSelect(toResearchPaper(paper))}>
                  View details
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function toResearchPaper(paper: SavedPaperOwnership): ResearchPaper {
  return {
    id: paper.openalex_id,
    title: paper.title,
    authors: paper.authors,
    publication_year: paper.publication_year,
    abstract: paper.abstract,
    doi: paper.doi,
    url: paper.url,
  }
}

export default SavedPapersOwnershipSection
