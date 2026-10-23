// 낙하 결과 기준 접촉 그림 — 한 각도의 하중경로 층 그래프와 파트쌍 × 각도(위치) 히트맵. 외부 의존 없이 SVG·캔버스
//
// 두 그림 다 생성기 데이터를 **다시 계산하지 않고** 그린다. 값이 없는 칸(None)은 '그 각도에 그 접촉이 없다' 이고 0 이
// 아니다 — 히트맵은 그 칸을 비워 두고, 0 은 옅게라도 칠한다.
import { useEffect, useMemo, useRef, useState } from 'react'

export interface FlowNode {
  id: string
  name?: string | null
  is_impactor?: boolean
}
export interface FlowEdge {
  key?: string
  src: string
  dst: string
  name?: string | null
  /** 굵기의 기준 — 최대 접촉력. 없으면 점선으로 그린다. */
  value: number | null
  work?: number | null
  impulse?: number | null
}

function smartNum(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2)
  return a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toFixed(4)
}

function themeColor(name: string, alpha = 1): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return raw ? `hsl(${raw} / ${alpha})` : `rgba(80,120,220,${alpha})`
}

// 층 — 충격체(없으면 들어오는 엣지가 없는 노드)에서 BFS 깊이. 닿지 않는 노드는 맨 끝 열에 따로 둔다.
function layerOf(nodes: FlowNode[], edges: FlowEdge[]): Map<string, number> {
  const out = new Map<string, number>()
  const adj = new Map<string, string[]>()
  const indeg = new Map<string, number>()
  for (const n of nodes) { adj.set(n.id, []); indeg.set(n.id, 0) }
  for (const e of edges) {
    adj.get(e.src)?.push(e.dst)
    indeg.set(e.dst, (indeg.get(e.dst) ?? 0) + 1)
  }
  let roots = nodes.filter((n) => n.is_impactor).map((n) => n.id)
  if (!roots.length) roots = nodes.filter((n) => (indeg.get(n.id) ?? 0) === 0 && (adj.get(n.id)?.length ?? 0) > 0).map((n) => n.id)
  if (!roots.length && edges.length) {
    const top = [...edges].sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0))[0]
    roots = [top.src]
  }
  const q = [...roots]
  for (const r of roots) out.set(r, 0)
  while (q.length) {
    const u = q.shift()!
    for (const v of adj.get(u) ?? []) {
      if (!out.has(v)) { out.set(v, (out.get(u) ?? 0) + 1); q.push(v) }
    }
  }
  const maxD = Math.max(0, ...out.values())
  for (const n of nodes) if (!out.has(n.id)) out.set(n.id, maxD + 1)
  return out
}

