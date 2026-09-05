// API envelope + domain types (mirror backend schemas).

export interface Envelope<T> {
  success: boolean
  data: T
  message: string | null
  errors: unknown
}

export interface User {
  id: number
  email: string
  display_name: string | null
  is_system_admin: boolean
  created_at: string
}

export interface TokenInfo {
  id: number
  name: string
  token_prefix: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
  status: 'active' | 'expired' | 'revoked'
}

export interface TokenCreated {
  token: string
  info: TokenInfo
  mcp_add: string
}

export interface SessionSummary {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
  file_count: number | null
}

export interface ModelPart {
  pid: number
  title: string
  elem_class: string
  n_elems: number
  area_ext: number
  volume: number
  proj: { x: number; y: number; z: number }
  material: {
    mid: number
    kfile?: { keyword?: string; name?: string; E?: number; nu?: number; rho?: number }
    db?: { name: string; category: string; match_basis: string; E_GPa: number } | null
  }
}

export interface ModelEdge {
  a: number
  b: number
  a_title: string
  b_title: string
  type?: string
  fs?: number
  gap_min?: number
}

export interface ModelConnectivity {
  contact_edges: ModelEdge[]
  single_surface: { contact: number; type: string; title: string; pids: number[] }[]
  geometric_edges?: ModelEdge[]
  contacts_total: number
  unresolved_sides: number
}

export interface ModelMeta {
  parts: ModelPart[]
  connectivity: ModelConnectivity
  conventions?: Record<string, string>
  detect?: boolean
  error?: string
}

export interface FileMeta {
  nodes?: number
  elements?: number
  parts?: number
  bbox_min?: number[]
  bbox_max?: number[]
  size?: number[]
  valid?: boolean
  includes?: string[]
  part_titles?: string[]
  keyword_counts?: Record<string, number>
  info_error?: string
  modelmeta?: ModelMeta
  [k: string]: unknown
}

export interface SessionFile {
  id: number
  session_id: string
  filename: string
  kind: 'input' | 'output' | 'generated'
  origin_job_id: string | null
  size_bytes: number
  sha256: string | null
  meta: FileMeta | null
  created_at: string
}

