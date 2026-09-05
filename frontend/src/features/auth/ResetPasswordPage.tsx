import { useEffect, useState } from 'react'
import { AuthApiError, resetPassword } from './authApi'

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error' | 'missing' >('idle')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const t = params.get('token')
    if (!t) {
      setStatus('missing')
      setMessage('Reset token missing from URL.')
    } else {
      setToken(t)
    }
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('submitting')
    setMessage(null)
    if (!token) {
      setStatus('error')
      setMessage('Missing token')
      return
    }
    if (password.length < 8) {
      setStatus('error')
      setMessage('Password must be at least 8 characters')
      return
    }
    if (password !== confirm) {
      setStatus('error')
      setMessage('Passwords do not match')
      return
    }

    try {
      await resetPassword(token, password)
      setStatus('success')
      setMessage('Password reset successful. You can now sign in.')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof AuthApiError ? err.message : 'Unable to reset password.')
    }
  }

  if (status === 'missing') return <main><h1>Reset password</h1><p>{message}</p></main>
  if (status === 'success') return <main><h1>Reset password</h1><p>{message}</p><p><a href="/">Sign in</a></p></main>

  return (
    <main>
      <h1>Reset password</h1>
      <form onSubmit={handleSubmit}>
        <label>New password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <label>Confirm</label>
        <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        {message && <p>{message}</p>}
        <button type="submit">Set new password</button>
      </form>
    </main>
  )
}
