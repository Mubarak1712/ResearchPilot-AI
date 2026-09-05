import { useEffect, useState } from 'react'
import { AuthApiError, requestJson } from './authApi'

export default function VerifyEmail() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'missing'>('loading')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (!token) {
      setStatus('missing')
      setMessage('Verification token missing from URL.')
      return
    }

    async function verify() {
      try {
        await requestJson('/api/v1/auth/verify-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        })
        setStatus('success')
        setMessage('Email verified successfully. You can now sign in.')
      } catch (err) {
        const msg = err instanceof AuthApiError ? err.message : 'Verification failed.'
        setStatus('error')
        setMessage(msg)
      }
    }

    void verify()
  }, [])

  if (status === 'loading') return <main><h1>Verifying…</h1></main>
  if (status === 'missing') return <main><h1>Verification</h1><p>{message}</p></main>
  if (status === 'error') return <main><h1>Verification failed</h1><p>{message}</p><p><a href="/">Back to sign in</a></p></main>
  return <main><h1>Verified</h1><p>{message}</p><p><a href="/">Sign in</a></p></main>
}
