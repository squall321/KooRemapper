// 낙하/충격 리포트 결과 분석 뷰 — 방향취약도·산포·에너지·파트위험도·시계열.
// 지금까지 MCP 도구로만 열려 있던 분석을 웹에서도 같은 깊이로 본다.
//
// 차트는 인라인 SVG 다. 차트 라이브러리를 넣지 않는 이유는 둘이다 —
//   ① 이 화면이 쓰는 형태가 가로 막대·오차막대·꺾은선 셋뿐이라 라이브러리 값어치가 없고,
//   ② 번들이 커지면 포탈 서브패스 빌드까지 두 벌로 늘어난다(현재 399KB).
// 색은 전부 테마 토큰(currentColor/text-*)으로 잡아 라이트·다크가 자동으로 따라온다.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, Compass, Flame, Image as ImageIcon, Layers, LineChart, Network, Sigma, Table2, Zap } from 'lucide-react'
import {
  mediaBlobUrl, reportAnalytics, reportAngleStats, reportBehaviorClusters, reportBlocks,
  reportDirectional,
  reportEnergy, reportHotspots, reportMedia, reportPartEnergy, reportPartRisk,
  reportPartSeries, reportScatter,
} from '@/shared/api/endpoints'
import type {
  AngleGroupStats, PartEnergySeries, Report, ReportAnalytics, ReportBehaviorClusters, ReportCase,
  ReportDirectional, ReportEnergy, ReportHotspots, ReportMedia, ReportMediaItem, ReportPartRisk,
  ReportPartSeries, ReportScatter, ScatterMetric,
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
// 각도군 통계는 리포트에 실재하는 어떤 물리량이든 받으므로(available_metrics) 넓은 라벨맵 + 폴백.
const M_LABEL: Record<string, string> = {
  peak_stress: '응력', peak_strain: '변형률', peak_plastic_strain: '소성변형률',
  peak_g: 'G', peak_disp: '변위', peak_vel: '속도',
  peak_ie: '내부E', peak_ke: '운동E', final_ie: '최종IE', final_ke: '최종KE',
  peak_principal: '주응력', min_principal: '최소주응력', peak_vm_strain: 'vM변형률', safety_factor: '안전계수',
}
const mlabel = (m: string) => M_LABEL[m] ?? m

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
type TabKey = 'parts' | 'directional' | 'scatter' | 'anglestats' | 'energy' | 'partenergy'
  | 'series' | 'hotspots' | 'clusters' | 'analytics' | 'media'
const TABS: Array<{ key: TabKey; label: string; icon: typeof Layers; kinds?: string[] }> = [
  { key: 'parts', label: '파트 위험도', icon: Layers },
  { key: 'directional', label: '방향 취약도', icon: Compass },
  { key: 'scatter', label: '방향 산포', icon: Activity, kinds: ['sphere'] },
  { key: 'anglestats', label: '각도군 통계', icon: Sigma, kinds: ['sphere', 'impact'] },
  { key: 'energy', label: '에너지·접촉', icon: AlertTriangle },
  { key: 'partenergy', label: '파트 에너지', icon: Zap, kinds: ['deep'] },
  { key: 'series', label: '파트 시계열', icon: LineChart },
  // ★아래 넷은 리포트에 **있었는데 플랫폼이 버리고 있던** 것들이다(실측: deep 21키 중 11,
  //   impact 27키 중 18). 그중에 핫스팟 군집 102레코드와 거동 군집이 있었다.
  { key: 'hotspots', label: '핫스팟 군집', icon: Flame, kinds: ['deep'] },
  { key: 'clusters', label: '거동 군집', icon: Network, kinds: ['impact'] },
  { key: 'media', label: '결과 이미지', icon: ImageIcon },
  { key: 'analytics', label: '분석 블록', icon: Table2 },
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
        {tab === 'anglestats' && <AngleStatsView reportId={report.id} />}
        {tab === 'energy' && <EnergyView reportId={report.id} cases={cases} />}
        {tab === 'partenergy' && <PartEnergyView reportId={report.id} />}
        {tab === 'series' && <SeriesView report={report} cases={cases} />}
        {tab === 'hotspots' && <HotspotsView reportId={report.id} />}
        {tab === 'clusters' && <ClustersView reportId={report.id} />}
        {tab === 'media' && <MediaView report={report} />}
        {tab === 'analytics' && <AnalyticsView reportId={report.id} />}
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

// ── 각도군 통계 ──────────────────────────────────────────────────────────────
// 방향군(sphere=base·범주, impact=면)별 분포(mean/±σ/최소–최대/최악) + 위험 부품.
// 물리량 목록은 리포트에 실재하는 것(available_metrics)으로 동적 구성 — 소성·에너지도 여기서.
function AngleStatsView({ reportId }: { reportId: string }) {
  const [metric, setMetric] = useState('peak_stress')
  const q = useQuery<AngleGroupStats>({
    queryKey: ['report-anglestats', reportId, metric], queryFn: () => reportAngleStats(reportId, { metric }),
  })
  const avail = q.data?.available_metrics ?? []
  // 기본 metric(peak_stress)이 이 리포트에 없으면 있는 첫 물리량으로 자동 전환(빈 화면 오독 방지).
  useEffect(() => {
    if (avail.length && !avail.includes(metric)) setMetric(avail[0])
  }, [avail.join(',')])  // eslint-disable-line react-hooks/exhaustive-deps
  if (q.isLoading) return <Spinner />
  const d = q.data
  const groups = d?.groups ?? []
  const domainMax = Math.max(...groups.map((g) => g.stats.max ?? 0), 0) || 1
  return (
    <div className="space-y-2 text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-muted">물리량</span>
        {avail.map((m) => (
          <button key={m} onClick={() => setMetric(m)}
            className={`px-1.5 py-0.5 rounded text-[10px] ${metric === m ? 'bg-primary text-primary-fg' : 'text-muted hover:text-fg'}`}>
            {mlabel(m)}
          </button>
        ))}
      </div>
      {!groups.length ? (
        <EmptyState title="데이터 없음" hint={d?.note ?? '이 물리량이 리포트에 없습니다.'} />
      ) : (
        <>
          <div className="flex items-center gap-2 text-[10px] text-muted">
            <span>방향군 {groups.length}개 · 위험한 순</span>
            <span className="inline-block w-3 h-[7px] rounded-sm bg-primary/40" /> ±1σ
            <span className="inline-block w-[2px] h-3 bg-fg" /> 평균
            <span className="inline-block w-[2px] h-3 bg-danger" /> 최악
            <span className="ml-auto">단위 {mlabel(metric)}</span>
          </div>
          {groups.map((g) => (
            <div key={g.group_key} className="space-y-0.5">
              <SpreadRow
                label={`${g.representative ?? g.group_key} · ${g.category} · n=${g.stats.n}`}
                mean={g.stats.mean} std={g.stats.std} min={g.stats.min} max={g.stats.max}
                worst={g.worst.value} cov={g.stats.cov} domainMax={domainMax}
              />
              {g.parts?.top_risk?.length ? (
                <div className="pl-2 text-[10px] text-muted">
                  위험 부품 {g.parts.top_risk.slice(0, 3).map((p) => `${p.part_name ?? p.part_id}(${smart(p.worst)})`).join(' · ')}
                </div>
              ) : null}
            </div>
          ))}
        </>
      )}
    </div>
  )
}

// ── 파트 에너지 ──────────────────────────────────────────────────────────────
// deep matsum 의 파트별 내부(IE)·운동(KE) 에너지 시간이력. run 이 matsum 을 덤프해야 담긴다.
function PartEnergyView({ reportId }: { reportId: string }) {
  const q = useQuery<PartEnergySeries>({
    queryKey: ['report-partenergy', reportId], queryFn: () => reportPartEnergy(reportId),
  })
  const [pid, setPid] = useState<number | null>(null)
  if (q.isLoading) return <Spinner />
  const d = q.data
  const parts = d?.parts ?? []
  if (!parts.length) {
    return <EmptyState title="파트 에너지 없음"
      hint={d?.note ?? 'LS-DYNA run 이 matsum 을 덤프해야 파트별 에너지 시계열이 담깁니다.'} />
  }
  const sel = parts.find((p) => p.part_id === pid) ?? parts[0]
  const t = d?.t ?? []
  return (
    <div className="space-y-2 text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-muted">부품</span>
        <select value={sel.part_id} onChange={(e) => setPid(Number(e.target.value))}
                className="bg-transparent border border-border rounded px-1 py-0.5 text-[11px] text-fg max-w-[240px]">
          {parts.map((p) => <option key={p.part_id} value={p.part_id}>{p.part_name || `part ${p.part_id}`}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <div className="text-muted mb-1">내부에너지 IE · peak {smart(sel.peak_internal_energy)}</div>
          {sel.internal_energy && t.length ? <Sparkline xs={t} ys={sel.internal_energy} />
            : <span className="text-muted">—</span>}
        </div>
        <div>
          <div className="text-muted mb-1">운동에너지 KE · peak {smart(sel.peak_kinetic_energy)}</div>
          {sel.kinetic_energy && t.length ? <Sparkline xs={t} ys={sel.kinetic_energy} />
            : <span className="text-muted">—</span>}
        </div>
      </div>
    </div>
  )
}

// ── 핫스팟 군집 (deep) ───────────────────────────────────────────────────────
// 생성기(`unified_analyzer --hotspot-clusters`)가 만든 **공간 군집**이다. 리포트에 있었는데
// 플랫폼이 읽지 않아 어디에도 도달하지 않았다(실측 102 레코드 · 105 군집 · 34파트 × 3기준).
function HotspotsView({ reportId }: { reportId: string }) {
  const [criterion, setCriterion] = useState<string>('')
  const q = useQuery<ReportHotspots>({
    queryKey: ['report-hotspots', reportId, criterion],
    queryFn: () => reportHotspots(reportId, { criterion: criterion || undefined, top: 50 }),
  })
  if (q.isLoading) return <Spinner />
  const d = q.data
  if (!d?.available) {
    return (
      <EmptyState
        title="핫스팟 군집 없음"
        hint={d?.note ?? '이 리포트에는 핫스팟 군집이 없습니다.'}
      />
    )
  }
  const rows = d.clusters ?? []
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-muted">
          레코드 {d.n_records} · 군집 {d.n_clusters} · 파트 {d.parts?.length ?? 0}개
        </span>
        <select
          value={criterion}
          onChange={(e) => setCriterion(e.target.value)}
          className="bg-bg border border-border rounded px-1 py-0.5"
        >
          <option value="">판정기준 전체</option>
          {(d.criteria ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      {/* ★크기 비교는 절대값이다 — min 기준의 값은 음수다. 그 사실을 화면에도 적는다. */}
      {d.order_note && <div className="text-[10px] text-muted">{d.order_note}</div>}
      {/* ★값이 고른 레코드의 군집은 '가장 뜨거운 곳' 이 아니다. */}
      {d.uniform_note && (
        <div className="text-[11px]" style={{ color: '#a33' }}>⚠ {d.uniform_note}</div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead className="text-muted">
            <tr className="text-left">
              <th className="py-1 pr-2">파트</th>
              <th className="pr-2">기준</th>
              <th className="pr-2">순위</th>
              <th className="pr-2 text-right">|응력| 최대</th>
              <th className="pr-2 text-right">요소</th>
              <th className="pr-2 text-right">부피</th>
              <th className="pr-2 text-right">반경</th>
              <th className="pr-2">중심 (x, y, z)</th>
              <th className="pr-2 text-right">피크 시각</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => (
              <tr key={i} className="border-t border-border/60">
                <td className="py-1 pr-2">
                  {c.part_id}
                  {c.uniform && <span style={{ color: '#a33' }} title="값이 고르다 — 핫스팟이 아니다"> ⚠</span>}
                </td>
                <td className="pr-2 mono">{c.criterion}</td>
                <td className="pr-2">{c.rank ?? '—'}</td>
                <td className="pr-2 text-right mono">{smart(c.stress_max == null ? null : Math.abs(c.stress_max))}</td>
                <td className="pr-2 text-right">{c.element_count ?? '—'}</td>
                <td className="pr-2 text-right mono">{smart(c.volume)}</td>
                <td className="pr-2 text-right mono">{fmt(c.radius_enclosing, 2)}</td>
                <td className="pr-2 mono">
                  {c.center ? c.center.map((v) => fmt(v, 1)).join(', ') : '—'}
                </td>
                <td className="pr-2 text-right mono">{c.peak_time == null ? '—' : c.peak_time.toExponential(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.truncated && (
        <div className="text-[10px] text-muted">
          전체 {d.truncated.total} 중 {d.truncated.returned} 만 표시했습니다.
        </div>
      )}
    </div>
  )
}

// ── 거동 군집 (impact) ───────────────────────────────────────────────────────
function ClustersView({ reportId }: { reportId: string }) {
  const q = useQuery<ReportBehaviorClusters>({
    queryKey: ['report-clusters', reportId], queryFn: () => reportBehaviorClusters(reportId),
  })
  if (q.isLoading) return <Spinner />
  const d = q.data
  if (!d?.available) return <EmptyState title="거동 군집 없음" hint={d?.note ?? ''} />
  return (
    <div className="space-y-2 text-[11px]">
      {/* ★합성 군집을 실측으로 읽으면 결론이 거짓이 된다 — 가장 먼저 크게 적는다. */}
      {d.is_mock && (
        <div className="rounded border px-2 py-1" style={{ color: '#a33', borderColor: '#a33' }}>
          ★ {d.mock_note ?? '이 군집은 합성(mock)입니다 — 결론의 근거로 쓰지 마세요.'}
        </div>
      )}
      {/* ★선언 수와 쓰인 수가 다르면 "N 가지 거동" 으로 읽어선 안 된다. */}
      {d.degenerate && (
        <div className="rounded border px-2 py-1" style={{ color: '#a33', borderColor: '#a33' }}>
          ★ {d.degenerate_note}
        </div>
      )}
      <div className="text-muted">
        선언 {d.n_clusters ?? '—'} · 실제 사용 {d.n_archetypes_used ?? '—'} · 라벨된 위치{' '}
        {d.n_positions_labeled ?? 0}
      </div>
      {!!d.features_used?.length && (
        <div className="flex flex-wrap gap-1">
          <span className="text-muted">군집에 쓴 특징:</span>
          {d.features_used.map((f) => (
            <span key={f} className="rounded bg-bg px-1.5 py-0.5 mono">{f}</span>
          ))}
        </div>
      )}
      <div className="space-y-1 pt-1">
        {(d.groups ?? []).map((g) => (
          <div key={g.archetype} className="border border-border rounded p-2">
            <div className="flex items-center justify-between">
              <span className="font-medium">{g.archetype}</span>
              <Badge>{g.n_positions} 위치</Badge>
            </div>
            <div className="text-muted mono pt-1 break-all">
              {g.positions.slice(0, 24).join(' · ')}
              {g.positions.length > 24 && ` … (+${g.positions.length - 24})`}
            </div>
          </div>
        ))}
      </div>
      {!!d.archetypes?.length && d.archetypes.length !== (d.groups ?? []).length && (
        <div className="text-[10px] text-muted">
          선언된 아키타입: {d.archetypes.join(' · ')} — 위에 안 보이는 것은 **쓰이지 않았다**는 뜻입니다.
        </div>
      )}
    </div>
  )
}

// ── 결과 이미지 갤러리 ───────────────────────────────────────────────────────
// ★결과 이미지는 리포트 HTML 안에 **없다** — 옆에 딸린 파일이라, 번들(.zip/.tar.gz)로 올려야
//   함께 들어온다. 비어 있을 때 그 사실을 말하지 않으면 "그림이 없는 리포트" 로 오해한다.
function MediaView({ report }: { report: Report }) {
  const [caseKey, setCaseKey] = useState<string>('')
  const q = useQuery<ReportMedia>({
    queryKey: ['report-media', report.id, caseKey],
    queryFn: () => reportMedia(report.id, { case_key: caseKey || undefined }),
  })
  if (q.isLoading) return <Spinner />
  const d = q.data
  if (!d || d.n_total === 0) {
    return <EmptyState title="결과 이미지 없음" hint={d?.note ?? ''} />
  }
  const images = d.media.filter((m) => m.kind === 'image')
  const videos = d.media.filter((m) => m.kind === 'video')
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-muted">
          이미지 {d.n_images} · 영상 {d.n_videos} · 그림 있는 케이스 {d.cases_with_media.length}
        </span>
        <select
          value={caseKey}
          onChange={(e) => setCaseKey(e.target.value)}
          className="bg-bg border border-border rounded px-1 py-0.5"
        >
          <option value="">케이스 전체</option>
          {d.cases_with_media.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
        {images.map((m) => (
          <MediaTile key={m.file_id} sessionId={report.session_id} item={m} />
        ))}
      </div>
      {!!videos.length && (
        <div className="text-[10px] text-muted pt-1">
          영상 {videos.length}개도 함께 들어왔습니다(목록만) — 다운로드로 보세요:{' '}
          <span className="mono">{videos.slice(0, 3).map((v) => v.path.split('/').pop()).join(', ')}</span>
          {videos.length > 3 && ' …'}
        </div>
      )}
    </div>
  )
}

/** 한 장 — blob URL 은 쓰고 나서 **반드시 해제**한다(안 하면 탭을 오래 열어 둘수록 샌다). */
function MediaTile({ sessionId, item }: { sessionId: string; item: ReportMediaItem }) {
  const [url, setUrl] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let dead = false
    let made: string | null = null
    mediaBlobUrl(sessionId, item.file_id, item.path)
      .then((u) => {
        made = u
        if (dead) URL.revokeObjectURL(u)
        else setUrl(u)
      })
      .catch((e) => !dead && setErr(String(e?.message ?? e)))
    return () => {
      dead = true
      if (made) URL.revokeObjectURL(made)
    }
  }, [sessionId, item.file_id, item.path])
  const name = item.path.split('/').pop()
  return (
    <figure className="border border-border rounded overflow-hidden">
      {/* ⚠ `<img>` 로만 띄운다 — `svgBlobUrl` 과 같은 규율(스크립트가 실행되지 않는다). */}
      {url ? (
        <img src={url} alt={name} className="w-full block" />
      ) : (
        <div className="h-32 flex items-center justify-center text-[10px] text-muted">
          {err ? `불러오기 실패: ${err}` : '불러오는 중…'}
        </div>
      )}
      <figcaption className="px-2 py-1 text-[10px] text-muted">
        <div className="flex items-center justify-between gap-1">
          <span className="mono truncate" title={item.path}>{name}</span>
          {item.role && <Badge>{item.role}</Badge>}
        </div>
        <div className="truncate">
          {item.case_key ?? '케이스 미지정'}
          {item.set_name ? ` · ${item.set_name}` : ''}
          {!item.declared && ' · 리포트가 케이스를 선언하지 않음'}
        </div>
      </figcaption>
    </figure>
  )
}

// ── 분석 블록 요약 ───────────────────────────────────────────────────────────
// 요약은 **생성기가 계산한 값 그대로**다(여기서 다시 계산하면 리포트 화면 숫자와 갈린다).
function AnalyticsView({ reportId }: { reportId: string }) {
  const q = useQuery<ReportAnalytics>({
    queryKey: ['report-analytics', reportId], queryFn: () => reportAnalytics(reportId),
  })
  const bq = useQuery({ queryKey: ['report-blocks', reportId], queryFn: () => reportBlocks(reportId) })
  if (q.isLoading) return <Spinner />
  const blocks = (q.data?.blocks ?? []).filter((b) => b.available)
  if (!blocks.length) return <EmptyState title="분석 블록 없음" hint="이 리포트에는 큰 분석 블록이 없습니다." />
  return (
    <div className="space-y-2 text-[11px]">
      {bq.data && (
        <div className="text-muted">
          임베드 블록 {bq.data.n_blocks}개 · 아직 해석하지 않는 것 {bq.data.n_unread}개
          <span className="text-[10px]"> (아래 요약 + API `/blocks/{'{name}'}` 로 원본까지 볼 수 있습니다)</span>
        </div>
      )}
      {blocks.map((b) => (
        <details key={b.name} className="border border-border rounded">
          <summary className="px-2 py-1 cursor-pointer">
            <span className="font-medium mono">{b.name}</span>
            <span className="text-muted"> · 하위 {b.n_subs ?? 0}</span>
          </summary>
          <div className="px-2 pb-2 space-y-1">
            {(b.subs ?? []).map((sub) => (
              <div key={sub.name} className="border-t border-border/60 pt-1">
                <div className="flex items-center gap-2">
                  <span className="mono">{sub.name}</span>
                  {sub.not_computed && (
                    <span style={{ color: '#a33' }} title={sub.not_computed_note}>
                      ★미계산 ({sub.not_computed.join(', ')})
                    </span>
                  )}
                </div>
                {/* ★'미계산' 은 "값이 0" 이 아니다 — 그 문구를 그대로 보인다. */}
                {sub.not_computed_note && (
                  <div className="text-[10px]" style={{ color: '#a33' }}>{sub.not_computed_note}</div>
                )}
                {sub.summary != null && (
                  <pre className="text-[10px] mono whitespace-pre-wrap break-all text-muted">
                    {JSON.stringify(sub.summary, null, 1).slice(0, 1200)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </details>
      ))}
      {q.data?.raw_access_note && (
        <div className="text-[10px] text-muted">{q.data.raw_access_note}</div>
      )}
    </div>
  )
}
