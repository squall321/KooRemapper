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

/** 값 → 색(순차 팔레트, 낮음 파랑 → 높음 빨강). */
function heat(t: number): string {
  const c = Math.max(0, Math.min(1, t))
  const r = Math.round(40 + c * 200), g = Math.round(90 + (1 - Math.abs(c - 0.5) * 2) * 90), b = Math.round(230 - c * 200)
  return `rgb(${r},${g},${b})`
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
        {worst && <span className="text-fg">최악 <b>{worst.value.toFixed(1)}</b> @ {factLabel(worst)}</span>}
      </div>

      {facts.isLoading || (report.kind === 'impact' && geom.isLoading) ? <Spinner /> : !fs.length ? (
        <div className="text-muted text-[11px]">이 부품·물리량의 값이 없습니다.</div>
      ) : report.kind === 'sphere' ? (
        <SphereMarker facts={fs} norm={norm} worst={worst} unit={unit} />
      ) : (
        <DeviceMarker facts={fs} norm={norm} worst={worst} unit={unit} geom={geom.data} partId={Number(partId)} />
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

/** 전각도 낙하 — 등장방형(pitch×roll)에 각 방향을 값으로 색칠, 최악 별표. */
function SphereMarker({ facts, norm, worst, unit }: {
  facts: ReportFact[]; norm: (v: number) => number; worst: ReportFact | null; unit: string
}) {
  const W = 320, H = 170, pad = 18
  const ang = (f: ReportFact) => (f.identity as { angle?: { roll?: number; pitch?: number } })?.angle ?? {}
  const sx = (pitch: number) => pad + ((pitch + 180) / 360) * (W - 2 * pad)
  const sy = (roll: number) => pad + ((90 - roll) / 180) * (H - 2 * pad)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[360px] border border-border rounded bg-white">
      {/* graticule */}
      {[-90, 0, 90].map((r) => <line key={`r${r}`} x1={pad} x2={W - pad} y1={sy(r)} y2={sy(r)} stroke="#eee" />)}
      {[-180, -90, 0, 90, 180].map((p) => <line key={`p${p}`} y1={pad} y2={H - pad} x1={sx(p)} x2={sx(p)} stroke="#eee" />)}
      <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="8" fill="#999">pitch →</text>
      <text x={6} y={H / 2} fontSize="8" fill="#999" transform={`rotate(-90 6 ${H / 2})`}>roll →</text>
      {facts.map((f, i) => {
        const a = ang(f)
        return <circle key={i} cx={sx(a.pitch ?? 0)} cy={sy(a.roll ?? 0)} r={3.2} fill={heat(norm(f.value))} opacity={0.9} />
      })}
      {worst && (() => { const a = ang(worst); return (
        <g>
          <circle cx={sx(a.pitch ?? 0)} cy={sy(a.roll ?? 0)} r={6} fill="none" stroke="#111" strokeWidth={1.5} />
          <text x={sx(a.pitch ?? 0) + 8} y={sy(a.roll ?? 0) - 6} fontSize="8" fill="#111">{worst.value.toFixed(0)} {unit}</text>
        </g>
      )})()}
    </svg>
  )
}

/** 전위치 부분충격 — 디바이스 외곽선 + 선택 부품 footprint + 충격 위치 값 마커. */
function DeviceMarker({ facts, norm, worst, unit, geom, partId }: {
  facts: ReportFact[]; norm: (v: number) => number; worst: ReportFact | null; unit: string
  geom: ReportGeometry | undefined; partId: number
}) {
  const bb = geom?.device_bbox
  const W = 300, H = 240, pad = 16
  const xr = bb ? [bb.xmin, bb.xmax] : [-50, 50], yr = bb ? [bb.ymin, bb.ymax] : [-40, 40]
  const sx = (x: number) => pad + ((x - xr[0]) / (xr[1] - xr[0])) * (W - 2 * pad)
  const sy = (y: number) => H - pad - ((y - yr[0]) / (yr[1] - yr[0])) * (H - 2 * pad)
  const pos = (f: ReportFact) => {
    const id = f.identity as { pos_x?: number; pos_y?: number } | null
    return { x: id?.pos_x ?? 0, y: id?.pos_y ?? 0 }
  }
  const partFp = geom?.parts.find((p) => p.part_id === partId)?.footprint
  const poly = (pts: number[][]) => pts.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[320px] border border-border rounded bg-white">
      {geom?.device_outline && <polygon points={poly(geom.device_outline)} fill="none" stroke="#bbb" strokeWidth={1} />}
      {partFp && <polygon points={poly(partFp)} fill="#4ecca355" stroke="#2a9d78" strokeWidth={1} />}
      {facts.map((f, i) => { const p = pos(f); return (
        <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={4} fill={heat(norm(f.value))} opacity={0.9} />
      )})}
      {worst && (() => { const p = pos(worst); return (
        <g>
          <circle cx={sx(p.x)} cy={sy(p.y)} r={7} fill="none" stroke="#111" strokeWidth={1.5} />
          <text x={sx(p.x) + 9} y={sy(p.y) - 7} fontSize="8" fill="#111">{worst.value.toFixed(0)} {unit}</text>
        </g>
      )})()}
      <text x={W / 2} y={H - 3} textAnchor="middle" fontSize="8" fill="#999">디바이스 XY · 초록=선택 부품 footprint</text>
    </svg>
  )
}
