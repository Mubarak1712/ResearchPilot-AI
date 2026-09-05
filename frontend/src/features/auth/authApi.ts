export type AuthUser = {
  id: number
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
}

type TokenResponse = {
  access_token: string
  token_type: 'bearer'
}

export class AuthApiError extends Error {}

const ACCESS_TOKEN_KEY = 'researchpilot.access_token'

export async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(input, init)
  } catch {
    throw new AuthApiError('Unable to reach the authentication service. Please try again.')
  }

  if (!response.ok) {
    try {
      const errBody = await response.json()
      const detail = (errBody && (errBody.detail || errBody.message || errBody.error)) as string | undefined
      if (detail) {
        throw new AuthApiError(detail)
      }
    } catch {
      // Fall back to generic messages below if response body isn't JSON or lacks detail.
    }

    throw new AuthApiError(
      response.status === 401
        ? 'Invalid authentication credentials.'
        : 'The authentication service returned an error. Please try again.',
    )
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new AuthApiError('The authentication service returned an invalid response.')
  }
}

function authenticatedRequest(token: string, init: RequestInit = {}): RequestInit {
  // Preserve any provided headers and add the Authorization header.
  const existingHeaders: Record<string, string> = {}

  if (init && init.headers) {
    const h = init.headers as any
    if (typeof h.forEach === 'function') {
      try {
        h.forEach((value: string, key: string) => {
          existingHeaders[key] = value
        })
      } catch {
        // ignore
      }
    } else if (typeof h === 'object') {
      Object.assign(existingHeaders, h)
    }
  }

  return {
    ...init,
    headers: {
      ...existingHeaders,
      Authorization: `Bearer ${token}`,
    },
  }
}

export async function login(email: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const tokenResponse = await requestJson<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (tokenResponse.token_type !== 'bearer' || !tokenResponse.access_token) {
    throw new AuthApiError('The authentication service returned an invalid token.')
  }

  const user = await getCurrentUser(tokenResponse.access_token)
  storeAccessToken(tokenResponse.access_token)
  return { token: tokenResponse.access_token, user }
}

export async function register(email: string, password: string): Promise<{ user: AuthUser; emailSent: boolean; verificationUrl: string | null }> {
  let response: Response
  try {
    response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    })
  } catch {
    throw new AuthApiError('Unable to reach the authentication service. Please try again.')
  }

  if (!response.ok) {
    try {
      const errBody = await response.json()
      const detail = (errBody && (errBody.detail || errBody.message || errBody.error)) as string | undefined
      if (detail) throw new AuthApiError(detail)
    } catch {
      // fall through
    }
    throw new AuthApiError(response.status === 401 ? 'Invalid authentication credentials.' : 'The authentication service returned an error. Please try again.')
  }

  let user: AuthUser
  try {
    user = (await response.json()) as AuthUser
  } catch {
    throw new AuthApiError('The authentication service returned an invalid response.')
  }

  const header = response.headers.get('x-verification-email-sent')
  const emailSent = header === 'true'
  const verificationUrl = response.headers.get('x-verification-url')
  return { user, emailSent, verificationUrl }
}

export function getCurrentUser(token: string): Promise<AuthUser> {
  return requestJson<AuthUser>('/api/v1/auth/me', authenticatedRequest(token))
}

export async function forgotPassword(email: string): Promise<{ resetUrl: string | null }> {
  const response = await fetch('/api/v1/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim() }),
  })

  if (!response.ok) {
    try {
      const errBody = await response.json()
      const detail = (errBody && (errBody.detail || errBody.message || errBody.error)) as string | undefined
      if (detail) {
        throw new AuthApiError(detail)
      }
    } catch {
      // fall through to generic error below
    }
    throw new AuthApiError('The authentication service returned an error. Please try again.')
  }

  const resetUrl = response.headers.get('x-reset-url')
  return { resetUrl }
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await requestJson('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}

export function getStoredAccessToken(): string | null {
  return typeof localStorage === 'undefined' ? null : localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function storeAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearStoredAccessToken() {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
}

export function authenticatedFetch(token: string, input: RequestInfo | URL, init?: RequestInit) {
  return fetch(input, authenticatedRequest(token, init))
}
