import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from './useAuth'
import './AuthUi.css'

function AuthUi({ children }: { children: ReactNode }) {
  const { user, isInitializing, logout } = useAuth()
  const location = useLocation()
  const isAuthPage = ['/', '/login', '/register', '/forgot-password'].includes(location.pathname)
  const isStandaloneAuthFlow = ['/verify-email', '/reset-password'].includes(location.pathname)

  if (isInitializing) {
    return (
      <main className="auth-loading" aria-live="polite">
        <p className="auth-kicker">ResearchPilot</p>
        <h1>Checking your session</h1>
        <p>Restoring your secure workspace…</p>
      </main>
    )
  }

  if (!user && !isAuthPage && !isStandaloneAuthFlow) {
    return <Navigate to="/login" replace />
  }

  if (user && isAuthPage) {
    return <Navigate to="/research" replace />
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-brand">ResearchPilot</span>
        <nav className="app-nav" aria-label="Workspace navigation">
          <Link to="/research">Explore</Link>
          <Link to="/saved">Library</Link>
        </nav>
        {user ? (
          <div className="auth-navigation">
            <span className="auth-user">{user.email}</span>
            <button type="button" onClick={logout}>Log out</button>
          </div>
        ) : (
          <span className="auth-status">Not signed in</span>
        )}
      </header>
      {!user && isAuthPage && <AuthPanel />}
      {children}
    </div>
  )
}

function AuthPanel() {
  const { error, login, register } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const routeMode = location.pathname === '/register' ? 'register' : location.pathname === '/forgot-password' ? 'forgot' : 'login'
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>(routeMode)
  useEffect(() => setMode(routeMode), [routeMode])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [devVerificationUrl, setDevVerificationUrl] = useState<string | null>(null)
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setDevVerificationUrl(null)
    setDevResetUrl(null)
    try {
      if (mode === 'login') {
        await login(email.trim(), password)
      } else if (mode === 'register') {
        const result = await register(email.trim(), password)
        setDevVerificationUrl(result?.verificationUrl ?? null)
      } else if (mode === 'forgot') {
        const { forgotPassword } = await import('./authApi')
        const result = await forgotPassword(email.trim())
        setDevResetUrl(result?.resetUrl ?? null)
      }
    } catch {
      // The auth context exposes the user-facing error; the form consumes the rejected action.
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="auth-panel" aria-labelledby="auth-title">
      <div>
        <p className="auth-kicker">Your research workspace</p>
        <h1 id="auth-title">{mode === 'login' ? 'Sign in to ResearchPilot' : mode === 'register' ? 'Create your account' : 'Reset your password'}</h1>
        <p className="auth-copy">
          {mode === 'login'
            ? 'Keep your research workspace close.'
            : mode === 'register'
            ? 'Start with a secure personal workspace.'
            : 'Enter your email to receive password reset instructions.'}
        </p>
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="auth-email">Email</label>
        <input
          id="auth-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          required
        />
        {mode !== 'forgot' && (
          <>
            <label htmlFor="auth-password">Password</label>
            <div className="password-row">
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </>
        )}
        {error && <p className="auth-error" role="alert">{error}</p>}
        {devVerificationUrl && (
          <div className="auth-dev-link" role="note">
            <strong>Development verification link:</strong>
            <a href={devVerificationUrl} target="_blank" rel="noreferrer">Verify account</a>
          </div>
        )}
        {devResetUrl && (
          <div className="auth-dev-link" role="note">
            <strong>Development reset link:</strong>
            <a href={devResetUrl} target="_blank" rel="noreferrer">Reset password</a>
          </div>
        )}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? 'Please wait…'
            : mode === 'login'
            ? 'Sign in'
            : mode === 'register'
            ? 'Create account'
            : 'Send reset email'}
        </button>
      </form>
      <div className="auth-actions">
        {mode === 'login' && (
          <>
            <button className="auth-mode-toggle" type="button" onClick={() => { setMode('register'); navigate('/register') }}>
              Need an account? Register
            </button>
            <button className="auth-mode-toggle" type="button" onClick={() => { setMode('forgot'); navigate('/forgot-password') }}>
              Forgot password?
            </button>
          </>
        )}
        {mode === 'register' && (
          <button className="auth-mode-toggle" type="button" onClick={() => { setMode('login'); navigate('/login') }}>
            Already have an account? Sign in
          </button>
        )}
        {mode === 'forgot' && (
          <button className="auth-mode-toggle" type="button" onClick={() => { setMode('login'); navigate('/login') }}>
            Cancel
          </button>
        )}
      </div>
    </section>
  )
}

export default AuthUi
