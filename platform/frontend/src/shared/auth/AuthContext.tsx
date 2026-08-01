import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getToken, setToken, setUnauthorizedHandler } from '@/shared/api/client'
import { getMe, login as apiLogin, signup as apiSignup, ssoLogin } from '@/shared/api/endpoints'
import type { User } from '@/shared/api/types'

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, displayName?: string) => Promise<void>
  logout: () => void
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
  }, [logout])

  useEffect(() => {
    if (!getToken()) {
      // HEAX 포탈 프록시 경유면 게이트웨이 헤더 기반 SSO 자동 로그인 시도 (1회).
      // standalone/미구성 환경에선 즉시 실패해 로그인 화면으로 간다.
      ssoLogin()
        .then(async (token) => {
          setToken(token)
          setUser(await getMe())
        })
        .catch(() => {})
        .finally(() => setLoading(false))
      return
    }
    getMe()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const token = await apiLogin(email, password)
    setToken(token)
    setUser(await getMe())
  }, [])

  const signup = useCallback(async (email: string, password: string, displayName?: string) => {
    const token = await apiSignup(email, password, displayName)
    setToken(token)
    setUser(await getMe())
  }, [])

  const value = useMemo(() => ({ user, loading, login, signup, logout }), [user, loading, login, signup, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
