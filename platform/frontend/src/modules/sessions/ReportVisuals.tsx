// 부품 리스크의 공간 컨텍스트 시각화 — 낙하 방향(구면)·충격 위치(디바이스)에 값 마커.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportGeometry, reportQuery } from '@/shared/api/endpoints'
import type { Report, ReportFact, ReportGeometry } from '@/shared/api/types'
import { Select, Spinner } from '@/shared/ui/ui'

const METRICS = [
  { v: 'peak_stress', label: '응력(MPa)' },
  { v: 'peak_g', label: 'G' },
  { v: 'peak_disp', label: '변위(mm)' },
  { v: 'peak_strain', label: '변형률' },
]

/** 값 → 색(색각 안전 순차 램프, 파랑→회→노랑. 적록 회피·명도 단조). */
function heat(t: number): string {
  const c = Math.max(0, Math.min(1, t))
  const lo = [59, 76, 192], mid = [200, 200, 200], hi = [250, 210, 40]
  const [a, b, f] = c < 0.5 ? [lo, mid, c / 0.5] : [mid, hi, (c - 0.5) / 0.5]
  const ch = (i: number) => Math.round(a[i] + (b[i] - a[i]) * f)
  return `rgb(${ch(0)},${ch(1)},${ch(2)})`
}

/** 물리량 크기에 맞춘 값 포맷 — 응력(수백)부터 변형률(수천분의 1)까지 '0' 뭉개짐 방지. */
function fmtVal(v: number): string {
  const a = Math.abs(v)
  if (a === 0) return '0'
  if (a >= 100) return v.toFixed(0)
  if (a >= 1) return v.toFixed(2)
  if (a >= 1e-3) return v.toFixed(4)
  return v.toExponential(1)
}

/** 색→값 매핑 범례(연속 컬러바 + 최소/최대 실값). 없으면 색이 무슨 값인지 못 읽는다. */
function Legend({ vmin, vmax, unit }: { vmin: number; vmax: number; unit: string }) {
  const stops = Array.from({ length: 12 }, (_, i) => i / 11)
  return (
    <svg viewBox="0 0 200 26" className="w-[200px]">
      {stops.map((t, i) => (
        <rect key={i} x={10 + t * 168} y={2} width={168 / 11 + 0.6} height={9} fill={heat(t)} />
      ))}
      <text x={10} y={22} fontSize="8" fill="#666" textAnchor="start">{fmtVal(vmin)}</text>
      <text x={94} y={22} fontSize="8" fill="#999" textAnchor="middle">{unit}</text>
      <text x={178} y={22} fontSize="8" fill="#666" textAnchor="end">{fmtVal(vmax)}</text>
    </svg>
  )
}