export interface SessionDetail extends SessionSummary {
  files: SessionFile[]
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

export interface Job {
  id: string
  session_id: string
  operation: string
  args: Record<string, unknown>
  resolved_cmd: { argv?: string[]; written_files?: string[]; error?: string } | null
  status: JobStatus
  progress: number | null
  exit_code: number | null
  input_file_ids: number[] | null
  output_file_ids: number[] | null
  error_summary: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface OperationSummary {
  name: string
  category: string
  summary: string
  invocation: 'positional' | 'yaml'
  takes_kfile: boolean
  requires_gmsh: boolean
  requires_tetgen: boolean
}

export interface OperationParam {
  name: string
  type: string
  role: string
  required: boolean
  description: string
  order?: number | null
  flag?: string | null
  yaml_path?: string | null
  enum?: string[] | null
  default?: unknown
}

export interface JsonSchema {
  type: string
  properties: Record<string, { type: string; description?: string; enum?: unknown[]; default?: unknown; 'x-kind'?: string }>
  required: string[]
  additionalProperties: boolean
}

export interface OperationKey {
  path: string
  type: string
  required: boolean
  default?: string | null
  values?: string[] | null
  desc: string
}

export interface OperationPreset {
  name: string
  summary: string
}

export interface OperationDetail extends OperationSummary {
  description: string
  config_style: 'structured' | 'freeform' | null
  params: OperationParam[]
  example: { args: Record<string, unknown>; note: string }
  example_folder: string
  notes: string
  args_schema: JsonSchema
  // deep option reference (source-grounded enrichment); optional for back-compat
  keys?: OperationKey[]
  presets?: OperationPreset[] | null
}

// 낙하/충격 리포트 (deep/sphere/impact)
export type ReportKind = 'deep' | 'sphere' | 'impact'
export interface ReportFinding {
  severity: string
  title: string
  detail: string
  recommendation: string
}
export interface ReportListItem {
  id: string
  kind: ReportKind
  label: string | null
  project_name: string | null
  n_cases: number
  created_at: string
}
export interface Report extends ReportListItem {
  session_id: string
  focus?: string | null              // 초점 라벨(camera-detail 등)
  source_file_id: number | null
  source_kfile_id?: number | null   // 원본 K파일 (1 K : N 리포트)
  scenario_file_id?: number | null
  scenario?: Record<string, unknown> | null  // 시뮬 조건 요약
  scenario_type?: string | null
  eng_meta?: Record<string, unknown> | null  // 과제/rev 수동 메타
  drop_height?: number | null
  worst_stress?: number | null
  worst_g?: number | null
  max_severity?: string | null
  generator: string | null
  doe_strategy: string | null
  test_dir: string | null
  sim_params: Record<string, unknown> | null
  parts: Array<{ part_id: number; name: string; group: string }> | null
  findings: ReportFinding[] | null
  summary: Record<string, unknown> | null
}
/** 최악값 + 그 값이 나온 케이스 — 분석 응답이 공통으로 쓰는 모양. */
export interface WorstRef {
  value: number | null
  case_key: string | null
  part_id?: number | null
  part_name?: string | null
}
export interface ReportPartRisk {
  report_id: string
  kind: ReportKind
  parts: Array<{
    part_id: number
    part_name: string | null
    worst_stress: WorstRef
    worst_g: WorstRef
    worst_disp: WorstRef
    min_safety_factor: number | null
  }>
}
export interface ReportDirectional {
  report_id: string
  kind: ReportKind
  part_id: number | null
  directions: Array<{
    category: string
    n_cases: number
    worst_stress: WorstRef
    worst_g: WorstRef
  }>
}
export type ScatterMetric = 'peak_stress' | 'peak_g' | 'peak_disp'
export interface ReportScatter {
  kind: ReportKind
  note?: string
  metric?: ScatterMetric
  part_id?: number | null
  n_cases?: number
  n_bases?: number
  /** 방향당 표본이 1개뿐이라 산포가 0인 상태 — 값이 아니라 DOE 설계의 문제다. */
  degenerate?: boolean
  most_severe?: { base?: string; representative?: string | null; worst_value?: number | null } | null
  most_scattered?: { base?: string; representative?: string | null; cov?: number | null } | null
  groups?: Array<{
    base: string
    category: string
    representative: string | null
    n: number
    mean: number | null
    std: number | null
    cov: number | null
    min: number | null
    max: number | null
    worst_value: number | null
    worst_case_key: string | null
  }>
}
export interface ReportEnergy {
  kind: ReportKind
  note?: string
  energy_balance?: {
    energy_ratio_min: number | null
    energy_ratio_max: number | null
    has_mass_added: boolean | null
    normal_termination: boolean | null
  }
  /** deep: {t:[], <계열명>:[]}. sphere/impact 는 energy_flow 쪽에 담긴다. */
  energy_series?: Record<string, number[]> | null
  energy_flow?: Record<string, unknown> | null
  contacts?: Array<{ id: number | null; name: string | null; side: number | string | null; peak_fmag: number | null }>
  contact_metrics?: Record<string, unknown> | null
  has_matsum?: boolean
}
/** 시계열 — kind 마다 담기는 키가 다르다(deep=stress/motion, sphere=*_ts). */
export interface ReportPartSeries {
  kind: ReportKind
  case_key?: string
  part_id: number
  note?: string
  stress?: Record<string, { t?: number[]; max?: number[]; avg?: number[]; global_max?: number | null }>
  motion?: Record<string, unknown>
  stress_ts?: number[][] | null
  strain_ts?: number[][] | null
  g_ts?: number[][] | null
  disp_ts?: number[][] | null
}
export interface ReportGeometry {
  kind: ReportKind
  device_outline: number[][] | null
  device_bbox: { xmin: number; xmax: number; ymin: number; ymax: number } | null
  parts: Array<{ part_id: number; name: string | null; group: string | null; footprint: number[][] | null; zmin: number | null; zmax: number | null }>
}
export interface ReportFact {
  case_key: string
  identity: Record<string, unknown> | null
  part_id: number
  part_name: string | null
  quantity: string
  value: number
  at_time?: number
}
export interface ReportFactQuery {
  report_id: string
  kind: ReportKind
  metric: string
  n_matched: number
  returned: number
  truncated: boolean
  facts: ReportFact[]
}
/** 각도군 표준 통계 — 분포(백분위·IQR·CoV) + 부품별 위험·민감도. */
export interface AngleStatBlock {
  n: number; mean: number; std: number; cov: number | null
  min: number; p05: number; p25: number; median: number; p75: number; p95: number; max: number
  iqr: number; range: number
}
export interface AnglePartRow {
  part_id: number; part_name: string | null; n: number; mean: number; worst: number; cov: number | null
}
export interface AngleGroupStats {
  report_id: string
  kind: ReportKind
  metric: string
  part_id: number | null
  available_metrics: string[]
  selection?: { mode: string; category?: string; angle_name?: string; near_lon?: number; near_lat?: number; tol_deg?: number }
  n_cases_total: number
  n_groups?: number
  groups: Array<{
    group_key: string
    category: string
    representative: string | null
    stats: AngleStatBlock
    worst: { value: number; angle_name: string | null; part_id: number; part_name: string | null; case_key: string }
    parts?: { top_risk: AnglePartRow[]; most_sensitive: AnglePartRow[] }
  }>
  note?: string | null
}
/** 파트별 에너지(내부 IE·운동 KE) 시계열 — deep matsum(있을 때). */
export interface PartEnergySeries {
  kind: ReportKind
  t?: number[] | null
  part_id?: number | null
  parts: Array<{
    part_id: number; part_name: string | null
    internal_energy: number[] | null; kinetic_energy: number[] | null
    peak_internal_energy: number | null; peak_kinetic_energy: number | null
    hourglass_energy?: number[]
  }>
  note?: string | null
}

export interface ReportCase {
  id: number
  report_id: string
  case_key: string
  identity: Record<string, unknown> | null
  num_states: number | null
  success: boolean | null
  parts_metrics: Record<string, Record<string, number | null>> | null
  max_stress: number | null
  max_g: number | null
  max_disp: number | null
  min_safety_factor: number | null
}
