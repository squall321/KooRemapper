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
  source_file_id: number | null
  generator: string | null
  doe_strategy: string | null
  test_dir: string | null
  sim_params: Record<string, unknown> | null
  parts: Array<{ part_id: number; name: string; group: string }> | null
  findings: ReportFinding[] | null
  summary: Record<string, unknown> | null
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
