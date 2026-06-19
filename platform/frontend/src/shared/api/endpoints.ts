// Typed API functions per resource.
import { api, unwrap } from './client'
import type {
  Job, OperationDetail, OperationSummary, SessionDetail, SessionFile,
  SessionSummary, TokenCreated, TokenInfo, User,
} from './types'

// auth
export async function login(email: string, password: string): Promise<string> {
  const { data } = await api.post('/auth/login', { email, password })
  return unwrap<{ access_token: string }>(data).access_token
}
export async function getMe(): Promise<User> {
  const { data } = await api.get('/me')
  return unwrap<User>(data)
}
export async function signup(email: string, password: string, display_name?: string): Promise<string> {
  const { data } = await api.post('/auth/signup', { email, password, display_name })
  return unwrap<{ access_token: string }>(data).access_token
}
export async function getAuthConfig(): Promise<{ allow_signup: boolean }> {
  const { data } = await api.get('/auth/config')
  return unwrap<{ allow_signup: boolean }>(data)
}

// tokens
export async function listTokens(): Promise<TokenInfo[]> {
  const { data } = await api.get('/me/tokens')
  return unwrap<TokenInfo[]>(data)
}
export async function createToken(name: string, expires_days?: number | null): Promise<TokenCreated> {
  const { data } = await api.post('/me/tokens', { name, expires_days: expires_days ?? null })
  return unwrap<TokenCreated>(data)
}
export async function revokeToken(id: number): Promise<void> {
  await api.delete(`/me/tokens/${id}`)
}

// sessions
export async function listSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get('/sessions')
  return unwrap<SessionSummary[]>(data)
}
export async function createSession(name: string, description?: string): Promise<SessionSummary> {
  const { data } = await api.post('/sessions', { name, description })
  return unwrap<SessionSummary>(data)
}
export async function getSession(id: string): Promise<SessionDetail> {
  const { data } = await api.get(`/sessions/${id}`)
  return unwrap<SessionDetail>(data)
}
export async function updateSession(id: string, patch: Partial<{ name: string; description: string; status: string }>): Promise<SessionSummary> {
  const { data } = await api.patch(`/sessions/${id}`, patch)
  return unwrap<SessionSummary>(data)
}
export async function deleteSession(id: string): Promise<void> {
  await api.delete(`/sessions/${id}`)
}

// files
export async function uploadFiles(sessionId: string, files: File[]): Promise<SessionFile[]> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const { data } = await api.post(`/sessions/${sessionId}/files`, fd)
  return unwrap<SessionFile[]>(data)
}
export async function listFiles(sessionId: string): Promise<SessionFile[]> {
  const { data } = await api.get(`/sessions/${sessionId}/files`)
  return unwrap<SessionFile[]>(data)
}
export async function deleteFile(sessionId: string, fileId: number): Promise<void> {
  await api.delete(`/sessions/${sessionId}/files/${fileId}`)
}
export function downloadFileUrl(sessionId: string, fileId: number): string {
  return `/api/v1/sessions/${sessionId}/files/${fileId}/download`
}
export async function downloadFile(sessionId: string, fileId: number, filename: string): Promise<void> {
  const res = await api.get(`/sessions/${sessionId}/files/${fileId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// operations
export async function listOperations(): Promise<OperationSummary[]> {
  const { data } = await api.get('/operations')
  return unwrap<OperationSummary[]>(data)
}
export async function getOperation(op: string): Promise<OperationDetail> {
  const { data } = await api.get(`/operations/${op}`)
  return unwrap<OperationDetail>(data)
}

// jobs
export async function createJob(sessionId: string, operation: string, args: Record<string, unknown>): Promise<Job> {
  const { data } = await api.post(`/sessions/${sessionId}/jobs`, { operation, args })
  return unwrap<Job>(data)
}
export async function listSessionJobs(sessionId: string): Promise<Job[]> {
  const { data } = await api.get(`/sessions/${sessionId}/jobs`)
  return unwrap<Job[]>(data)
}
export async function getJob(jobId: string): Promise<Job> {
  const { data } = await api.get(`/jobs/${jobId}`)
  return unwrap<Job>(data)
}
export async function getJobLogs(jobId: string): Promise<string> {
  const { data } = await api.get(`/jobs/${jobId}/logs`, { responseType: 'text' })
  return data as string
}
export async function getJobOutputs(jobId: string): Promise<SessionFile[]> {
  const { data } = await api.get(`/jobs/${jobId}/outputs`)
  return unwrap<SessionFile[]>(data)
}
export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/cancel`)
}
