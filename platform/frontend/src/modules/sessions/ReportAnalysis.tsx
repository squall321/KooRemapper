// 낙하/충격 리포트 결과 분석 뷰 — 방향취약도·산포·에너지·파트위험도·시계열.
// 지금까지 MCP 도구로만 열려 있던 분석을 웹에서도 같은 깊이로 본다.
//
// 차트는 인라인 SVG 다. 차트 라이브러리를 넣지 않는 이유는 둘이다 —
//   ① 이 화면이 쓰는 형태가 가로 막대·오차막대·꺾은선 셋뿐이라 라이브러리 값어치가 없고,
//   ② 번들이 커지면 포탈 서브패스 빌드까지 두 벌로 늘어난다(현재 399KB).
// 색은 전부 테마 토큰(currentColor/text-*)으로 잡아 라이트·다크가 자동으로 따라온다.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, Compass, Layers, LineChart } from 'lucide-react'
import {
  reportDirectional, reportEnergy, reportPartRisk, reportPartSeries, reportScatter,
} from '@/shared/api/endpoints'
import type {
  Report, ReportCase, ReportDirectional, ReportEnergy, ReportPartRisk, ReportPartSeries,
  ReportScatter, ScatterMetric,
} from '@/shared/api/types'
import { Badge, EmptyState, Spinner } from '@/shared/ui/ui'

