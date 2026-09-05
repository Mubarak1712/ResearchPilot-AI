import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import AuthUi from './AuthUi'
import { useAuth } from './useAuth'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('./useAuth', () => ({ useAuth: vi.fn() }))

const user = {
  id: 1,
  email: 'ada@example.com',
  is_active: true,
  created_at: '2026-08-23T00:00:00Z',
  updated_at: '2026-08-23T00:00:00Z',
}

function renderAuth(overrides: {
  user?: typeof user | null
  accessToken?: string | null
  isInitializing?: boolean
  error?: string | null
} = {}) {
  const state = { ...authState(), ...overrides }
  vi.mocked(useAuth).mockReturnValue(state)
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(createElement(MemoryRouter, null, createElement(AuthUi, null, createElement('p', null, 'Research content')))))
  return { container, root, state }
}

function authState() {
  return {
    user: null,
    accessToken: null,
    isInitializing: false,
    error: null,
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
  }
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await Promise.resolve()
  })
}

describe('authentication UI', () => {
  beforeEach(() => vi.clearAllMocks())

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows the authentication loading state', () => {
    const { container, root } = renderAuth({ isInitializing: true })

    expect(container.textContent).toContain('Checking your session')
    expect(container.querySelector('form')).toBeNull()
    act(() => root.unmount())
  })

  it('submits registration credentials through useAuth', async () => {
    const { container, root, state } = renderAuth()
    await click(container.querySelector('.auth-mode-toggle')!)
    const form = container.querySelector('form')!
    const inputs = form.querySelectorAll('input')
    act(() => {
      Object.defineProperty(inputs[0], 'value', { value: 'ada@example.com', writable: true })
      inputs[0].dispatchEvent(new Event('input', { bubbles: true }))
      Object.defineProperty(inputs[1], 'value', { value: 'password-123', writable: true })
      inputs[1].dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => {
      form.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }))
      await Promise.resolve()
    })

    expect(state.register).toHaveBeenCalledWith('ada@example.com', 'password-123')
    act(() => root.unmount())
  })

  it('submits login credentials through useAuth', async () => {
    const { container, root, state } = renderAuth()
    const form = container.querySelector('form')!
    const inputs = form.querySelectorAll('input')
    act(() => {
      Object.defineProperty(inputs[0], 'value', { value: 'ada@example.com', writable: true })
      inputs[0].dispatchEvent(new Event('input', { bubbles: true }))
      Object.defineProperty(inputs[1], 'value', { value: 'password-123', writable: true })
      inputs[1].dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => {
      form.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }))
      await Promise.resolve()
    })

    expect(state.login).toHaveBeenCalledWith('ada@example.com', 'password-123')
    act(() => root.unmount())
  })

  it('renders authentication errors from the session layer', () => {
    const { container, root } = renderAuth({ error: 'Invalid authentication credentials.' })

    expect(container.querySelector('[role="alert"]')?.textContent).toBe('Invalid authentication credentials.')
    act(() => root.unmount())
  })

  it('shows authenticated navigation and invokes logout', async () => {
    const { container, root, state } = renderAuth({ user, accessToken: 'token' })

    expect(container.textContent).toContain(user.email)
    expect(container.textContent).not.toContain('Not signed in')
    expect(container.querySelector('.auth-panel')).toBeNull()
    await click(container.querySelector('.auth-navigation button')!)
    expect(state.logout).toHaveBeenCalledOnce()
    act(() => root.unmount())
  })

  it('shows unauthenticated navigation and login controls', () => {
    const { container, root } = renderAuth()

    expect(container.textContent).toContain('Not signed in')
    expect(container.querySelector('input[type="email"]')).not.toBeNull()
    expect(container.textContent).toContain('Sign in')
    act(() => root.unmount())
  })
})