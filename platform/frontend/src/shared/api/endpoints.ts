// Typed API functions per resource.
import { api, unwrap } from './client'
import type {
  Job, ModelMeta, OperationDetail, OperationSummary, Report, ReportCase, ReportListItem,
  SessionDetail, SessionFile, SessionSummary, TokenCreated, TokenInfo, User,
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
/** HEAX 포탈 게이트웨이 SSO — 프록시 헤더 기반 자동 로그인 (미구성/미로그인 시 throw). */
export async function ssoLogin(): Promise<string> {
  const { data } = await api.post('/auth/sso')
  return unwrap<{ access_token: string }>(data).access_token
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
export async function extractConnectivity(
  sessionId: string, fileId: number, detect = true,
): Promise<ModelMeta> {
  const { data } = await api.post(
    `/sessions/${sessionId}/files/${fileId}/connectivity?detect=${detect}`,
  )
  return unwrap<ModelMeta>(data)
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

// reports (낙하/충격 리포트 인제스트·분석)
export async function listReports(sessionId: string): Promise<ReportListItem[]> {
  const { data } = await api.get(`/sessions/${sessionId}/reports`)
  return unwrap<ReportListItem[]>(data)
}
export async function ingestReport(sessionId: string, file: File, kind?: string): Promise<Report> {
  const fd = new FormData()
  fd.append('file', file)
  if (kind) fd.append('kind', kind)
  const { data } = await api.post(`/sessions/${sessionId}/reports`, fd)
  return unwrap<Report>(data)
}
export async function getReport(reportId: string): Promise<Report> {
  const { data } = await api.get(`/reports/${reportId}`)
  return unwrap<Report>(data)
}
export async function listReportCases(
  reportId: string, sort = 'max_stress', order = 'desc', limit = 20,
): Promise<ReportCase[]> {
  const { data } = await api.get(`/reports/${reportId}/cases`, { params: { sort, order, limit } })
  return unwrap<ReportCase[]>(data)
}
export async function publishReportToDatahub(
  reportId: string, body: { project: string; stage: string; variation?: string; doe?: string },
): Promise<{ record_id: string; view: string }> {
  const { data } = await api.post(`/reports/${reportId}/publish-datahub`, body)
  return unwrap<{ record_id: string; view: string }>(data)
}
export async function deleteReport(reportId: string): Promise<void> {
  await api.delete(`/reports/${reportId}`)
}
/** 원본 리포트 HTML 을 blob URL 로 (iframe src 용 — 인증 헤더가 필요해 직접 fetch).
 *  백엔드 download 는 octet-stream 이라 iframe 이 다운로드해버린다 → text/html 로 리타입. */
export async function reportHtmlBlobUrl(sessionId: string, fileId: number): Promise<string> {
  const res = await api.get(`/sessions/${sessionId}/files/${fileId}/download`, { responseType: 'blob' })
  const html = new Blob([res.data as Blob], { type: 'text/html' })
  return URL.createObjectURL(html)
}
