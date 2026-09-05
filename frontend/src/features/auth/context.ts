import { createContext } from 'react'
import type { AuthUser } from './authApi'

export type AuthContextValue = {
  user: AuthUser | null
  accessToken: string | null
  isInitializing: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<{ user: AuthUser; emailSent: boolean; verificationUrl: string | null }>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