// ── 표시 유틸 ────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, d = 1): string {
  return n == null ? '—' : Number(n).toFixed(d)
}
/** 값의 크기에 상관없이 읽히게 — 1000 이상은 천단위, 0.01 미만은 지수. */
function smart(n: number | null | undefined): string {
  if (n == null) return '—'
  const a = Math.abs(n)
  if (a >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (a > 0 && a < 0.01) return n.toExponential(1)
  return n.toFixed(a >= 100 ? 0 : a >= 1 ? 1 : 3)
}
const METRIC_LABEL: Record<ScatterMetric, string> = {
  peak_stress: '최대응력', peak_g: '최대 G', peak_disp: '최대변위',
}

// ── 차트 프리미티브 ──────────────────────────────────────────────────────────
/** 가로 막대 — 크기 비교용. 값은 막대 끝에 직접 라벨한다(범례 없이 읽히게). */
function BarRow({ label, value, max, hint, tone = 'primary' }: {
  label: string; value: number | null; max: number; hint?: string; tone?: 'primary' | 'danger'
}) {
  const pct = value != null && max > 0 ? Math.max(1.5, (value / max) * 100) : 0
  return (
    <div className="flex items-center gap-2 py-[3px]">
      {/* 라벨·힌트는 넓은 화면에서 더 준다 — 파트명과 케이스 키가 잘리면 표가 아니라 그림이 된다. */}
      <span className="w-28 lg:w-44 shrink-0 truncate text-muted" title={label}>{label}</span>
      <div className="flex-1 h-3 rounded-sm bg-muted/15 overflow-hidden">
        <div
          className={`h-full rounded-sm ${tone === 'danger' ? 'bg-danger' : 'bg-primary'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-16 shrink-0 text-right tabular-nums text-fg">{smart(value)}</span>
      {hint && <span className="w-24 lg:w-56 shrink-0 truncate text-muted" title={hint}>{hint}</span>}
    </div>
  )
}

/** 평균 ± 표준편차 — 산포는 평균만 보면 안 된다. 최악값 위치를 같이 찍는다. */
function SpreadRow({ label, mean, std, min, max, worst, domainMax, cov }: {
  label: string; mean: number | null; std: number | null; min: number | null
  max: number | null; worst: number | null; domainMax: number; cov: number | null
}) {
  const p = (v: number | null) => (v != null && domainMax > 0 ? (v / domainMax) * 100 : 0)
  const lo = mean != null && std != null ? Math.max(0, mean - std) : mean
  const hi = mean != null && std != null ? mean + std : mean
  const hot = (cov ?? 0) >= 0.15   // 변동계수 15% 이상 = 방향에 민감하다
  return (
    <div className="flex items-center gap-2 py-[3px]">
      <span className="w-24 lg:w-40 shrink-0 truncate font-mono text-[10px] text-muted" title={label}>{label}</span>
      <div className="relative flex-1 h-3">
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-px bg-border" />
        {/* min–max 범위 */}
        <div className="absolute top-1/2 -translate-y-1/2 h-[3px] rounded-sm bg-muted/40"
             style={{ left: `${p(min)}%`, width: `${Math.max(0.5, p(max) - p(min))}%` }} />
        {/* ±1σ */}
        <div className={`absolute top-1/2 -translate-y-1/2 h-[7px] rounded-sm ${hot ? 'bg-warning/50' : 'bg-primary/40'}`}
             style={{ left: `${p(lo)}%`, width: `${Math.max(0.5, p(hi) - p(lo))}%` }} />
        {/* 평균 */}
        <div className="absolute top-1/2 -translate-y-1/2 w-[2px] h-[11px] bg-fg" style={{ left: `${p(mean)}%` }} />
        {/* 최악 */}
        {worst != null && (
          <div className="absolute top-1/2 -translate-y-1/2 w-[2px] h-[11px] bg-danger" style={{ left: `${p(worst)}%` }} />
        )}
      </div>
      <span className="w-14 shrink-0 text-right tabular-nums text-fg">{smart(mean)}</span>
      <span className={`w-12 shrink-0 text-right tabular-nums ${hot ? 'text-warning' : 'text-muted'}`}>
        {cov == null ? '—' : `${(cov * 100).toFixed(0)}%`}
      </span>
    </div>
  )
}

/** 꺾은선 — 시계열용. 값 범위를 자동으로 잡고 마지막 점을 강조한다. */
function Sparkline({ xs, ys, height = 120 }: { xs: number[]; ys: number[]; height?: number }) {
  const n = Math.min(xs.length, ys.length)
  if (n < 2) return <div className="text-muted text-[11px] py-4">표시할 시계열이 없습니다.</div>
  const xMin = xs[0], xMax = xs[n - 1] || 1
  let yMin = Infinity, yMax = -Infinity
  for (let i = 0; i < n; i++) { if (ys[i] < yMin) yMin = ys[i]; if (ys[i] > yMax) yMax = ys[i] }
  if (!isFinite(yMin) || !isFinite(yMax)) return null
  const span = yMax - yMin || 1
  const W = 1000, H = height, PAD = 4
  const px = (x: number) => ((x - xMin) / ((xMax - xMin) || 1)) * (W - PAD * 2) + PAD
  const py = (y: number) => H - PAD - ((y - yMin) / span) * (H - PAD * 2)
  let d = ''
  for (let i = 0; i < n; i++) d += `${i ? 'L' : 'M'}${px(xs[i]).toFixed(1)},${py(ys[i]).toFixed(1)}`
  const peakIdx = ys.indexOf(yMax)
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full text-primary" style={{ height }}>
        <path d={d} fill="none" stroke="currentColor" strokeWidth={2} vectorEffect="non-scaling-stroke" />
        {peakIdx >= 0 && (
          <circle cx={px(xs[peakIdx])} cy={py(yMax)} r={3} className="fill-danger" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="flex justify-between text-[10px] text-muted tabular-nums">
        <span>{smart(xMin)}</span>
        <span className="text-danger">최대 {smart(yMax)}</span>
        <span>{smart(xMax)}</span>
      </div>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'bad' }) {
  return (
    <div className="rounded border border-border px-2.5 py-1.5 min-w-[104px]">
      <div className="text-[10px] text-muted">{label}</div>
      <div className={`text-sm tabular-nums ${tone === 'bad' ? 'text-danger' : tone === 'ok' ? 'text-success' : 'text-fg'}`}>
        {value}
      </div>
    </div>
  )
}

// ── 탭 ───────────────────────────────────────────────────────────────────────
type TabKey = 'parts' | 'directional' | 'scatter' | 'energy' | 'series'
const TABS: Array<{ key: TabKey; label: string; icon: typeof Layers; kinds?: string[] }> = [
  { key: 'parts', label: '파트 위험도', icon: Layers },
  { key: 'directional', label: '방향 취약도', icon: Compass },
  { key: 'scatter', label: '방향 산포', icon: Activity, kinds: ['sphere'] },
  { key: 'energy', label: '에너지·접촉', icon: AlertTriangle },
  { key: 'series', label: '파트 시계열', icon: LineChart },
]

export function ReportAnalysis({ report, cases }: { report: Report; cases: ReportCase[] }) {
  const [tab, setTab] = useState<TabKey>('parts')
  // sphere 전용 탭은 다른 리포트에서 아예 숨긴다 — 눌러서 "지원 안 함"을 보는 것보다 낫다.
  const tabs = TABS.filter((t) => !t.kinds || t.kinds.includes(report.kind))

  return (
    <div className="border border-border rounded">
      <div className="flex flex-wrap gap-1 p-1 border-b border-border bg-muted/10">
        {tabs.map((t) => {
          const Icon = t.icon
          const on = tab === t.key
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition ${
                on ? 'bg-primary text-primary-fg' : 'text-muted hover:text-fg'
              }`}
            >
              <Icon size={12} /> {t.label}
            </button>
          )
        })}
      </div>
      <div className="p-3">
        {tab === 'parts' && <PartsView reportId={report.id} />}
        {tab === 'directional' && <DirectionalView reportId={report.id} />}
        {tab === 'scatter' && <ScatterView reportId={report.id} />}
        {tab === 'energy' && <EnergyView reportId={report.id} cases={cases} />}
        {tab === 'series' && <SeriesView report={report} cases={cases} />}
      </div>
    </div>
  )
}