export function LoadPathGraph({ nodes, edges, valueLabel = '최대 접촉력' }: {
  nodes: FlowNode[]
  edges: FlowEdge[]
  valueLabel?: string
}) {
  const [hover, setHover] = useState<string | null>(null)
  const all = useMemo(() => {
    const m = new Map<string, FlowNode>()
    for (const n of nodes) m.set(n.id, n)
    for (const e of edges) {
      if (!m.has(e.src)) m.set(e.src, { id: e.src, name: e.src })
      if (!m.has(e.dst)) m.set(e.dst, { id: e.dst, name: e.dst })
    }
    // 엣지가 하나도 닿지 않는 노드는 그림에서 뺀다(하중경로 밖이다)
    const touched = new Set(edges.flatMap((e) => [e.src, e.dst]))
    return [...m.values()].filter((n) => touched.has(n.id))
  }, [nodes, edges])
  const layer = useMemo(() => layerOf(all, edges), [all, edges])
  const load = useMemo(() => {
    const l = new Map<string, number>()
    for (const e of edges) {
      const v = Math.abs(e.value ?? 0)
      l.set(e.src, (l.get(e.src) ?? 0) + v)
      l.set(e.dst, (l.get(e.dst) ?? 0) + v)
    }
    return l
  }, [edges])
  const colW = 176, rowH = 30, boxW = 132, boxH = 22, pad = 14
  const pos = useMemo(() => {
    const cols = new Map<number, FlowNode[]>()
    for (const n of all) {
      const d = layer.get(n.id) ?? 0
      if (!cols.has(d)) cols.set(d, [])
      cols.get(d)!.push(n)
    }
    const p = new Map<string, { x: number; y: number }>()
    for (const [d, list] of cols) {
      list.sort((a, b) => (load.get(b.id) ?? 0) - (load.get(a.id) ?? 0))
      list.forEach((n, i) => p.set(n.id, { x: pad + d * colW, y: pad + i * rowH }))
    }
    return { p, nCols: Math.max(1, ...[...cols.keys()].map((k) => k + 1)), nRows: Math.max(1, ...[...cols.values()].map((l) => l.length)) }
  }, [all, layer, load])
  const vmax = Math.max(1e-12, ...edges.map((e) => Math.abs(e.value ?? 0)))
  if (!edges.length) return <div className="text-[11px] text-muted">그릴 접촉 엣지가 없다.</div>
  const width = pad * 2 + (pos.nCols - 1) * colW + boxW
  const height = pad * 2 + (pos.nRows - 1) * rowH + boxH
  return (
    <div className="space-y-1">
      <div className="overflow-x-auto">
        <svg width={width} height={height} className="select-none">
          {edges.map((e, i) => {
            const a = pos.p.get(e.src), b = pos.p.get(e.dst)
            if (!a || !b) return null
            const on = hover === null || hover === e.src || hover === e.dst
            const x1 = a.x + boxW, y1 = a.y + boxH / 2, x2 = b.x, y2 = b.y + boxH / 2
            // 같은 열이거나 거꾸로 가는 엣지는 위로 휘게 그린다(겹치지 않게)
            const back = x2 <= x1
            const d = back
              ? `M ${a.x + boxW / 2} ${a.y} C ${a.x + boxW / 2} ${a.y - 26}, ${b.x + boxW / 2} ${b.y - 26}, ${b.x + boxW / 2} ${b.y}`
              : `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`
            const w = e.value == null ? 1 : 1 + 7 * (Math.abs(e.value) / vmax)
            return (
              <path key={e.key ?? i} d={d} fill="none" stroke="currentColor"
                    className={on ? 'text-primary' : 'text-border'} strokeWidth={w}
                    strokeDasharray={e.value == null ? '3 3' : undefined} opacity={on ? 0.75 : 0.25}>
                <title>{`${e.name ?? e.key ?? ''} ${e.src} → ${e.dst}\n${valueLabel} ${smartNum(e.value)}`
                  + (e.work != null ? ` · 일 ${smartNum(e.work)}` : '') + (e.impulse != null ? ` · 충격량 ${smartNum(e.impulse)}` : '')}</title>
              </path>
            )
          })}
          {all.map((n) => {
            const q = pos.p.get(n.id)!
            const label = n.name || n.id
            return (
              <g key={n.id} transform={`translate(${q.x},${q.y})`} onMouseEnter={() => setHover(n.id)}
                 onMouseLeave={() => setHover(null)} style={{ cursor: 'default' }}>
                <rect width={boxW} height={boxH} rx={4}
                      fill={n.is_impactor ? themeColor('--danger', 0.18) : themeColor('--surface')}
                      stroke={themeColor('--border')} />
                <text x={6} y={15} fontSize={10.5} fill="currentColor" className="text-fg">
                  {label.length > 20 ? label.slice(0, 19) + '…' : label}
                </text>
                <title>{`${label} (${n.id})${n.is_impactor ? ' — 충격체' : ''} · 접촉력 합 ${smartNum(load.get(n.id))}`}</title>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="text-[10px] text-muted">
        굵기 = {valueLabel}(최대 {smartNum(vmax)}) · 왼쪽부터 충격체 → 전파 깊이 · 점선은 값 없음 · 노드에 올리면 그 파트의 엣지만 진하게
      </div>
    </div>
  )
}

export interface HeatRow { key: string; label: string; resolved: boolean }
export interface HeatCol { case_key: string | null; label: string | null }

export function ContactHeatmap({ rows, cols, values, selected, onPick, valueLabel }: {
  rows: HeatRow[]
  cols: HeatCol[]
  values: (number | null)[][]
  selected?: string | null
  onPick?: (caseKey: string) => void
  valueLabel: string
}) {
  const ref = useRef<HTMLCanvasElement | null>(null)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const labelW = 190, cellH = 14, axisH = 18
  const cellW = Math.max(3, Math.min(18, Math.floor(900 / Math.max(1, cols.length))))
  // 오른쪽에 축 이름이 들어갈 자리를 남긴다(열이 하나여도 이름이 잘리지 않게)
  const width = labelW + Math.max(cols.length * cellW, 40) + 72
  const height = rows.length * cellH + axisH
  const vmax = useMemo(() => {
    let m = 0
    for (const r of values) for (const v of r) if (v != null) m = Math.max(m, Math.abs(v))
    return m || 1
  }, [values])
  useEffect(() => {
    const c = ref.current
    if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = width * dpr
    c.height = height * dpr
    const g = c.getContext('2d')
    if (!g) return
    g.scale(dpr, dpr)
    g.clearRect(0, 0, width, height)
    g.font = '10px ui-sans-serif, system-ui'
    g.textBaseline = 'middle'
    const fg = themeColor('--fg'), muted = themeColor('--muted'), grid = themeColor('--border', 0.6)
    rows.forEach((r, i) => {
      const y = i * cellH
      g.fillStyle = r.resolved ? fg : muted
      const t = r.label.length > 30 ? r.label.slice(0, 29) + '…' : r.label
      g.fillText(t, 2, y + cellH / 2)
      g.strokeStyle = grid
      g.beginPath(); g.moveTo(labelW, y + cellH - 0.5); g.lineTo(width, y + cellH - 0.5); g.stroke()
      const row = values[i] ?? []
      for (let j = 0; j < cols.length; j++) {
        const v = row[j]
        if (v == null) continue            // 접촉 없음 — 비워 둔다(0 이 아니다)
        g.fillStyle = themeColor('--primary', 0.12 + 0.88 * (Math.abs(v) / vmax))
        g.fillRect(labelW + j * cellW, y + 1, Math.max(1, cellW - 1), cellH - 2)
      }
    })
    if (selected) {
      const j = cols.findIndex((c2) => c2.case_key === selected)
      if (j >= 0) {
        g.strokeStyle = themeColor('--danger')
        g.lineWidth = 1.5
        g.strokeRect(labelW + j * cellW, 0, cellW, rows.length * cellH)
        g.lineWidth = 1
      }
    }
    // 축 눈금 — 열이 많으면 띄엄띄엄
    g.fillStyle = muted
    const every = Math.max(1, Math.ceil(cols.length / Math.max(1, Math.floor((width - labelW) / 60))))
    cols.forEach((c2, j) => {
      if (j % every) return
      g.fillText(c2.label ?? String(j), labelW + j * cellW, rows.length * cellH + axisH / 2)
    })
  }, [rows, cols, values, selected, width, height, cellW, vmax])
  const at = (ev: React.MouseEvent) => {
    const r = (ev.target as HTMLCanvasElement).getBoundingClientRect()
    const x = ev.clientX - r.left, y = ev.clientY - r.top
    const j = Math.floor((x - labelW) / cellW), i = Math.floor(y / cellH)
    if (x < labelW || i < 0 || i >= rows.length || j < 0 || j >= cols.length) return null
    return { i, j, x, y }
  }
  return (
    <div className="relative overflow-x-auto">
      <canvas ref={ref} style={{ width, height, cursor: onPick ? 'pointer' : 'default' }}
              onMouseMove={(ev) => {
                const h = at(ev)
                if (!h) { setTip(null); return }
                const v = values[h.i]?.[h.j]
                setTip({ x: h.x + 12, y: h.y + 10,
                         text: `${rows[h.i].label} · ${cols[h.j].label ?? cols[h.j].case_key} · ${valueLabel} `
                           + (v == null ? '접촉 없음' : smartNum(v)) })
              }}
              onMouseLeave={() => setTip(null)}
              onClick={(ev) => {
                const h = at(ev)
                const ck = h ? cols[h.j].case_key : null
                if (ck && onPick) onPick(ck)
              }} />
      {tip && (
        <div className="absolute pointer-events-none bg-bg border border-border rounded px-1.5 py-0.5 text-[10px] text-fg shadow"
             style={{ left: tip.x, top: tip.y }}>{tip.text}</div>
      )}
    </div>
  )
}
