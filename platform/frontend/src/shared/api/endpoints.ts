// Typed API functions per resource.
import { api, unwrap } from './client'
import type {
  AngleGroupStats, Job, ModelMeta, OperationDetail, OperationSummary, PartEnergySeries, Report,
  ReportCase, ReportDirectional, ReportEnergy, ReportFactQuery, ReportGeometry, ReportListItem,
  ReportKind, ReportPartRisk, ReportPartSeries, ReportScatter, ScatterMetric, SessionDetail,
  SessionFile, SessionSummary, TokenCreated, TokenInfo, User,
  ReportAnalytics, ReportBehaviorClusters, ReportBlocks, ReportHotspots, ReportMedia,
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
  // 폴더로 고른 파일은 `webkitRelativePath` 에 하위 경로가 들어 있다. 그 경로를 파트 이름으로
  // 실어 보내야 서버가 `sub/part.k` 를 그대로 저장한다 — 눕히면 산출물의 `*INCLUDE sub/part.k`
  // 가 가리킬 곳이 없어지고, LS-DYNA 는 인클루드를 따라가므로 거기서 깨진다.
  for (const f of files) fd.append('files', f, f.webkitRelativePath || f.name)
  const { data } = await api.post(`/sessions/${sessionId}/files`, fd)
  return unwrap<SessionFile[]>(data)
}