// ── 파트 위험도 ──────────────────────────────────────────────────────────────
function PartsView({ reportId }: { reportId: string }) {
  const q = useQuery<ReportPartRisk>({ queryKey: ['report-parts', reportId], queryFn: () => reportPartRisk(reportId) })
  if (q.isLoading) return <Spinner />
  const parts = q.data?.parts ?? []
  if (!parts.length) return <EmptyState title="파트 정보 없음" hint="리포트에 파트별 지표가 없습니다." />
  const rows = [...parts].sort((a, b) => (b.worst_stress.value ?? -1) - (a.worst_stress.value ?? -1))
  const max = rows[0]?.worst_stress.value ?? 0
  return (
    <div className="space-y-2 text-[11px]">
      <div className="text-muted">최대응력 기준 정렬 — 막대 옆은 그 값이 나온 케이스입니다.</div>
      {rows.map((p) => (
        <BarRow
          key={p.part_id}
          label={p.part_name ?? `part ${p.part_id}`}
          value={p.worst_stress.value}
          max={max}
          hint={p.worst_stress.case_key ?? undefined}
          tone={p.min_safety_factor != null && p.min_safety_factor < 1 ? 'danger' : 'primary'}
        />
      ))}
      {rows.some((p) => p.min_safety_factor != null && p.min_safety_factor < 1) && (
        <div className="text-danger pt-1">붉은 막대 = 안전율 1 미만 파트입니다.</div>
      )}
    </div>
  )
}

