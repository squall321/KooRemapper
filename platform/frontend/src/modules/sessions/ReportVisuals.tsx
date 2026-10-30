// 부품 리스크의 공간 컨텍스트 시각화 — 낙하 방향(구면)·충격 위치(디바이스)에 값 마커.
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { reportGeometry, reportQuery } from '@/shared/api/endpoints'
import type { Report, ReportFact, ReportGeometry } from '@/shared/api/types'
import { Button, Input, Select, Spinner } from '@/shared/ui/ui'
import type { GlobePoint } from './SphereGlobe3D'
import { levelOf, lonLatGrid, makeField, ratioOf, topN, type Field, type Level, type Sample } from './sphereRisk'

// 값이 없는 지표는 조회 시 빈 결과로 안내되므로, 리포트에 있으면 자동으로 채워진다.
const METRICS = [
  { v: 'peak_stress', label: '응력(MPa)' },
  { v: 'peak_g', label: 'G' },
  { v: 'peak_disp', label: '변위(mm)' },
  { v: 'peak_strain', label: '변형률' },
  { v: 'peak_plastic_strain', label: '소성변형률' },
  { v: 'peak_vel', label: '속도' },
  { v: 'peak_ie', label: '내부E(IE)' },
  { v: 'peak_ke', label: '운동E(KE)' },
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

function factLabel(f: ReportFact): string {
  const a = (f.identity as { angle?: { name?: string } })?.angle
  if (a?.name) return a.name
  const id = f.identity as { face?: string; pos_x?: number; pos_y?: number } | null
  if (id?.face) return `${id.face} (${id.pos_x ?? '?'},${id.pos_y ?? '?'})`
  return f.case_key
}

type Plot = { w: number; h: number; inner: JSX.Element; note?: string }

/** 색→값 매핑 범례를 <g> 로(자립 SVG 안에 함께 구워 내보내기 가능). */
function legendGroup(vmin: number, vmax: number, unit: string, x: number, y: number): JSX.Element {
  const stops = Array.from({ length: 12 }, (_, i) => i / 11)
  return (
    <g transform={`translate(${x},${y})`}>
      {stops.map((t, i) => <rect key={i} x={t * 168} y={0} width={168 / 11 + 0.6} height={8} fill={heat(t)} />)}
      <text x={0} y={19} fontSize="8" fill="#666" textAnchor="start">{fmtVal(vmin)}</text>
      <text x={84} y={19} fontSize="8" fill="#999" textAnchor="middle">{unit}</text>
      <text x={168} y={19} fontSize="8" fill="#666" textAnchor="end">{fmtVal(vmax)}</text>
    </g>
  )
}

/** 구면 표본의 경도 · 위도(도). 좌표는 백엔드가 swap 규약을 반영해 저장한 lon/lat 을 그대로 쓴다(구버전은 클램프 폴백). */
function sphereLonLat(f: ReportFact): { lon: number; lat: number } {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
  const wrapLon = (v: number) => (((v + 180) % 360) + 360) % 360 - 180
  const a = (f.identity as { angle?: { lon?: number; lat?: number; roll?: number; pitch?: number; swap?: boolean } })?.angle ?? {}
  if (typeof a.lon === 'number' && typeof a.lat === 'number') return { lon: wrapLon(a.lon), lat: clamp(a.lat, -90, 90) }
  // 폴백(구버전 리포트, lon/lat 미저장): swap 규약 반영 + 경도 래핑(클램프 아님).
  const roll = a.roll ?? 0, pitch = a.pitch ?? 0
  return { lon: wrapLon(a.swap ? roll : pitch), lat: clamp(a.swap ? pitch : roll, -90, 90) }
}

const angName = (f: ReportFact) => (f.identity as { angle?: { name?: string } })?.angle?.name ?? f.case_key

interface SphereExtras {
  fill: string | null                        // 보간 격자 그림(data URL) — null 이면 채우지 않는다
  levelOf: (f: ReportFact) => Level | null   // 허용값이 없으면 늘 null
  selectedKey: string | null
  onSelect: (key: string) => void
}

/** 전각도 낙하 — 등장방형(경도×위도)에 각 방향을 값으로 색칠, 최악 고리 · 임계 모양 · 고른 각도.
 *  채움(보간)은 표본 사이 추정이라 판정 · 최악은 표본 값으로만 한다. */
function spherePlot(facts: ReportFact[], colorOf: (f: ReportFact) => string, worst: ReportFact | null,
                    unit: string, fmt: (v: number) => string, ex: SphereExtras): Plot {
  const W = 320, H = 170, pad = 18
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
  const sx = (lon: number) => pad + ((lon + 180) / 360) * (W - 2 * pad)
  const sy = (lat: number) => pad + ((90 - lat) / 180) * (H - 2 * pad)
  const sel = ex.selectedKey ? facts.find((f) => f.case_key === ex.selectedKey) : undefined
  const inner = (
    <g>
      {ex.fill && <image href={ex.fill} x={pad} y={pad} width={W - 2 * pad} height={H - 2 * pad} preserveAspectRatio="none" />}
      {[-90, 0, 90].map((lat) => <line key={`la${lat}`} x1={pad} x2={W - pad} y1={sy(lat)} y2={sy(lat)} stroke={ex.fill ? '#fff' : '#eee'} strokeOpacity={ex.fill ? 0.6 : 1} />)}
      {[-180, -90, 0, 90, 180].map((lon) => <line key={`lo${lon}`} y1={pad} y2={H - pad} x1={sx(lon)} x2={sx(lon)} stroke={ex.fill ? '#fff' : '#eee'} strokeOpacity={ex.fill ? 0.6 : 1} />)}
      {[-90, 0, 90].map((lat) => <text key={`lat${lat}`} x={pad - 2} y={sy(lat) + 3} textAnchor="end" fontSize="6" fill="#bbb">{lat}°</text>)}
      {[-180, 0, 180].map((lon) => <text key={`lon${lon}`} x={sx(lon)} y={pad - 3} textAnchor="middle" fontSize="6" fill="#bbb">{lon}°</text>)}
      <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="8" fill="#999">경도(방위) →</text>
      <text x={7} y={H / 2} fontSize="8" fill="#999" transform={`rotate(-90 7 ${H / 2})`}>위도(고각) →</text>
      {facts.map((f, i) => {
        const { lon, lat } = sphereLonLat(f)
        const lv = ex.levelOf(f)
        // 임계는 색만이 아니라 모양으로도 — 초과 굵은 테두리, 경고 점선 테두리(색각 안전 램프 위라)
        const stroke = lv === 'exceed' ? '#111' : lv === 'warn' ? '#333' : '#fff'
        return (
          <circle key={i} cx={sx(lon)} cy={sy(lat)} r={lv === 'exceed' ? 3.8 : 3.2} fill={colorOf(f)}
                  stroke={stroke} strokeWidth={lv === 'exceed' ? 1.6 : lv === 'warn' ? 1.1 : 0.5}
                  strokeDasharray={lv === 'warn' ? '1.6 1' : undefined}
                  style={{ cursor: 'pointer' }} onClick={() => ex.onSelect(f.case_key)}>
            <title>{`${angName(f)} · ${fmt(f.value)} ${unit}`}</title>
          </circle>
        )
      })}
      {worst && (() => { const { lon, lat } = sphereLonLat(worst); return (
        <g>
          <circle cx={sx(lon)} cy={sy(lat)} r={6} fill="none" stroke="#111" strokeWidth={1.5} />
          <text x={clamp(sx(lon) + 8, 0, W - 40)} y={clamp(sy(lat) - 6, 10, H)} fontSize="8" fill="#111">{fmt(worst.value)} {unit}</text>
        </g>
      )})()}
      {sel && (() => { const { lon, lat } = sphereLonLat(sel); return (
        <g>
          <circle cx={sx(lon)} cy={sy(lat)} r={8} fill="none" stroke="#e11d48" strokeWidth={1.6} />
          <text x={clamp(sx(lon) + 9, 0, W - 60)} y={clamp(sy(lat) + 12, 10, H - 2)} fontSize="7" fill="#e11d48">{angName(sel)}</text>
        </g>
      )})()}
    </g>
  )
  return { w: W, h: H, inner, note: ex.fill ? '채움은 표본 사이 보간(추정)이다 — 판정 · 순위 · 최악은 표본 값으로 한다.' : undefined }
}

/** 전위치 부분충격 — 디바이스 외곽선 + 선택 부품 footprint + 충격 위치 값 마커.
 *  종횡비를 보존(늘어남 방지)하고, bbox 결측 시 외곽선/footprint 로 범위를 유추한다. */
function devicePlot(facts: ReportFact[], norm: (v: number) => number, worst: ReportFact | null,
                    unit: string, fmt: (v: number) => string,
                    geom: ReportGeometry | undefined, partId: number): Plot {
  const W = 300, H = 240, pad = 16
  const partRec = geom?.parts.find((p) => p.part_id === partId)
  const partFp = partRec?.footprint ?? null
  // ★합성 footprint 는 **실측 형상이 아니다** — 상류가 파트 id 해시로 지어낸 사각형이다.
  //   같은 초록 채움으로 그리면 "부품이 여기 있다" 는 거짓이 된다. 점선 외곽 + 글자로 가린다.
  const fpSynth = partRec?.synthetic_footprint === true
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
  const inner = (
    <g>
      {geom?.device_outline && <polygon points={poly(geom.device_outline)} fill="none" stroke="#bbb" strokeWidth={1} />}
      {partFp && (fpSynth
        ? <polygon points={poly(partFp)} fill="none" stroke="#a33" strokeWidth={1} strokeDasharray="3 2" />
        : <polygon points={poly(partFp)} fill="#4ecca355" stroke="#2a9d78" strokeWidth={1} />)}
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
      <text x={W / 2} y={H - 3} textAnchor="middle" fontSize="8" fill={fpSynth ? '#a33' : '#999'}>
        {fpSynth
          ? '디바이스 XY · ⚠ 빨간 점선 = **지어낸** footprint (실측 형상 아님)'
          : '디바이스 XY · 초록=선택 부품 footprint'}
      </text>
    </g>
  )
  return {
    w: W, h: H, inner,
    note: coincident ? '충격 위치가 모두 같은 좌표에 뭉쳐 있습니다(면 단위 낙하로 보임) — 개별 위치 구분은 리포트 조건에 따라 달라집니다.' : undefined,
  }
}

function serializeSvg(svg: SVGSVGElement): string {
  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  return new XMLSerializer().serializeToString(clone)
}
function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}
function exportSvg(svg: SVGSVGElement, name: string) {
  downloadBlob(new Blob([serializeSvg(svg)], { type: 'image/svg+xml' }), `${name}.svg`)
}
async function exportPng(svg: SVGSVGElement, name: string, scale = 2) {
  const vb = svg.viewBox.baseVal
  const src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializeSvg(svg))
  const img = new Image()
  await new Promise<void>((res, rej) => { img.onload = () => res(); img.onerror = () => rej(new Error('svg load')); img.src = src })
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(vb.width * scale); canvas.height = Math.round(vb.height * scale)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((b) => { if (b) downloadBlob(b, `${name}.png`) }, 'image/png')
}

