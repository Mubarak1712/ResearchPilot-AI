import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import {
  AuthApiError,
  clearStoredAccessToken,
  getCurrentUser,
  getStoredAccessToken,
  login as loginWithApi,
  register as registerWithApi,
  type AuthUser,
} from './authApi'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true
    const storedToken = getStoredAccessToken()

    async function restoreSession() {
      if (!storedToken) {
        if (isCurrent) setIsInitializing(false)
        return
      }

      try {
        const restoredUser = await getCurrentUser(storedToken)
        if (isCurrent) {
          setAccessToken(storedToken)
          setUser(restoredUser)
        }
      } catch {
        clearStoredAccessToken()
        if (isCurrent) {
          setAccessToken(null)
          setUser(null)
        }
      } finally {
        if (isCurrent) setIsInitializing(false)
      }
    }

    void restoreSession()
    return () => {
      isCurrent = false
    }
  }, [])

  async function login(email: string, password: string) {
    setError(null)
    try {
      const session = await loginWithApi(email, password)
      setAccessToken(session.token)
      setUser(session.user)
    } catch (caughtError) {
      const message = caughtError instanceof AuthApiError ? caughtError.message : 'Unable to sign in.'
      setError(message)
      throw caughtError
    }
  }

  async function register(email: string, password: string) {
    setError(null)
    try {
      const result = await registerWithApi(email, password)
      // Do not sign in automatically. Inform the user to verify their email.
      if (result.emailSent) {
        setError('Account created. Please check your inbox to verify your email before signing in.')
      } else if (result.verificationUrl) {
        setError('Account created. Use the development verification link below to verify your email before signing in.')
      } else {
        setError('Account created, but the verification email could not be sent. Please configure SMTP and try again.')
      }
      return result
    } catch (caughtError) {
      const message = caughtError instanceof AuthApiError ? caughtError.message : 'Unable to create an account.'
      setError(message)
      throw caughtError
    }
  }

  function logout() {
    clearStoredAccessToken()
    setAccessToken(null)
    setUser(null)
    setError(null)
  }

  return (
    <AuthContext.Provider value={{ user, accessToken, isInitializing, error, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