export type IncludeStatus = { ok: boolean; missing_by_file: Record<string, { missing: string[]; satisfied: string[] }> }
// 덱이 정의되지 않은 것을 가리키나 (P1-5). `grade` 가 게이트를 가른다 — `certain` 만 잡 제출을 막는다.
export type RefDangling = {
  count: number
  grade: 'certain' | 'uncertain'
  damaged: number
  top: { line: number; keyword: string; what: string }[]
  unread_includes: string[]
}
export async function getIncludeStatus(sessionId: string): Promise<IncludeStatus> {
  const { data } = await api.get(`/sessions/${sessionId}/includes`)
  return unwrap<IncludeStatus>(data)
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

// stcx (전각도 낙하) — 2026-10-14 부터 **프리셋이라는 개념이 없다.** 제출이
// SmartTwinMCP 로 옮겨지면서 각도는 방향 수(num_directions)로만 정한다. 그래서 이
// 엔드포인트는 빈 목록과 **사유**를 돌려준다(빈 목록만 주면 "없다" 처럼 보인다).
// ⚠ 이 함수는 지금 **부르는 곳이 없다**(제출 전부터 그랬다).
export interface StcxOptions {
  available: boolean
  presets: string[]
  catalog: string
  reason?: string
  detail?: string
}
export async function getStcxOptions(): Promise<StcxOptions> {
  const { data } = await api.get('/stcx/options')
  return unwrap<StcxOptions>(data)
}

// 온톨로지 — 과제 거울과 개발 개정. **과제는 읽기만**이다(정본은 허브).
export interface TaskMirror {
  key: string; label: string; status: string; deleted: boolean
  properties: Record<string, unknown>; updated_at: string | null
}
export interface TaskListOut {
  items: TaskMirror[]
  sync_enabled: boolean
  last_status: string | null
  last_error: string | null
  last_run_at: string | null
  /** 목록이 빈 **이유**. 빈 목록만 주면 「과제가 없다」로 읽히는데 실제로는 물어보지도 못한 것이다. */
  reason: string | null
}
export async function listTasks(q?: string, limit = 100): Promise<TaskListOut> {
  const { data } = await api.get('/ontology/tasks', { params: { q: q || undefined, limit } })
  return unwrap<TaskListOut>(data)
}

export interface RevisionRow {
  key: string; code: string | null; phase: string | null; round: string | null
  rev_seq: number | null; rev_source: string | null; status: string | null
  decided_by: string | null; decided_at: string | null
  model: string | null; supersedes: string | null; reports: string[]
}
export async function taskRevisions(taskKey: string): Promise<{ task: string; revisions: RevisionRow[] }> {
  const { data } = await api.get(`/ontology/tasks/${encodeURIComponent(taskKey)}/revisions`)
  return unwrap<{ task: string; revisions: RevisionRow[] }>(data)
}

export interface RevisionCandidate {
  code: string; source: string; evidence: string; valid: boolean
  why?: string; phase?: string; round?: string | null; rev_seq?: number
}
export interface TaskCandidate { key: string; label: string; why: string }
export interface ReportRevisionOut {
  report_id: string
  eng_meta: Record<string, unknown>
  free_task: string
  resolved_task: string | null
  resolved_how: string | null
  /** 비어 있지 않으면 수동 메타와 이어진 개정이 **다르다**. 서버는 조용히 맞추지 않는다 —
   *  화면이 보여 주고 사람이 고른다. */
  mismatch: { kind: string; linked: string; eng_meta?: string; said: string } | null
  candidates: RevisionCandidate[]
  task_candidates: TaskCandidate[]
}
export async function reportRevision(reportId: string, taskKey?: string): Promise<ReportRevisionOut> {
  const { data } = await api.get(`/reports/${reportId}/revision`, { params: { task_key: taskKey || undefined } })
  return unwrap<ReportRevisionOut>(data)
}
export async function setReportRevision(reportId: string, body: {
  task_key: string; code: string; model_key?: string; supersedes?: string; note?: string
}): Promise<{ key: string; rev_seq: number; task_unverified: boolean; detail: string }> {
  const { data } = await api.put(`/reports/${reportId}/revision`, body)
  return unwrap<{ key: string; rev_seq: number; task_unverified: boolean; detail: string }>(data)
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
/** 진단 요약(클립보드용)과 본문. `deckLines` 를 켜면 에러가 가리킨 덱 줄이 함께 담긴다 —
 *  고객 모델이 IP 라 기본은 담지 않는다. */
export async function getJobDiagnostics(
  jobId: string, deckLines = false,
): Promise<{ diagnostic: unknown; summary: string }> {
  const { data } = await api.get(`/jobs/${jobId}/diagnostics`, { params: { deck_lines: deckLines } })
  return unwrap<{ diagnostic: unknown; summary: string }>(data)
}
/** 진단 전문 .zip. 기존 downloadFile 과 같은 Blob 선례를 따른다. */
export async function downloadJobDiagnostics(jobId: string, deckLines = false): Promise<void> {
  const res = await api.get(`/jobs/${jobId}/diagnostics.zip`, {
    params: { deck_lines: deckLines }, responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `koorm-diag-${jobId}.zip`
  a.click()
  URL.revokeObjectURL(url)
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
/** 원샷 반입 — 리포트+K파일(+scenario)을 한 호출로. .gz 가능(서버가 해제). */
export interface ReportIntakeResult {
  session_id: string; report_id: string; kfile_id: number | null
  source_kfile_id: number | null; kind: ReportKind; n_cases: number; label: string | null
}
export async function reportIntake(opts: {
  file: File; kfile?: File | null; scenario?: File | null; session_id?: string;
  kind?: string; project?: string; dev_rev?: string; variation?: string; doe?: string; focus?: string;
}): Promise<ReportIntakeResult> {
  const fd = new FormData()
  fd.append('file', opts.file)
  if (opts.kfile) fd.append('kfile', opts.kfile)
  if (opts.scenario) fd.append('scenario', opts.scenario)
  for (const k of ['session_id', 'kind', 'project', 'dev_rev', 'variation', 'doe', 'focus'] as const) {
    const v = opts[k]
    if (v) fd.append(k, v)
  }
  const { data } = await api.post('/reports/intake', fd)
  return unwrap<ReportIntakeResult>(data)
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
/** 과제명·rev·설계안·DOE·원본 K파일 링크 수동 설정(부분 갱신). */
export async function patchReportMeta(
  reportId: string,
  body: Partial<{ label: string; project: string; dev_rev: string; variation: string; doe: string; focus: string; kfile_id: number }>,
): Promise<Report> {
  const { data } = await api.patch(`/reports/${reportId}`, body)
  return unwrap<Report>(data)
}
/** 시뮬 조건(scenario.json) 첨부 — 조건 요약 캐시 + K파일 자동매칭. */
export async function attachReportScenario(reportId: string, file: File): Promise<Report> {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post(`/reports/${reportId}/scenario`, fd)
  return unwrap<Report>(data)
}
// 결과 분석 — 지금까지 MCP 도구로만 열려 있던 것들을 웹에서도 그대로 본다.
export async function reportPartRisk(reportId: string, partId?: number): Promise<ReportPartRisk> {
  const { data } = await api.get(`/reports/${reportId}/parts`, { params: partId != null ? { part_id: partId } : {} })
  return unwrap<ReportPartRisk>(data)
}
export async function reportDirectional(reportId: string, partId?: number): Promise<ReportDirectional> {
  const { data } = await api.get(`/reports/${reportId}/directional`, { params: partId != null ? { part_id: partId } : {} })
  return unwrap<ReportDirectional>(data)
}
export async function reportScatter(
  reportId: string, metric: ScatterMetric = 'peak_stress', partId?: number,
): Promise<ReportScatter> {
  const { data } = await api.get(`/reports/${reportId}/scatter`, {
    params: { metric, ...(partId != null ? { part_id: partId } : {}) },
  })
  return unwrap<ReportScatter>(data)
}
export async function reportEnergy(reportId: string, caseKey?: string): Promise<ReportEnergy> {
  const { data } = await api.get(`/reports/${reportId}/energy`, { params: caseKey ? { case_key: caseKey } : {} })
  return unwrap<ReportEnergy>(data)
}
/** 공간 컨텍스트(부품 위치 시각화) — impact 디바이스 외곽선 + 파트 footprint. */
export async function reportGeometry(reportId: string): Promise<ReportGeometry> {
  const { data } = await api.get(`/reports/${reportId}/geometry`)
  return unwrap<ReportGeometry>(data)
}
/** 한 물리량 기준 (각도/위치 × 값) fact — 마커 시각화용 서버 필터. */
export async function reportQuery(
  reportId: string, opts: { part_id?: number; metric?: string; category?: string; limit?: number } = {},
): Promise<ReportFactQuery> {
  const { data } = await api.get(`/reports/${reportId}/query`, {
    params: { metric: 'peak_stress', limit: 2000, ...opts },
  })
  return unwrap<ReportFactQuery>(data)
}
/** 특정 각도군 표준 통계(분포 + 부품별 위험/민감도) — 선택 모드 인자(미지정=전체 그룹). */
export async function reportAngleStats(
  reportId: string,
  opts: { metric?: string; part_id?: number; category?: string; angle_name?: string; near_lon?: number; near_lat?: number; tol_deg?: number; top_parts?: number } = {},
): Promise<AngleGroupStats> {
  const { data } = await api.get(`/reports/${reportId}/angle-stats`, { params: opts })
  return unwrap<AngleGroupStats>(data)
}
/** 파트별 에너지(IE/KE) 시계열 — deep matsum. part_id 로 한 파트만. */
export async function reportPartEnergy(reportId: string, partId?: number): Promise<PartEnergySeries> {
  const { data } = await api.get(`/reports/${reportId}/part-energy`, { params: partId != null ? { part_id: partId } : {} })
  return unwrap<PartEnergySeries>(data)
}
export async function reportPartSeries(
  reportId: string, caseKey: string, partId: number,
): Promise<ReportPartSeries> {
  const { data } = await api.get(`/reports/${reportId}/cases/${encodeURIComponent(caseKey)}/series`, {
    params: { part_id: partId },
  })
  return unwrap<ReportPartSeries>(data)
}
/** 원본 리포트 HTML 을 blob URL 로 (iframe src 용 — 인증 헤더가 필요해 직접 fetch).
 *  백엔드 download 는 octet-stream 이라 iframe 이 다운로드해버린다 → text/html 로 리타입. */
export async function reportHtmlBlobUrl(sessionId: string, fileId: number): Promise<string> {
  const res = await api.get(`/sessions/${sessionId}/files/${fileId}/download`, { responseType: 'blob' })
  const html = new Blob([res.data as Blob], { type: 'text/html' })
  return URL.createObjectURL(html)
}

/** 산출 SVG(단면 그림)를 그림으로 띄울 blob URL. `reportHtmlBlobUrl` 과 같은 선례다.
 *
 * ⚠ 이것은 **`<img src>` 로만** 쓴다. SVG 는 스크립트를 실을 수 있고 파트 제목은 `*PART` 다음
 * 줄의 자유 텍스트라 무엇이든 들어 있다(op 쪽이 이스케이프하지만 방어는 두 겹이어야 한다).
 * `<img>` 로 불러들인 SVG 는 스크립트가 **실행되지 않는다** — `dangerouslySetInnerHTML` 이나
 * `<object>`·`<iframe>` 으로 바꾸면 그 보호가 사라진다. 다운로드 엔드포인트가 MIME 을
 * `application/octet-stream` 으로 주므로 타입은 여기서 정한다. */
export async function svgBlobUrl(sessionId: string, fileId: number): Promise<string> {
  const res = await api.get(`/sessions/${sessionId}/files/${fileId}/download`, { responseType: 'blob' })
  const svg = new Blob([res.data as Blob], { type: 'image/svg+xml' })
  return URL.createObjectURL(svg)
}

/** 리포트 임베드 블록 전수 — 무엇이 들어 있나 / 무엇이 아직 해석 안 되나. */
export async function reportBlocks(reportId: string): Promise<ReportBlocks> {
  const { data } = await api.get(`/reports/${reportId}/blocks`)
  return unwrap<ReportBlocks>(data)
}
/** 핫스팟 군집(deep) — 어디가 뜨거운가. */
export async function reportHotspots(
  reportId: string, opts: { criterion?: string; part_id?: number; top?: number; order?: string } = {},
): Promise<ReportHotspots> {
  const { data } = await api.get(`/reports/${reportId}/hotspots`, { params: opts })
  return unwrap<ReportHotspots>(data)
}
/** 거동 아키타입 군집(impact). */
export async function reportBehaviorClusters(reportId: string): Promise<ReportBehaviorClusters> {
  const { data } = await api.get(`/reports/${reportId}/clusters`)
  return unwrap<ReportBehaviorClusters>(data)
}
/** 큰 분석 블록 요약 — 생성기 summary 를 그대로 싣는다. */
export async function reportAnalytics(reportId: string, block?: string): Promise<ReportAnalytics> {
  const { data } = await api.get(`/reports/${reportId}/analytics`, { params: block ? { block } : {} })
  return unwrap<ReportAnalytics>(data)
}
/** 결과 이미지·영상 목록. 내용은 `mediaBlobUrl` 로 받는다. */
export async function reportMedia(
  reportId: string, opts: { case_key?: string; kind?: string; role?: string; images_only?: boolean } = {},
): Promise<ReportMedia> {
  const { data } = await api.get(`/reports/${reportId}/media`, { params: opts })
  return unwrap<ReportMedia>(data)
}

/** 결과 이미지를 `<img src>` 로 띄울 blob URL.
 *
 * ⚠ `svgBlobUrl` 과 같은 선례이고 같은 이유로 **`<img>` 로만** 쓴다. 다운로드 엔드포인트가
 * MIME 을 `application/octet-stream` 으로 주므로 타입을 여기서 정한다. 확장자로 정하되
 * 모르는 것은 png 로 두지 않고 그대로 octet-stream 을 쓴다 — 틀린 타입을 억지로 붙이면
 * 브라우저가 깨진 그림을 조용히 보여 준다. */
export function mediaMime(path: string): string {
  const ext = path.toLowerCase().slice(path.lastIndexOf('.'))
  const m: Record<string, string> = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.gif': 'image/gif', '.webp': 'image/webp',
    '.mp4': 'video/mp4', '.webm': 'video/webm',
  }
  return m[ext] ?? 'application/octet-stream'
}
export async function mediaBlobUrl(sessionId: string, fileId: number, path: string): Promise<string> {
  const res = await api.get(`/sessions/${sessionId}/files/${fileId}/download`, { responseType: 'blob' })
  return URL.createObjectURL(new Blob([res.data as Blob], { type: mediaMime(path) }))
}
