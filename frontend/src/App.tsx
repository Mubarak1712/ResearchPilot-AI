import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { AuthProvider } from './features/auth/AuthContext'
import AuthUi from './features/auth/AuthUi'
import ResetPasswordPage from './features/auth/ResetPasswordPage'
import SavedPapersOwnershipSection from './features/auth/SavedPapersOwnershipSection'
import VerifyEmail from './features/auth/VerifyEmail'
import PaperDetailsPage from './features/research/PaperDetailsPage'
import ResearchSearchPage from './features/research/ResearchSearchPage'
import AnalysisPage from './features/analysis/AnalysisPage'
import type { ResearchPaper, SavedPaper } from './features/research/types'
import { getPaper, ResearchApiError } from './features/research/researchApi'

function SavedPage() {
  const navigate = useNavigate()
  return (
    <main className="research-page">
      <section className="research-hero details-hero" aria-labelledby="saved-page-title">
        <div className="details-shell">
          <p className="brand">ResearchPilot</p>
          <p className="eyebrow">Your library</p>
          <h1 id="saved-page-title">Your research library.</h1>
          <p className="hero-copy">A focused home for the papers you want to return to.</p>
        </div>
      </section>
      <SavedPapersOwnershipSection
        onSelect={(paper) => navigate(`/papers/${encodeURIComponent(paper.id)}`, { state: { paper } })}
      />
    </main>
  )
}

function PaperRoute() {
  const location = useLocation()
  const navigate = useNavigate()
  const paper = (location.state as { paper?: ResearchPaper | SavedPaper } | null)?.paper
  const [loadedPaper, setLoadedPaper] = useState<SavedPaper | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  useEffect(() => {
    if (paper) return
    let active = true
    const identifier = decodeURIComponent(location.pathname.split('/').pop() || '')
    void getPaper(identifier).then((result) => {
      if (active) setLoadedPaper(result)
    }).catch((error) => {
      if (active) setLoadError(error instanceof ResearchApiError ? error.message : 'Unable to load this paper.')
    })
    return () => { active = false }
  }, [paper, location.pathname])
  const resolvedPaper = paper ?? loadedPaper
  if (!resolvedPaper) {
    return (
      <main className="research-page">
        <section className="research-results">
          <div className="empty-state">
            <h2>Paper details unavailable</h2>
            <p>{loadError || 'Loading paper details...'}</p>
            <button type="button" onClick={() => navigate('/research')}>Back to research</button>
          </div>
        </section>
      </main>
    )
  }
  return <PaperDetailsPage paper={resolvedPaper} onBack={() => navigate(-1)} />
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthUi>
          <Routes>
            <Route path="/" element={<Navigate to="/research" replace />} />
            <Route path="/login" element={null} />
            <Route path="/register" element={null} />
            <Route path="/forgot-password" element={null} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/research" element={<ResearchSearchPage />} />
            <Route path="/research/results" element={<ResearchSearchPage />} />
            <Route path="/saved" element={<SavedPage />} />
            <Route path="/papers/:id" element={<PaperRoute />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route path="*" element={<Navigate to="/research" replace />} />
          </Routes>
        </AuthUi>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
