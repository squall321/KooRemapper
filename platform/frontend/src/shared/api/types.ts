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
  // true 면 2차(고차) 솔리드 파트다(ELFORM 16·17·23~29). 2026-10-17 부터 리더가 절점 칸을 다 읽고 코너를 제자리에
  //   놓으므로 기하 값(area_ext·volume·proj)은 **코너로 잰 값**이다 — `geometry_basis: 'corners'`(휜 모서리는 곧게 본다).
  //   기하를 믿을 수 없는 파트(코너 차례를 모르는 ELFORM 25~28 · 칸이 모자란 카드)만 값이 **null** 이고 까닭은
  //   `geometry_reason`. (2026-10-16 까지는 리더가 앞 8칸만 담아 2차 파트 전부가 null 이었다 — 실측 부피 -48.4%.)
  //   플래그를 파트에도 두는 이유는, 파트 하나만 읽는 소비자가 모델 수준 목록을 못 보기 때문이다.
  second_order?: boolean
  geometry_basis?: 'nodes' | 'corners' | null
  geometry_reason?: string | null
  area_ext: number | null
  volume: number | null
  proj: { x: number; y: number; z: number } | null
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
  /** `*CONTACT_…_ID` 의 CID(없으면 null) — 결과 쪽 접촉 id 와 잇는 열쇠. */
  cid?: number | null
  title?: string
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
  /** 못 푼 접촉 면마다 까닭(`_GENERAL`·`_ADVANCED`·순환·없는 세트…) — 그 면의 파트쌍은 연결도에 없다. */
  unresolved_detail?: { contact: number; cid?: number | null; type: string; title: string; side: string; sid: number; styp: number; why: string }[]
}

