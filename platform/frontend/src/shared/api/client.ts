import axios, { AxiosError } from 'axios'
import type { Envelope } from './types'

const TOKEN_KEY = 'koorm_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(t: string | null) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use((cfg) => {
  const t = getToken()
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError<Envelope<unknown>>) => {
    if (err.response?.status === 401 && onUnauthorized) onUnauthorized()
    return Promise.reject(err)
  },
)

/** Unwrap the {success,data,message} envelope, throwing the message on failure. */
export function unwrap<T>(env: Envelope<T>): T {
  if (!env.success) throw new Error(env.message || 'request failed')
  return env.data
}

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const env = err.response?.data as Envelope<unknown> | undefined
    if (env?.message) return env.message
    return err.message
  }
  return err instanceof Error ? err.message : String(err)
}
