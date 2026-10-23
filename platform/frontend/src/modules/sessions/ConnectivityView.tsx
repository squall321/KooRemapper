// K파일 파트 연결도(접촉 connectivity)를 SVG 원형 그래프 + 파트 메트릭 표로 시각화
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Network, Sparkles } from 'lucide-react'
import { extractConnectivity } from '@/shared/api/endpoints'
import { errorMessage } from '@/shared/api/client'
import type { ModelMeta, ModelEdge } from '@/shared/api/types'
import { Button, Spinner } from '@/shared/ui/ui'

// 파트를 원둘레에 배치하고 접촉 엣지를 현(chord)으로 그린다. 외부 의존성 없음.
function Graph({ parts, edges, highlight }: {
  parts: { pid: number; title: string }[]
  edges: ModelEdge[]
  highlight: number | null
}) {
  const size = 460
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 70
  const n = parts.length
  const pos = useMemo(() => {
    const m = new Map<number, { x: number; y: number; a: number }>()
    parts.forEach((p, i) => {
      const a = (i / Math.max(1, n)) * Math.PI * 2 - Math.PI / 2
      m.set(p.pid, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), a })
    })
    return m
  }, [parts, n, cx, cy, r])

  // 파트별 접촉 차수(연결 수) — 노드 크기에 반영
  const degree = useMemo(() => {
    const d = new Map<number, number>()
    for (const e of edges) {
      d.set(e.a, (d.get(e.a) ?? 0) + 1)
      d.set(e.b, (d.get(e.b) ?? 0) + 1)
    }
    return d
  }, [edges])

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[460px] mx-auto select-none">
      {edges.map((e, i) => {
        const a = pos.get(e.a)
        const b = pos.get(e.b)
        if (!a || !b) return null
        const on = highlight === null || highlight === e.a || highlight === e.b
        return (
          <path
            key={i}
            d={`M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`}
            fill="none"
            stroke="currentColor"
            className={on ? 'text-primary' : 'text-border'}
            strokeWidth={on ? 1.1 : 0.5}
            opacity={on ? 0.55 : 0.2}
          />
        )
      })}
      {parts.map((p) => {
        const q = pos.get(p.pid)!
        const deg = degree.get(p.pid) ?? 0
        const on = highlight === null || highlight === p.pid
        const nodeR = 3 + Math.min(6, deg)
        const right = Math.cos(q.a) >= 0
        return (
          <g key={p.pid} opacity={on ? 1 : 0.35}>
            <circle cx={q.x} cy={q.y} r={nodeR}
              className={deg ? 'fill-primary' : 'fill-muted'} />
            <text
              x={q.x + (right ? 8 : -8)} y={q.y}
              textAnchor={right ? 'start' : 'end'}
              dominantBaseline="middle"
              className="fill-current text-muted"
              style={{ fontSize: 8 }}
            >
              {p.title || `PID ${p.pid}`}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// 빽빽한 모델용 — 파트 × 파트 인접 행렬. 원형 현 그림은 엣지가 수백이면 읽히지 않는다(실측: 61파트 배터리 덱의
// 기하 탐지가 700쌍). 칸 — *CONTACT 로 정의된 쌍은 진하게, 기하 탐지로만 찾은 쌍은 옅게. 연결 수 순으로 세운다.
function Matrix({ parts, cardEdges, geoEdges, highlight, onHover }: {
  parts: { pid: number; title: string }[]
  cardEdges: ModelEdge[]
  geoEdges: ModelEdge[]
  highlight: number | null
  onHover: (pid: number | null) => void
}) {
  const key = (a: number, b: number) => (a < b ? `${a}-${b}` : `${b}-${a}`)
  const card = useMemo(() => new Set(cardEdges.map((e) => key(e.a, e.b))), [cardEdges])
  const geo = useMemo(() => new Map(geoEdges.map((e) => [key(e.a, e.b), e])), [geoEdges])
  const all = useMemo(() => {
    const m = new Map<string, ModelEdge>()
    for (const e of [...geoEdges, ...cardEdges]) m.set(key(e.a, e.b), e)
    return [...m.values()]
  }, [cardEdges, geoEdges])
  const order = useMemo(() => {
    const deg = new Map<number, number>()
    for (const e of all) { deg.set(e.a, (deg.get(e.a) ?? 0) + 1); deg.set(e.b, (deg.get(e.b) ?? 0) + 1) }
    return [...parts].sort((x, y) => (deg.get(y.pid) ?? 0) - (deg.get(x.pid) ?? 0) || x.pid - y.pid)
  }, [parts, all])
  const idx = useMemo(() => new Map(order.map((p, i) => [p.pid, i])), [order])
  const n = order.length
  const cell = Math.max(4, Math.min(14, Math.floor(560 / Math.max(1, n))))
  const labelW = 130
  const hiIdx = highlight == null ? -1 : idx.get(highlight) ?? -1
  return (
    <div className="overflow-auto max-h-[640px]">
      <svg width={labelW + n * cell + 2} height={n * cell + 2} className="select-none">
        {hiIdx >= 0 && (
          <>
            <rect x={labelW} y={hiIdx * cell} width={n * cell} height={cell} className="fill-primary" opacity={0.08} />
            <rect x={labelW + hiIdx * cell} y={0} width={cell} height={n * cell} className="fill-primary" opacity={0.08} />
          </>
        )}
        {order.map((p, i) => (
          <text key={p.pid} x={labelW - 4} y={i * cell + cell / 2} textAnchor="end" dominantBaseline="middle"
                className="fill-current text-muted" style={{ fontSize: Math.min(9, cell) }}
                onMouseEnter={() => onHover(p.pid)} onMouseLeave={() => onHover(null)}>
            {(p.title || `PID ${p.pid}`).slice(0, 22)}
          </text>
        ))}
        <rect x={labelW} y={0} width={n * cell} height={n * cell} fill="none" stroke="currentColor"
              className="text-border" />
        {all.map((e) => {
          const i = idx.get(e.a), j = idx.get(e.b)
          if (i == null || j == null) return null
          const k = key(e.a, e.b)
          const isCard = card.has(k)
          const g = geo.get(k)
          const tip = `${e.a_title || e.a} ↔ ${e.b_title || e.b}`
            + (isCard ? ` · *CONTACT ${e.type ?? ''}${e.title ? ` "${e.title}"` : ''}${e.cid != null ? ` (CID ${e.cid})` : ''}` : '')
            + (g && g.gap_min != null ? ` · 기하 gap_min ${g.gap_min}` : '')
          return [[i, j], [j, i]].map(([r, c2]) => (
            <rect key={`${k}-${r}-${c2}`} x={labelW + c2 * cell + 0.5} y={r * cell + 0.5}
                  width={cell - 1} height={cell - 1} className="fill-primary" opacity={isCard ? 0.9 : 0.35}>
              <title>{tip}</title>
            </rect>
          ))
        })}
      </svg>
      <div className="text-[10px] text-muted mt-1">
        진한 칸 = *CONTACT 로 정의된 쌍 · 옅은 칸 = 기하 탐지로만 찾은 쌍 · 행·열은 연결 수 순 · 이름에 올리면 그 파트의 행·열
      </div>
    </div>
  )
}

export function ConnectivityView({ sessionId, fileId, meta }: {
  sessionId: string; fileId: number; meta: ModelMeta
}) {
  const qc = useQueryClient()
  const [err, setErr] = useState<string | null>(null)
  const [hi, setHi] = useState<number | null>(null)
  const [local, setLocal] = useState<ModelMeta | null>(null)
  const [view, setView] = useState<'graph' | 'matrix' | null>(null)
  const mm = local ?? meta

  const detect = useMutation({
    mutationFn: () => extractConnectivity(sessionId, fileId, true),
    onSuccess: (m) => { setErr(null); setLocal(m); qc.invalidateQueries({ queryKey: ['session', sessionId] }) },
    onError: (e) => setErr(errorMessage(e)),
  })

  if (mm.error) return <div className="text-xs text-danger">connectivity 오류: {mm.error}</div>

  const c = mm.connectivity
  const parts = mm.parts.map((p) => ({ pid: p.pid, title: p.title }))
  // 카드 엣지 + (있으면) 기하 엣지를 합쳐 그린다.
  const edges: ModelEdge[] = [...(c.contact_edges || []), ...(c.geometric_edges || [])]
  const ss = c.single_surface || []
  // 엣지가 많으면 원형 현 그림은 읽히지 않는다 — 행렬을 기본으로(사람이 바꿀 수 있다)
  const shown = view ?? (edges.length > 150 ? 'matrix' : 'graph')
  const unresolved = c.unresolved_detail || []

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <Network size={13} className="text-primary" />
        <span>접촉 {c.contacts_total ?? 0} · 파트쌍 엣지 {c.contact_edges?.length ?? 0}
          {c.geometric_edges ? ` · 기하 ${c.geometric_edges.length}` : ''}
          {ss.length ? ` · 자기접촉 ${ss.length}` : ''}</span>
        <div className="flex-1" />
        {!mm.detect && (
          <Button size="sm" variant="ghost" onClick={() => detect.mutate()} disabled={detect.isPending}
            title="*CONTACT 만으로 파트쌍이 안 나오는 모델(자기접촉 등)에서 기하학적으로 닿는 파트쌍을 찾습니다 (수십 초 소요)">
            {detect.isPending ? <Spinner /> : <Sparkles size={13} />} 기하 탐지
          </Button>
        )}
      </div>
      {err && <div className="text-xs text-danger">{err}</div>}
      {/* ★못 푼 접촉 면 — 그 면의 파트쌍은 그림에 없다. 개수만 내면 「무엇이 왜」 를 모른다. */}
      {(c.unresolved_sides ?? 0) > 0 && (
        <div className="text-[11px] rounded border border-border p-2 space-y-0.5">
          <div style={{ color: '#a33' }}>
            ⚠ 못 푼 접촉 면 {c.unresolved_sides} — 그 면의 파트쌍은 연결도에 없다
          </div>
          {unresolved.slice(0, 8).map((u, i) => (
            <div key={i} className="text-muted">
              접촉 #{u.contact}{u.cid != null ? ` (CID ${u.cid})` : ''}{u.title ? ` ${u.title}` : ''} · {u.side === 'slave' ? '슬레이브' : '마스터'} SID {u.sid}
              (STYP={u.styp}) — {u.why}
            </div>
          ))}
          {unresolved.length > 8 && <div className="text-muted">… 외 {unresolved.length - 8}</div>}
        </div>
      )}

      {edges.length > 0 && (
        <div className="flex items-center gap-1 text-[10px]">
          {(['graph', 'matrix'] as const).map((v) => (
            <button key={v} onClick={() => setView(v)}
                    className={`px-1.5 py-0.5 rounded ${shown === v ? 'bg-primary text-primary-fg' : 'text-muted hover:text-fg'}`}>
              {v === 'graph' ? '원형 그래프' : '인접 행렬'}
            </button>
          ))}
          {edges.length > 150 && view === null && <span className="text-muted">엣지 {edges.length} — 행렬로 보였다</span>}
        </div>
      )}
      {edges.length > 0 ? (
        shown === 'matrix' ? (
          <Matrix parts={parts} cardEdges={c.contact_edges || []} geoEdges={c.geometric_edges || []}
                  highlight={hi} onHover={setHi} />
        ) : (
          <div className="text-current" style={{ lineHeight: 0 }}>
            <Graph parts={parts} edges={edges} highlight={hi} />
          </div>
        )
      ) : (
        <div className="text-xs text-muted rounded border border-border p-3">
          카드 기반 파트쌍 엣지가 없습니다.
          {ss.length
            ? ` 이 모델은 자기접촉(SINGLE_SURFACE, ${ss[0]?.pids?.length ?? 0}개 파트 범위)이라 '기하 탐지'로 실제 접촉쌍을 뽑을 수 있습니다.`
            : ''}
        </div>
      )}

      {/* 파트 메트릭 표 */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-muted">
            <tr className="text-left border-b border-border">
              <th className="py-1 pr-2">파트</th>
              <th className="py-1 pr-2">타입</th>
              <th className="py-1 pr-2 text-right">요소</th>
              <th className="py-1 pr-2 text-right">부피</th>
              <th className="py-1 pr-2 text-right">표면적</th>
              <th className="py-1 pr-2">재료</th>
            </tr>
          </thead>
          <tbody>
            {mm.parts.map((p) => {
              const mat = p.material?.db?.name || p.material?.kfile?.name || `MID ${p.material?.mid}`
              return (
                <tr key={p.pid}
                  className={`border-b border-border/50 cursor-pointer ${hi === p.pid ? 'bg-bg' : ''}`}
                  onMouseEnter={() => setHi(p.pid)} onMouseLeave={() => setHi(null)}>
                  <td className="py-1 pr-2 truncate max-w-[160px]" title={p.title}>{p.title || `PID ${p.pid}`}</td>
                  <td className="py-1 pr-2 text-muted">{p.elem_class}</td>
                  <td className="py-1 pr-2 text-right mono">{p.n_elems}</td>
                  <td className="py-1 pr-2 text-right mono">{p.volume ? p.volume.toPrecision(3) : '–'}</td>
                  <td className="py-1 pr-2 text-right mono">{p.area_ext ? p.area_ext.toPrecision(3) : '–'}</td>
                  <td className="py-1 pr-2 text-muted truncate max-w-[140px]" title={mat}>{mat}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