export interface ModelMeta {
  parts: ModelPart[]
  connectivity: ModelConnectivity
  conventions?: Record<string, string>
  // ⚠ bbox 는 **두 기준**이다. `bbox_all_*` 는 `*NODE` 전체(고아 포함),
  //   `bbox_used_*` 와 `parts[].bbox_*` 는 요소가 쓰는 절점이다.
  //   낙하판·접촉면은 **used** 기준으로 놓아야 한다 — 현장에서 두 값이 14.55mm vs 67.50mm 로
  //   갈려 낙하판이 기기 밖 53mm 에 생겼다. 선언이 없으면 이 신호가 조용히 사라진다.
  // 2차 솔리드 파트가 있으면 센 고아는 상한일 뿐이라 0 이 아닐 때 null 로 온다 — 까닭은 `orphan_nodes_reason`.
  orphan_nodes?: number | null
  orphan_nodes_reason?: string | null
  bbox_basis?: string
  bbox_all_min?: number[]
  bbox_all_max?: number[]
  bbox_used_min?: number[]
  bbox_used_max?: number[]
  // ★2차 솔리드(ELFORM 16·17·23~29)를 쓰는 파트 전부. `geometry_basis` 가 'corners' 면 기하 값을 코너로 쟀고,
  //   null 이면 그 파트의 volume·area_ext·proj·edge_len 이 null 이다(코너 차례를 모르는 ELFORM 25~28 · 칸이 모자란 카드).
  //   파트별로는 `ModelPart.second_order`·`geometry_basis`.
  second_order_solid_pids?: { pid: number; elform: number; geometry_basis?: 'corners' | null }[]
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
  // 성공한 잡에도 남는 경고(개행 왕복 등) — rc=0 인데 산출 덱이 상한 경우가 실제 사고의 모양이었다
  warnings: string[] | null
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

// 폼 한 칸의 스키마. `x-group` 은 화면이 칸을 묶을 이름이다(칸이 수십 개인 작업용).
export interface PropDef {
  type: string
  description?: string
  enum?: unknown[]
  default?: unknown
  'x-kind'?: string
  'x-group'?: string
}

export interface JsonSchema {
  type: string
  properties: Record<string, PropDef>
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
/** 하중경로 노드(파트·충격체). 압축본에는 원해상도 피크가 없어 null 이다(`form_note`). */
export interface EnergyFlowNode {
  node_id: string | null
  name?: string | null
  is_impactor: boolean
  peak_ke: number | null
  peak_ie: number | null
  final_ke: number | null
  final_ie: number | null
}
export interface EnergyFlowEdge {
  src: string
  dst: string
  name?: string | null
  contact_id?: number | null
  peak_force: number | null
  total_work: number | null
  total_impulse: number | null
  confidence: number | null
  first_engage_idx?: number | null
  first_engage_t?: number | null
}
export interface EnergyFlow {
  form: 'neutral' | 'html_compact'
  form_note?: string
  impactor_ke_initial: number | null
  impactor_ke_final: number | null
  energy_dissipated: number | null
  propagation_order?: string[] | null
  nodes: EnergyFlowNode[]
  edges: EnergyFlowEdge[]
  contact?: Record<string, unknown>
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
  energy_flow?: EnergyFlow | null
  /** 실제로 쓴 케이스 — case_key 를 안 주면 대표 하나, 주었는데 상세가 없으면 null(다른 각도로 떨어지지 않는다). */
  flow_case_key?: string | null
  n_flows?: number
  /** 상세(시계열)는 생성기가 상위 각도에만 싣는다 — 그 사유. */
  detail_note?: string
  available_case_keys?: string[]
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
  // ⚠ `synthetic_footprint` — 상류 생성기가 **파트 id 해시로 지어낸** 사각형이라는 표시다
  //   (실측 형상이 아니다). 그리는 쪽이 반드시 가려 보여야 한다.
  parts: Array<{ part_id: number; name: string | null; group: string | null; footprint: number[][] | null; synthetic_footprint?: boolean; zmin: number | null; zmax: number | null }>
  synthetic_footprints?: number
  footprints_are_measured?: boolean
  footprint_warning?: string
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

// ── 리포트 블록·핫스팟·군집·미디어 (2026-10-13) ──────────────────────────────
// ★왜 이 타입들이 있나 — 리포트 임베드 데이터의 블록 상당수가 플랫폼에서 **버려지고** 있었다
//   (실측: deep 21키 중 11, impact 27키 중 18). 그중에 핫스팟 군집 102레코드와 거동 군집이
//   있었다. 선언이 없으면 신호가 조용히 사라지므로 여기에 적어 둔다.

export interface ReportBlock {
  name: string
  type: string
  count: number | null
  sub_keys: string[]
  item_type?: string | null
  bytes: number
  /** 정규화가 해석하는가. false 는 "쓸 수 없다" 가 아니라 "아직 해석 안 한다" 다. */
  read_by_parser: boolean
}
export interface ReportBlocks {
  n_blocks: number
  n_unread: number
  blocks: ReportBlock[]
}

export interface HotspotCluster {
  part_id: number
  part_name?: string | null
  criterion?: string | null
  direction?: string | null
  /** ⚠ true 면 값이 고르다 — 그 군집은 '가장 뜨거운 곳' 이 **아니다**. */
  uniform: boolean
  top_percent?: number | null
  threshold_value?: number | null
  distance_threshold?: number | null
  element_count_selected?: number | null
  element_count_total?: number | null
  rank?: number | null
  center?: number[] | null
  radius_enclosing?: number | null
  radius_rms?: number | null
  element_count?: number | null
  volume?: number | null
  /** ⚠ `min_principal` 기준의 값은 **음수**다 — 크기는 절대값으로 비교해야 한다. */
  stress_max?: number | null
  stress_mean?: number | null
  strain_max?: number | null
  peak_element_id?: number | null
  peak_time?: number | null
  /** sphere — 그 군집이 난 각도 런. */
  case_key?: string | null
  angle?: { name?: string | null; roll?: number | null; pitch?: number | null; yaw?: number | null; category?: string | null } | null
  energy_total?: number | null
  energy_max?: number | null
}
/** sphere — 파트 × 기준마다 **전 각도에서** 가장 센 군집 하나. */
export interface HotspotEnvelope {
  part_id: number | null
  part_name?: string | null
  criterion?: string | null
  n_angles: number
  worst_case_key: string | null
  worst_angle?: HotspotCluster['angle']
  stress_max: number | null
  element_count?: number | null
  radius_enclosing?: number | null
  center?: number[] | null
  peak_time?: number | null
}
export interface ReportHotspots {
  available: boolean
  kind?: ReportKind
  n_records?: number
  n_clusters?: number
  n_clusters_all?: number
  n_angles_total?: number
  n_angles_with_clusters?: number
  envelope?: HotspotEnvelope[]
  envelope_note?: string
  /** 생성기 상한(군집 2만)에 걸려 일부만 실렸다는 말 — 조용히 자른 것이 아니다. */
  cap_note?: string
  /** HTML 압축본에 없는 값(uniform·부피·평균응력) — 지어내지 않는다. */
  compact_note?: string
  mesh_note?: string
  hotspot_parts?: number[] | null
  criteria?: string[]
  parts?: number[]
  order?: string
  order_note?: string
  clusters: HotspotCluster[]
  uniform_records?: number
  uniform_note?: string
  truncated?: { returned: number; total: number }
  note?: string
}

export interface BehaviorClusterGroup {
  archetype: string
  index: number | null
  n_positions: number
  positions: string[]
}
export interface ReportBehaviorClusters {
  available: boolean
  n_clusters?: number | null
  n_archetypes_used?: number
  /** ⚠ true 면 선언한 군집 수와 **실제로 쓰인** 수가 다르다 — "N 가지 거동" 으로 읽으면 안 된다. */
  degenerate?: boolean
  degenerate_note?: string
  /** ⚠ true 면 **합성**이다 — 결론의 근거로 쓰면 안 된다. */
  is_mock?: boolean
  mock_note?: string
  archetypes?: string[]
  features_used?: string[]
  n_positions_labeled?: number
  groups?: BehaviorClusterGroup[]
  note?: string
}

export interface AnalyticsSub {
  name: string
  summary?: unknown
  values?: Record<string, unknown>
  detail_shape?: Record<string, unknown>
  /** "값이 0" 이 아니라 **계산되지 않았다**는 뜻. */
  not_computed?: string[]
  not_computed_note?: string
  shape?: unknown
}
export interface ReportAnalyticsBlock {
  name: string
  available: boolean
  bytes?: number
  n_subs?: number
  subs?: AnalyticsSub[]
  note?: string
}
export interface ReportAnalytics {
  n_blocks: number
  requested?: string | null
  raw_access_note?: string
  blocks: ReportAnalyticsBlock[]
}

export interface ReportMediaItem {
  path: string
  stored_as?: string
  file_id: number
  bytes: number
  kind: 'image' | 'video'
  /** ⚠ 모델이 볼 수 있는지 — png/jpeg/gif/webp 는 보고 **mp4 는 못 본다**. */
  can_llm_view: boolean
  case_key?: string | null
  set_name?: string | null
  role?: string | null
  declared?: boolean
}
export interface ReportMedia {
  report_id: string
  kind: string
  n_total: number
  n_returned: number
  n_images: number
  n_videos: number
  cases_with_media: string[]
  media: ReportMediaItem[]
  note?: string
}

// ── 파트쌍 × 각도(위치) 접촉 프로파일 (sphere · impact) ──────────────────────
export interface ContactProfilePair {
  key: string
  src: string
  dst: string
  src_name?: string | null
  dst_name?: string | null
  contact_id?: number | null
  name?: string | null
  /** false 면 접촉 정의가 파트로 분해되지 않았다(single-surface 등) — 파트쌍이 아니다. */
  resolved: boolean
  n_engaged: number
  peak: number | null
  peak_case_key: string | null
  peak_label: string | null
}
export interface ContactProfileAxis {
  case_key: string | null
  label: string | null
  roll?: number | null
  pitch?: number | null
  yaw?: number | null
  category?: string | null
  x?: number | null
  y?: number | null
  face?: string | null
  n_engaged: number
  top_pair: string | null
  top_value: number | null
}
export interface ContactProfileEdge {
  key: string
  src: string
  dst: string
  src_name?: string | null
  dst_name?: string | null
  name?: string | null
  resolved: boolean
  peak_force: number | null
  total_impulse: number | null
  total_work: number | null
}
export type ContactMetric = 'pf' | 'ti' | 'tw'
export interface ReportContactProfile {
  available: boolean
  kind: ReportKind
  metric: ContactMetric
  metric_name?: string
  note?: string
  error?: string
  trust?: { n_runs?: number; n_available?: number; n_interfaces?: number; newton3_worst_rel?: number | null; n_one_sided?: number }
  axis_kind?: 'angle' | 'position'
  n_pairs?: number
  n_resolved?: number
  n_axis?: number
  pairs?: ContactProfilePair[]
  axis_summary?: ContactProfileAxis[]
  at?: { case_key: string; found: boolean; label?: string | null; edges?: ContactProfileEdge[]; note?: string }
  /** 히트맵용 — None 칸은 '그 각도에 그 접촉이 없다'(0 이 아니다). 크면 null + matrix_note. */
  matrix?: { pairs: string[]; values: (number | null)[][] } | null
  matrix_note?: string
}