// ── 방향 취약도 ──────────────────────────────────────────────────────────────
function DirectionalView({ reportId }: { reportId: string }) {
  const q = useQuery<ReportDirectional>({
    queryKey: ['report-directional', reportId], queryFn: () => reportDirectional(reportId),
  })
  if (q.isLoading) return <Spinner />
  const dirs = (q.data?.directions ?? []).filter((d) => d.n_cases > 0)
  if (!dirs.length) return <EmptyState title="방향 정보 없음" hint="방향 범주가 있는 리포트에서만 표시됩니다." />
  const rows = [...dirs].sort((a, b) => (b.worst_stress.value ?? -1) - (a.worst_stress.value ?? -1))
  const max = rows[0]?.worst_stress.value ?? 0
  return (
    <div className="space-y-2 text-[11px]">
      <div className="text-muted">방향 범주(면·엣지·코너)별 최악 응력 — 어느 방향이 제일 위험한가.</div>
      {rows.map((d) => (
        <BarRow
          key={d.category}
          label={`${d.category} (${d.n_cases})`}
          value={d.worst_stress.value}
          max={max}
          hint={d.worst_stress.part_name ?? d.worst_stress.case_key ?? undefined}
        />
      ))}
    </div>
  )
}

// ── 방향 산포 (sphere 전용) ──────────────────────────────────────────────────
function ScatterView({ reportId }: { reportId: string }) {
  const [metric, setMetric] = useState<ScatterMetric>('peak_stress')
  const q = useQuery<ReportScatter>({
    queryKey: ['report-scatter', reportId, metric], queryFn: () => reportScatter(reportId, metric),
  })
  if (q.isLoading) return <Spinner />
  const dirs = q.data?.groups ?? []
  if (!dirs.length) return <EmptyState title="산포 데이터 없음" hint={q.data?.note ?? '전각도(sphere) 리포트에서만 계산됩니다.'} />
  const domainMax = Math.max(...dirs.map((d) => d.max ?? d.worst_value ?? 0), 0) || 1
  // 축퇴 상태(방향당 표본 1개)면 CoV 가 전부 0이라 그 정렬은 의미가 없다 — 최악값 순으로 본다.
  const degen = !!q.data?.degenerate
  const rows = [...dirs].sort((a, b) =>
    degen ? (b.worst_value ?? -1) - (a.worst_value ?? -1) : (b.cov ?? -1) - (a.cov ?? -1))
  const sensitive = rows.filter((d) => (d.cov ?? 0) >= 0.15).length
  return (
    <div className="space-y-2 text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-muted">지표</span>
        {(Object.keys(METRIC_LABEL) as ScatterMetric[]).map((m) => (
          <button
            key={m}
            onClick={() => setMetric(m)}
            className={`px-1.5 py-0.5 rounded text-[10px] ${metric === m ? 'bg-primary text-primary-fg' : 'text-muted hover:text-fg'}`}
          >
            {METRIC_LABEL[m]}
          </button>
        ))}
        <span className="ml-auto text-muted">
          {degen ? '최악값 큰 순' : '변동계수(CoV) 큰 순 — 방향을 조금만 틀어도 값이 흔들리는 곳'}
        </span>
      </div>
      {/* 산포가 0인 것을 '안정적'으로 읽으면 정반대 결론이 난다. 그래서 값이 아니라 설계 문제로 알린다. */}
      {degen && (
        <div className="rounded border border-warning/40 bg-warning/10 px-2 py-1.5 text-warning">
          {q.data?.note ?? '방향당 표본이 1개라 산포가 0입니다.'}
          <div className="text-muted mt-0.5">
            지금 보이는 ±1σ 가 0인 것은 안정적이라는 뜻이 아니라, <b className="text-fg">측정이 안 됐다</b>는 뜻입니다.
            민감도를 보려면 방향당 여러 run 을 도는 섭동 DOE 가 필요합니다.
          </div>
        </div>
      )}
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span className="inline-block w-3 h-[7px] rounded-sm bg-primary/40" /> ±1σ
        <span className="inline-block w-[2px] h-3 bg-fg" /> 평균
        <span className="inline-block w-[2px] h-3 bg-danger" /> 최악
        <span className="inline-block w-3 h-[3px] rounded-sm bg-muted/40" /> 최소–최대
        <span className="ml-auto">단위는 {METRIC_LABEL[metric]}</span>
      </div>
      {rows.map((d) => (
        <SpreadRow
          key={d.base}
          label={d.representative ?? d.base}
          mean={d.mean} std={d.std} min={d.min} max={d.max}
          worst={d.worst_value} cov={d.cov} domainMax={domainMax}
        />
      ))}
      {sensitive > 0 && (
        <div className="text-warning pt-1">
          {sensitive}개 방향이 CoV 15% 이상입니다 — 그 방향은 대표값 하나로 판단하면 위험합니다.
        </div>
      )}
    </div>
  )
}