export function ReportVisuals({ report }: { report: Report }) {
  const partList = report.parts ?? []
  const [partId, setPartId] = useState<number | ''>(partList[0]?.part_id ?? '')
  const [metric, setMetric] = useState('peak_stress')

  const facts = useQuery({
    queryKey: ['report-facts', report.id, partId, metric],
    queryFn: () => reportQuery(report.id, { part_id: Number(partId), metric, limit: 3000 }),
    enabled: partId !== '',
  })
  const geom = useQuery<ReportGeometry>({
    queryKey: ['report-geom', report.id],
    queryFn: () => reportGeometry(report.id),
    enabled: report.kind === 'impact',
  })

  if (report.kind === 'deep') {
    return <div className="text-muted text-[11px]">단건 심층 리포트는 방향/위치 마커가 없습니다 — 원본 리포트 렌더를 보세요.</div>
  }

  const fs = facts.data?.facts ?? []
  const vals = fs.map((f) => f.value)
  const vmin = vals.length ? Math.min(...vals) : 0
  const vmax = vals.length ? Math.max(...vals) : 1
  const norm = (v: number) => (vmax > vmin ? (v - vmin) / (vmax - vmin) : 0.5)
  const worst = fs.reduce<ReportFact | null>((a, f) => (!a || f.value > a.value ? f : a), null)
  const unit = METRICS.find((m) => m.v === metric)?.label ?? metric

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap text-[11px]">
        <span className="text-muted">부품 위치·방향 시각화</span>
        <Select value={String(partId)} onChange={(e) => setPartId(e.target.value === '' ? '' : Number(e.target.value))}
                className="h-7 text-xs w-40">
          {partList.map((p) => <option key={p.part_id} value={p.part_id}>{p.name ?? `Part ${p.part_id}`}</option>)}
        </Select>
        <Select value={metric} onChange={(e) => setMetric(e.target.value)} className="h-7 text-xs w-28">
          {METRICS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
        </Select>
        {worst && <span className="text-fg">최악 <b>{fmtVal(worst.value)}</b> @ {factLabel(worst)}</span>}
      </div>

      {facts.isLoading || (report.kind === 'impact' && geom.isLoading) ? <Spinner /> : !fs.length ? (
        <div className="text-muted text-[11px]">이 부품·물리량의 값이 없습니다.</div>
      ) : (
        <div className="space-y-1">
          {report.kind === 'sphere' ? (
            <SphereMarker facts={fs} norm={norm} worst={worst} unit={unit} fmt={fmtVal} />
          ) : (
            <DeviceMarker facts={fs} norm={norm} worst={worst} unit={unit} fmt={fmtVal} geom={geom.data} partId={Number(partId)} />
          )}
          <Legend vmin={vmin} vmax={vmax} unit={unit} />
          {facts.data?.truncated && (
            <div className="text-[10px] text-amber-600">
              값이 많아 {fs.length}건만 표시(색 스케일이 일부 편향될 수 있음). 부품/물리량으로 좁혀 보세요.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function factLabel(f: ReportFact): string {
  const a = (f.identity as { angle?: { name?: string } })?.angle
  if (a?.name) return a.name
  const id = f.identity as { face?: string; pos_x?: number; pos_y?: number } | null
  if (id?.face) return `${id.face} (${id.pos_x ?? '?'},${id.pos_y ?? '?'})`
  return f.case_key
}

/** 전각도 낙하 — 등장방형(경도×위도)에 각 방향을 값으로 색칠, 최악 별표.
 *  좌표는 백엔드가 swap 규약을 반영해 저장한 lon/lat 을 그대로 쓴다(구버전은 클램프 폴백). */
function SphereMarker({ facts, norm, worst, unit, fmt }: {
  facts: ReportFact[]; norm: (v: number) => number; worst: ReportFact | null; unit: string; fmt: (v: number) => string
}) {
  const W = 320, H = 170, pad = 18
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
  const lonlat = (f: ReportFact) => {
    const a = (f.identity as { angle?: { lon?: number; lat?: number; roll?: number; pitch?: number } })?.angle ?? {}
    const lon = a.lon ?? a.pitch ?? 0            // 폴백: 구버전 리포트(재인제스트 전)
    const lat = clamp(a.lat ?? a.roll ?? 0, -90, 90)
    return { lon: clamp(lon, -180, 180), lat }
  }
  const sx = (lon: number) => pad + ((lon + 180) / 360) * (W - 2 * pad)
  const sy = (lat: number) => pad + ((90 - lat) / 180) * (H - 2 * pad)
  const angName = (f: ReportFact) => (f.identity as { angle?: { name?: string } })?.angle?.name ?? f.case_key
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[360px] border border-border rounded bg-white">
      {/* graticule + 각도 눈금 */}
      {[-90, 0, 90].map((lat) => <line key={`la${lat}`} x1={pad} x2={W - pad} y1={sy(lat)} y2={sy(lat)} stroke="#eee" />)}
      {[-180, -90, 0, 90, 180].map((lon) => <line key={`lo${lon}`} y1={pad} y2={H - pad} x1={sx(lon)} x2={sx(lon)} stroke="#eee" />)}
      {[-90, 0, 90].map((lat) => <text key={`lat${lat}`} x={pad - 2} y={sy(lat) + 3} textAnchor="end" fontSize="6" fill="#bbb">{lat}°</text>)}
      {[-180, 0, 180].map((lon) => <text key={`lon${lon}`} x={sx(lon)} y={pad - 3} textAnchor="middle" fontSize="6" fill="#bbb">{lon}°</text>)}
      <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="8" fill="#999">경도(방위) →</text>
      <text x={7} y={H / 2} fontSize="8" fill="#999" transform={`rotate(-90 7 ${H / 2})`}>위도(고각) →</text>
      {facts.map((f, i) => {
        const { lon, lat } = lonlat(f)
        return (
          <circle key={i} cx={sx(lon)} cy={sy(lat)} r={3.2} fill={heat(norm(f.value))} opacity={0.9}>
            <title>{`${angName(f)} · ${fmt(f.value)} ${unit}`}</title>
          </circle>
        )
      })}
      {worst && (() => { const { lon, lat } = lonlat(worst); return (
        <g>
          <circle cx={sx(lon)} cy={sy(lat)} r={6} fill="none" stroke="#111" strokeWidth={1.5} />
          <text x={clamp(sx(lon) + 8, 0, W - 40)} y={clamp(sy(lat) - 6, 10, H)} fontSize="8" fill="#111">{fmt(worst.value)} {unit}</text>
        </g>
      )})()}
    </svg>
  )
}

/** 전위치 부분충격 — 디바이스 외곽선 + 선택 부품 footprint + 충격 위치 값 마커.
 *  종횡비를 보존(늘어남 방지)하고, bbox 결측 시 외곽선/footprint 로 범위를 유추한다. */
function DeviceMarker({ facts, norm, worst, unit, fmt, geom, partId }: {
  facts: ReportFact[]; norm: (v: number) => number; worst: ReportFact | null; unit: string
  fmt: (v: number) => string; geom: ReportGeometry | undefined; partId: number
}) {
  const W = 300, H = 240, pad = 16
  const partFp = geom?.parts.find((p) => p.part_id === partId)?.footprint ?? null
  const pos = (f: ReportFact) => {
    const id = f.identity as { pos_x?: number; pos_y?: number } | null
    return { x: id?.pos_x ?? 0, y: id?.pos_y ?? 0 }
  }
  // 범위: bbox 우선, 없으면 외곽선+footprint+위치에서 유추.
  const bb = geom?.device_bbox
  let xr: [number, number], yr: [number, number]
  if (bb) { xr = [bb.xmin, bb.xmax]; yr = [bb.ymin, bb.ymax] } else {
    const xs: number[] = [], ys: number[] = []
    for (const pt of geom?.device_outline ?? []) { xs.push(pt[0]); ys.push(pt[1]) }
    for (const pt of partFp ?? []) { xs.push(pt[0]); ys.push(pt[1]) }
    for (const f of facts) { const p = pos(f); xs.push(p.x); ys.push(p.y) }
    xr = xs.length ? [Math.min(...xs), Math.max(...xs)] : [-50, 50]
    yr = ys.length ? [Math.min(...ys), Math.max(...ys)] : [-40, 40]
  }
  // 종횡비 보존: x·y 공통 스케일 + 중앙 정렬.
  const spanX = Math.max(1e-6, xr[1] - xr[0]), spanY = Math.max(1e-6, yr[1] - yr[0])
  const s = Math.min((W - 2 * pad) / spanX, (H - 2 * pad) / spanY)
  const ox = (W - spanX * s) / 2, oy = (H - spanY * s) / 2
  const sx = (x: number) => ox + (x - xr[0]) * s
  const sy = (y: number) => H - oy - (y - yr[0]) * s
  const poly = (pts: number[][]) => pts.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' ')
  const factLbl = (f: ReportFact) => (f.identity as { face?: string } | null)?.face
    ? `${(f.identity as { face?: string }).face} · ${fmt(f.value)} ${unit}` : `${fmt(f.value)} ${unit}`
  // 충격 위치가 사실상 한 점에 뭉쳤는지(면-낙하 DOE 등) 감지 → 오독 방지 안내.
  const coincident = facts.length > 1 && facts.every((f) => {
    const p = pos(f), q = pos(facts[0]); return Math.abs(p.x - q.x) < 1e-6 && Math.abs(p.y - q.y) < 1e-6
  })
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[320px] border border-border rounded bg-white">
        {geom?.device_outline && <polygon points={poly(geom.device_outline)} fill="none" stroke="#bbb" strokeWidth={1} />}
        {partFp && <polygon points={poly(partFp)} fill="#4ecca355" stroke="#2a9d78" strokeWidth={1} />}
        {facts.map((f, i) => { const p = pos(f); return (
          <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={4} fill={heat(norm(f.value))} opacity={0.85}>
            <title>{factLbl(f)}</title>
          </circle>
        )})}
        {worst && (() => { const p = pos(worst); return (
          <g>
            <circle cx={sx(p.x)} cy={sy(p.y)} r={7} fill="none" stroke="#111" strokeWidth={1.5} />
            <text x={Math.min(sx(p.x) + 9, W - 40)} y={Math.max(sy(p.y) - 7, 10)} fontSize="8" fill="#111">{fmt(worst.value)} {unit}</text>
          </g>
        )})()}
        <text x={W / 2} y={H - 3} textAnchor="middle" fontSize="8" fill="#999">디바이스 XY · 초록=선택 부품 footprint</text>
      </svg>
      {coincident && (
        <div className="text-[10px] text-amber-600">
          충격 위치가 모두 같은 좌표에 뭉쳐 있습니다(면 단위 낙하로 보임) — 개별 위치 구분은 리포트 조건에 따라 달라집니다.
        </div>
      )}
    </>
  )
}
