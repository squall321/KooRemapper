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

export function ConnectivityView({ sessionId, fileId, meta }: {
  sessionId: string; fileId: number; meta: ModelMeta
}) {
  const qc = useQueryClient()
  const [err, setErr] = useState<string | null>(null)
  const [hi, setHi] = useState<number | null>(null)
  const [local, setLocal] = useState<ModelMeta | null>(null)
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

      {edges.length > 0 ? (
        <div className="text-current" style={{ lineHeight: 0 }}>
          <Graph parts={parts} edges={edges} highlight={hi} />
        </div>
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