/** 캡션+플롯+범례를 하나의 자립 SVG 로 합쳐 그리고, 그 SVG 를 그대로 PNG/SVG 로 내보낸다. */
function MarkerFigure({ plot, caption, vmin, vmax, unit, fileBase }: {
  plot: Plot; caption: string; vmin: number; vmax: number; unit: string; fileBase: string
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const CAP = 18, GAP = 8, LEG_H = 22
  const totH = CAP + plot.h + GAP + LEG_H
  const legX = Math.max(0, (plot.w - 168) / 2)
  return (
    <div className="space-y-1">
      <svg ref={svgRef} viewBox={`0 0 ${plot.w} ${totH}`}
           className="w-full border border-border rounded"
           style={{ maxWidth: plot.w + 40, background: '#fff' }}>
        <rect x={0} y={0} width={plot.w} height={totH} fill="#fff" />
        <text x={plot.w / 2} y={13} textAnchor="middle" fontSize="10" fill="#333" fontWeight="600">{caption}</text>
        <g transform={`translate(0,${CAP})`}>{plot.inner}</g>
        {legendGroup(vmin, vmax, unit, legX, CAP + plot.h + GAP)}
      </svg>
      {plot.note && <div className="text-[10px] text-amber-600">{plot.note}</div>}
      <div className="flex gap-1">
        <Button size="sm" variant="ghost" onClick={() => svgRef.current && exportPng(svgRef.current, fileBase)}>
          <Download size={12} /> PNG
        </Button>
        <Button size="sm" variant="ghost" onClick={() => svgRef.current && exportSvg(svgRef.current, fileBase)}>
          <Download size={12} /> SVG
        </Button>
      </div>
    </div>
  )
}

// 3D 구는 three.js 라 처음 열 때만 받는다 — 첫 화면 묶음을 키우지 않는다.
const SphereGlobe3D = lazy(() => import('./SphereGlobe3D'))
// 형상 뷰어도 three.js(+ glb 읽기)라 「형상 보기」 를 누를 때만 받는다.
const CadViewer3D = lazy(() => import('./CadViewer3D'))
const LEGEND_STOPS = Array.from({ length: 12 }, (_, i) => heat(i / 11))

/** 허용값 칸 — 이 브라우저에만 둔다(리포트 · 부품 · 물리량별). 넣은 적이 없으면 기본값(있으면)을 쓴다.
 *  돌려주는 셋째 값은 「기본값을 쓰는 중」 이다(화면에 그렇다고 적는다). */
function useAllowable(key: string, fallback: string): [string, (v: string) => void, boolean] {
  const read = useCallback(() => {
    try { return window.localStorage.getItem(key) } catch { return null }
  }, [key])
  const [stored, setStored] = useState<string | null>(read)
  useEffect(() => { setStored(read()) }, [read])
  const set = (v: string) => {
    setStored(v)
    try { window.localStorage.setItem(key, v) } catch { /* 저장 못 해도 이 화면에는 쓴다 */ }
  }
  return [stored ?? fallback, set, stored == null && fallback !== '']
}

/** 보간 격자 → 그림(data URL) — 경도 -180→180 · 위도 90→-90. 표본이 많으면 칸을 키운다(셈 시간). */
function gridImage(field: Field, nSamples: number, color: (v: number) => string): string {
  const g = lonLatGrid(field, nSamples > 1000 ? 3 : 2)
  const c = document.createElement('canvas')
  c.width = g.w
  c.height = g.h
  const ctx = c.getContext('2d')!
  for (let r = 0; r < g.h; r++) {
    for (let k = 0; k < g.w; k++) {
      ctx.fillStyle = color(g.values[r * g.w + k])
      ctx.fillRect(k, r, 1, 1)
    }
  }
  return c.toDataURL('image/png')
}

const LEVEL_LABEL: Record<Level, string> = { exceed: '초과', warn: '경고', ok: '정상' }

export function ReportVisuals({ report }: { report: Report }) {
  const partList = report.parts ?? []
  // 기본 파트를 parts[0](흔히 강체/바닥 파트1, 값이 비거나 0)이 아니라 최악응력 파트로 —
  // 첫 화면이 빈 맵으로 떠 '데이터 없음'으로 오독되는 것 방지(파트1 함정).
  const worstPart = (report.summary as { worst_stress?: { part_id?: number } } | null)?.worst_stress?.part_id
  const [partId, setPartId] = useState<number | ''>(
    (typeof worstPart === 'number' ? worstPart : partList[0]?.part_id) ?? '')
  const [metric, setMetric] = useState('peak_stress')
  const isSphere = report.kind === 'sphere'
  const [view, setView] = useState<'2d' | '3d'>('2d')
  const [fillOn, setFillOn] = useState(true)
  const [warnRatio, setWarnRatio] = useState(0.8)
  const [nTop, setNTop] = useState(10)
  const [selected, setSelected] = useState<string | null>(null)
  const [cadOpen, setCadOpen] = useState(false)
  // 응력의 기본 허용값 — 리포트에 연구 전체 항복응력이 있을 때만(부품별 값은 리포트에 없다)
  const yieldStress = Number((report.sim_params as { yield_stress?: unknown } | null)?.yield_stress)
  const stressDefault = metric === 'peak_stress' && Number.isFinite(yieldStress) && yieldStress > 0 ? String(yieldStress) : ''
  const [allowText, setAllowText, allowIsDefault] = useAllowable(`koorm:allow:${report.id}:${partId}:${metric}`, stressDefault)
  const allowNum = Number(allowText)
  const allowable = isSphere && allowText.trim() !== '' && Number.isFinite(allowNum) && allowNum > 0 ? allowNum : null
  const ratioMode = allowable != null

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

  const fs = useMemo(() => facts.data?.facts ?? [], [facts.data])
  const samples = useMemo<Sample[]>(
    () => (isSphere ? fs.map((f) => ({ key: f.case_key, name: angName(f), ...sphereLonLat(f), value: f.value })) : []),
    [fs, isSphere])
  // 색은 「보이는 값」 으로 — 허용값이 있으면 허용비(0 부터, 1 이 보이게), 없으면 값의 범위
  const shownOf = useCallback((v: number) => (allowable != null ? v / allowable : v), [allowable])
  const shown = fs.map((f) => shownOf(f.value))
  const lo = ratioMode ? 0 : (shown.length ? Math.min(...shown) : 0)
  const hiRaw = shown.length ? Math.max(...shown) : 1
  const hi = ratioMode ? Math.max(1, hiRaw) : hiRaw
  const colorOfShown = useCallback((v: number) => heat(hi > lo ? (v - lo) / (hi - lo) : 0.5), [lo, hi])
  const levelOfFact = useCallback((f: ReportFact) => levelOf(ratioOf(f.value, allowable), warnRatio), [allowable, warnRatio])
  const field = useMemo(() => (isSphere && fillOn && samples.length >= 3 ? makeField(samples) : null),
                        [isSphere, fillOn, samples])
  const fillHref = useMemo(() => (field && view === '2d'
    ? gridImage(field, samples.length, (v) => colorOfShown(shownOf(v))) : null),
    [field, view, samples.length, colorOfShown, shownOf])
  const top = useMemo(() => topN(samples, nTop), [samples, nTop])
  const globePoints = useMemo<GlobePoint[]>(() => samples.map((s) => {
    const r = ratioOf(s.value, allowable)
    return { key: s.key, name: s.name, lon: s.lon, lat: s.lat, shown: r ?? s.value,
             level: levelOf(r, warnRatio), label: `${s.name} · ${fmtVal(s.value)}` }
  }), [samples, allowable, warnRatio])

  if (report.kind === 'deep') {
    return <div className="text-muted text-[11px]">단건 심층 리포트는 방향/위치 마커가 없습니다 — 원본 리포트 렌더를 보세요.</div>
  }

  const norm = (v: number) => (hi > lo ? (v - lo) / (hi - lo) : 0.5)
  const worst = fs.reduce<ReportFact | null>((a, f) => (!a || f.value > a.value ? f : a), null)
  const unit = METRICS.find((m) => m.v === metric)?.label ?? metric
  const partName = partList.find((p) => p.part_id === Number(partId))?.name ?? `Part ${partId}`
  const legendUnit = ratioMode ? '허용비(1 = 허용값)' : unit
  const caption = `${partName} · ${ratioMode ? `허용비(허용값 ${fmtVal(allowable as number)})` : unit}`
    + (field ? ' · 보간 채움(추정)' : '')
  const fileBase = `${report.kind}_${partName}_${metric}`.replace(/[^\w.-]+/g, '_')
  const levels = ratioMode ? samples.map((s) => levelOf(ratioOf(s.value, allowable), warnRatio)) : []
  const nExceed = levels.filter((l) => l === 'exceed').length
  const nWarn = levels.filter((l) => l === 'warn').length

  const plot: Plot | null = !fs.length ? null
    : isSphere ? spherePlot(fs, (f) => colorOfShown(shownOf(f.value)), worst, unit, fmtVal,
                            { fill: fillHref, levelOf: levelOfFact, selectedKey: selected, onSelect: setSelected })
    : devicePlot(fs, norm, worst, unit, fmtVal, geom.data, Number(partId))

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap text-[11px]">
        <span className="text-muted">부품 위치·방향 시각화</span>
        {/* 공용 Select 는 w-full 이고 cn 이 clsx 라 넘긴 폭이 밀린다 — 폭은 감싼 상자로 준다 */}
        <div className="w-40 shrink-0">
          <Select value={String(partId)} onChange={(e) => setPartId(e.target.value === '' ? '' : Number(e.target.value))}
                  className="h-7 text-xs">
            {partList.map((p) => <option key={p.part_id} value={p.part_id}>{p.name ?? `Part ${p.part_id}`}</option>)}
          </Select>
        </div>
        <div className="w-28 shrink-0">
          <Select value={metric} onChange={(e) => setMetric(e.target.value)} className="h-7 text-xs">
            {METRICS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
          </Select>
        </div>
        {worst && <span className="text-fg">최악 <b>{fmtVal(worst.value)}</b> @ {factLabel(worst)}</span>}
      </div>

      {isSphere && (
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <div className="w-24 shrink-0">
            <Select value={view} onChange={(e) => setView(e.target.value as '2d' | '3d')} className="h-7 text-xs">
              <option value="2d">평면(2D)</option>
              <option value="3d">구(3D)</option>
            </Select>
          </div>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={fillOn} onChange={(e) => setFillOn(e.target.checked)} /> 보간 채움
          </label>
          <span className="text-muted">허용값</span>
          <div className="w-24 shrink-0">
            <Input type="number" value={allowText} placeholder="없음" onChange={(e) => setAllowText(e.target.value)}
                   className="h-7 text-xs" />
          </div>
          <span className="text-muted">{unit}</span>
          <span className="text-muted">경고 ≥</span>
          <div className="w-16 shrink-0">
            <Input type="number" step="0.05" min="0.1" max="0.99" value={warnRatio}
                   onChange={(e) => { const v = Number(e.target.value); if (v > 0 && v < 1) setWarnRatio(v) }}
                   className="h-7 text-xs" />
          </div>
          <span className="text-muted">상위</span>
          <div className="w-16 shrink-0">
            <Select value={String(nTop)} onChange={(e) => setNTop(Number(e.target.value))} className="h-7 text-xs">
              {[5, 10, 20, 50].map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </div>
        </div>
      )}
      {isSphere && allowIsDefault && (
        <div className="text-[10px] text-amber-600">
          허용값은 리포트 기본값이다 — 연구 전체 항복응력 하나라 부품별 값이 아니다. 부품에 맞는 값을 넣어 바꿀 수 있다(이 브라우저에만 남는다).
        </div>
      )}
      {isSphere && fs.length > 0 && (ratioMode ? (
        <div className="text-[11px]">
          초과 <b>{nExceed}</b> · 경고 <b>{nWarn}</b> / 표본 {samples.length} — 판정은 표본 값 ÷ 허용값(경고 ≥ {warnRatio})
        </div>
      ) : (
        <div className="text-[10px] text-muted">허용값을 넣으면 허용비 · 임계(초과 · 경고)가 보인다.</div>
      ))}

      {facts.isLoading || (report.kind === 'impact' && geom.isLoading) ? <Spinner /> : !plot ? (
        <div className="text-muted text-[11px]">이 부품·물리량의 값이 없습니다.</div>
      ) : (
        <div className="space-y-1">
          {isSphere && view === '3d' ? (
            <Suspense fallback={<Spinner />}>
              <SphereGlobe3D points={globePoints} field={field} fieldToShown={shownOf} colorOf={colorOfShown}
                             selectedKey={selected} onSelect={setSelected} caption={caption}
                             legend={{ lo: fmtVal(lo), hi: fmtVal(hi), unit: legendUnit, colors: LEGEND_STOPS }}
                             fileBase={fileBase} />
            </Suspense>
          ) : (
            <MarkerFigure plot={plot} caption={caption} vmin={lo} vmax={hi} unit={legendUnit} fileBase={fileBase} />
          )}
          {facts.data?.truncated && (
            <div className="text-[10px] text-amber-600">
              값이 많아 {fs.length}건만 표시(색 스케일이 일부 편향될 수 있음). 부품/물리량으로 좁혀 보세요.
            </div>
          )}
          {isSphere && view === '3d' && field && (
            <div className="text-[10px] text-amber-600">면 색은 표본 사이 보간(추정)이다 — 판정 · 순위 · 최악은 표본 값으로 한다.</div>
          )}
        </div>
      )}

      {isSphere && selected && (
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span>고른 각도 <b>{samples.find((s) => s.key === selected)?.name ?? selected}</b></span>
          {report.cad ? (
            <Button size="sm" onClick={() => setCadOpen((v) => !v)}>{cadOpen ? '형상 닫기' : '형상 보기'}</Button>
          ) : (
            <span className="text-muted">
              형상 묶음이 없다 — StepForge fe_cad 묶음을 MCP <code>attach_cad(report_id, 묶음 폴더)</code> 나
              REST <code>POST /reports/{'{id}'}/cad</code>(zip)로 붙이면 여기서 연다.
            </span>
          )}
        </div>
      )}
      {isSphere && selected && cadOpen && report.cad && (
        <Suspense fallback={<Spinner />}>
          <CadViewer3D reportId={report.id} sessionId={report.session_id} cad={report.cad} caseKey={selected}
                       caseName={samples.find((s) => s.key === selected)?.name ?? selected}
                       metric={metric} metricLabel={unit} highlightPid={partId === '' ? null : Number(partId)}
                       colorOf={heat} fmt={fmtVal} legendColors={LEGEND_STOPS} onClose={() => setCadOpen(false)} />
        </Suspense>
      )}

      {isSphere && top.length > 0 && (
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="text-muted text-left">
              <th className="font-normal pr-2">#</th>
              <th className="font-normal pr-2">각도</th>
              <th className="font-normal pr-2 text-right">{unit}</th>
              {ratioMode && <th className="font-normal pr-2 text-right">허용비</th>}
              {ratioMode && <th className="font-normal pr-2">판정</th>}
              <th className="font-normal">경도 / 위도</th>
            </tr>
          </thead>
          <tbody>
            {top.map((s, i) => {
              const r = ratioOf(s.value, allowable)
              const lv = levelOf(r, warnRatio)
              return (
                <tr key={s.key} onClick={() => setSelected(s.key)} className="cursor-pointer border-t border-border"
                    style={selected === s.key ? { background: '#fff1f2' } : undefined}>
                  <td className="pr-2">{i + 1}</td>
                  <td className="pr-2">{s.name}</td>
                  <td className="pr-2 text-right">{fmtVal(s.value)}</td>
                  {/* 셋째 자리까지 — 둘째 자리 반올림은 0.7986 을 「0.80 · 정상」 처럼 경계와 같아 보이게 한다 */}
                  {ratioMode && <td className="pr-2 text-right">{r != null ? r.toFixed(3) : '–'}</td>}
                  {ratioMode && <td className="pr-2">{lv ? LEVEL_LABEL[lv] : '–'}</td>}
                  <td className="text-muted">{s.lon.toFixed(0)}° / {s.lat.toFixed(0)}°</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
