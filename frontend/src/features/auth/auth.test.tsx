import { act, createElement, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from './AuthContext'
import { authenticatedFetch, getStoredAccessToken } from './authApi'
import { useAuth } from './useAuth'

const user = {
  id: 7,
  email: 'ada@example.com',
  is_active: true,
  created_at: '2026-08-23T00:00:00Z',
  updated_at: '2026-08-23T00:00:00Z',
}

function Probe() {
  const auth = useAuth()
  return createElement(
    'div',
    { 'data-user': auth.user?.email ?? '', 'data-token': auth.accessToken ?? '', 'data-initializing': String(auth.isInitializing), 'data-error': auth.error ?? '' },
    createElement('button', { onClick: () => void auth.login('ada@example.com', 'password-123').catch(() => undefined), 'data-action': 'login' }),
    createElement('button', { onClick: () => void auth.register('ada@example.com', 'password-123').catch(() => undefined), 'data-action': 'register' }),
    createElement('button', { onClick: auth.logout, 'data-action': 'logout' }),
  )
}

function mount(children: ReactNode): { container: HTMLDivElement; root: Root } {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(children))
  return { container, root }
}

async function settle() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('frontend authentication session', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('starts unauthenticated and initializes without a stored token', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))
    await settle()

    expect(container.firstElementChild?.getAttribute('data-user')).toBe('')
    expect(container.firstElementChild?.getAttribute('data-token')).toBe('')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('logs in successfully and does not persist the password', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({ access_token: 'login-token', token_type: 'bearer' }))
      .mockResolvedValueOnce(response(user))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))

    await act(async () => container.querySelector('[data-action="login"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await settle()

    expect(container.firstElementChild?.getAttribute('data-user')).toBe(user.email)
    expect(getStoredAccessToken()).toBe('login-token')
    expect(localStorage.getItem('password')).toBeNull()
  })

  it('registers and establishes a session through login and /me', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response(user, 201))
      .mockResolvedValueOnce(response({ access_token: 'register-token', token_type: 'bearer' }))
      .mockResolvedValueOnce(response(user))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))

    await act(async () => container.querySelector('[data-action="register"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await settle()

    // Registration no longer auto-authenticates; registration should prompt verification
    expect(container.firstElementChild?.getAttribute('data-user')).toBe('')
    expect(container.firstElementChild?.getAttribute('data-error')).toContain('verification email')
    expect(getStoredAccessToken()).toBeNull()
  })

  it('restores a stored token only after /me validates it', async () => {
    localStorage.setItem('researchpilot.access_token', 'stored-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(user))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))
    await settle()

    expect(container.firstElementChild?.getAttribute('data-user')).toBe(user.email)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/me', expect.objectContaining({ headers: { Authorization: 'Bearer stored-token' } }))
  })

  it('clears an invalid stored token and becomes logged out', async () => {
    localStorage.setItem('researchpilot.access_token', 'expired-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ detail: 'Invalid authentication token.' }, 401))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))
    await settle()

    expect(container.firstElementChild?.getAttribute('data-user')).toBe('')
    expect(getStoredAccessToken()).toBeNull()
  })

  it('clears the session on logout', async () => {
    localStorage.setItem('researchpilot.access_token', 'stored-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(user))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))
    await settle()

    act(() => container.querySelector('[data-action="logout"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(container.firstElementChild?.getAttribute('data-user')).toBe('')
    expect(getStoredAccessToken()).toBeNull()
  })

  it('adds the bearer token through the centralized authenticated request helper', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ ok: true }))

    await authenticatedFetch('central-token', '/api/v1/ownership/papers')

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ownership/papers', { headers: { Authorization: 'Bearer central-token' } })
  })

  it('reports failed login while remaining logged out', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ detail: 'Invalid email or password.' }, 401))
    const { container } = mount(createElement(AuthProvider, null, createElement(Probe)))

    await act(async () => {
      container.querySelector('[data-action="login"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })
    await settle()

    expect(container.firstElementChild?.getAttribute('data-user')).toBe('')
    expect(container.firstElementChild?.getAttribute('data-error')).toContain('Invalid authentication credentials')
    expect(getStoredAccessToken()).toBeNull()
  })
})