// ── 에너지·접촉 ──────────────────────────────────────────────────────────────
function EnergyView({ reportId, cases }: { reportId: string; cases: ReportCase[] }) {
  const [caseKey, setCaseKey] = useState<string>('')
  const [seriesKey, setSeriesKey] = useState<string>('')
  const q = useQuery<ReportEnergy>({
    queryKey: ['report-energy', reportId, caseKey], queryFn: () => reportEnergy(reportId, caseKey || undefined),
  })
  if (q.isLoading) return <Spinner />
  const eb = q.data?.energy_balance
  const contacts = (q.data?.contacts ?? []).filter((c) => c.peak_fmag != null)
  const cmax = contacts[0]?.peak_fmag ?? 0
  // energy_series 는 {t:[...], kinetic:[...], internal:[...]} 꼴 — t 를 뺀 나머지가 고를 수 있는 계열이다.
  const raw = q.data?.energy_series ?? null
  const seriesKeys = raw ? Object.keys(raw).filter((k) => k !== 't' && Array.isArray(raw[k])) : []
  const activeKey = seriesKey && seriesKeys.includes(seriesKey) ? seriesKey : seriesKeys[0] ?? ''
  const series = raw && raw.t && activeKey
    ? { t: raw.t as number[], v: raw[activeKey] as number[] }
    : null
  return (
    <div className="space-y-3 text-[11px]">
      {cases.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-muted">케이스</span>
          <select
            value={caseKey} onChange={(e) => setCaseKey(e.target.value)}
            className="bg-transparent border border-border rounded px-1 py-0.5 text-[11px] text-fg max-w-[240px]"
          >
            <option value="">기본(전체/대표)</option>
            {cases.map((c) => <option key={c.id} value={c.case_key}>{c.case_key}</option>)}
          </select>
        </div>
      )}
      {eb && (
        <div className="flex flex-wrap gap-2">
          <Stat label="에너지비 최소" value={fmt(eb.energy_ratio_min, 3)}
                tone={eb.energy_ratio_min != null && eb.energy_ratio_min < 0.9 ? 'bad' : 'ok'} />
          <Stat label="에너지비 최대" value={fmt(eb.energy_ratio_max, 3)}
                tone={eb.energy_ratio_max != null && eb.energy_ratio_max > 1.1 ? 'bad' : 'ok'} />
          <Stat label="질량 추가" value={eb.has_mass_added == null ? '—' : eb.has_mass_added ? '있음' : '없음'}
                tone={eb.has_mass_added ? 'bad' : 'ok'} />
          <Stat label="정상 종료" value={eb.normal_termination == null ? '—' : eb.normal_termination ? '예' : '아니오'}
                tone={eb.normal_termination === false ? 'bad' : 'ok'} />
        </div>
      )}
      {eb && (eb.energy_ratio_min != null && eb.energy_ratio_min < 0.9) && (
        <div className="text-danger">에너지비가 0.9 미만입니다 — 해석 신뢰도부터 확인해야 합니다.</div>
      )}
      {series && (
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-muted">에너지 이력</span>
            {seriesKeys.map((k) => (
              <button key={k} onClick={() => setSeriesKey(k)}
                      className={`px-1.5 py-0.5 rounded text-[10px] ${activeKey === k ? 'bg-primary text-primary-fg' : 'text-muted hover:text-fg'}`}>
                {k}
              </button>
            ))}
          </div>
          <Sparkline xs={series.t} ys={series.v} />
        </div>
      )}
      {contacts.length > 0 && (
        <div className="space-y-1">
          <div className="text-muted">접촉 최대 힘 (peak |F|) — 하중이 실제로 지나간 경로 (상위 {Math.min(12, contacts.length)}/{contacts.length})</div>
          {contacts.slice(0, 12).map((c, i) => (
            <BarRow key={`${c.id}-${i}`} label={c.name ?? `contact ${c.id ?? i}`}
                    value={c.peak_fmag} max={cmax} hint={c.side != null ? `side ${c.side}` : undefined} />
          ))}
        </div>
      )}
      {!eb && !contacts.length && !series && (
        <EmptyState title="표시할 에너지 정보 없음" hint={q.data?.note ?? '원본 리포트에 해당 항목이 없습니다.'} />
      )}
    </div>
  )
}

// ── 파트 시계열 ──────────────────────────────────────────────────────────────
function SeriesView({ report, cases }: { report: Report; cases: ReportCase[] }) {
  const parts = report.parts ?? []
  const [caseKey, setCaseKey] = useState<string>(cases[0]?.case_key ?? '')
  const [partId, setPartId] = useState<number>(parts[0]?.part_id ?? 0)
  const enabled = !!caseKey && !!partId
  const q = useQuery<ReportPartSeries>({
    queryKey: ['report-series', report.id, caseKey, partId],
    queryFn: () => reportPartSeries(report.id, caseKey, partId),
    enabled,
  })

  if (!parts.length || !cases.length) {
    return <EmptyState title="시계열 선택 불가" hint="파트·케이스 정보가 있는 리포트에서만 표시됩니다." />
  }
  // sphere/impact 는 [t, v] 쌍 배열, deep 은 stress 맵. 둘 다 (xs, ys) 로 펼친다.
  const pairs = q.data?.stress_ts ?? q.data?.g_ts ?? q.data?.disp_ts ?? null
  let xs: number[] = [], ys: number[] = [], seriesLabel = ''
  if (pairs && Array.isArray(pairs)) {
    xs = pairs.map((p) => Number(p?.[0])).filter((v) => !Number.isNaN(v))
    ys = pairs.map((p) => Number(p?.[1])).filter((v) => !Number.isNaN(v))
    seriesLabel = q.data?.stress_ts ? '응력' : q.data?.g_ts ? '가속도(G)' : '변위'
  } else if (q.data?.stress) {
    const first = Object.values(q.data.stress)[0]
    if (first?.t && first?.max) { xs = first.t; ys = first.max; seriesLabel = '응력(최대)' }
  }

  return (
    <div className="space-y-2 text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-muted">케이스</span>
        <select value={caseKey} onChange={(e) => setCaseKey(e.target.value)}
                className="bg-transparent border border-border rounded px-1 py-0.5 text-[11px] text-fg max-w-[220px]">
          {cases.map((c) => <option key={c.id} value={c.case_key}>{c.case_key}</option>)}
        </select>
        <span className="text-muted">파트</span>
        <select value={partId} onChange={(e) => setPartId(Number(e.target.value))}
                className="bg-transparent border border-border rounded px-1 py-0.5 text-[11px] text-fg max-w-[220px]">
          {parts.map((p) => <option key={p.part_id} value={p.part_id}>{p.name || `part ${p.part_id}`}</option>)}
        </select>
        {seriesLabel && <Badge tone="running">{seriesLabel}</Badge>}
      </div>
      {q.isLoading ? <Spinner />
        : q.data?.note ? <EmptyState title="시계열 없음" hint={q.data.note} />
        : <Sparkline xs={xs} ys={ys} />}
    </div>
  )
}
