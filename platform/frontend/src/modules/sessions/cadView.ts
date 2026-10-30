// CAD 형상 뷰어의 순수 셈 — glb 노드를 FE 파트에 잇고, 고른 각도의 파트 값을 색 자리(0–1)로 바꾼다
//
// 앱 타입(ReportCadPart)을 가져오지 않고 쓰는 칸만 적는다 — 확인 스크립트가 이 파일만 옮겨 돌린다.

export interface CadPartLike {
  pid: number
  glb: { node: number }
}

/** glb 노드 번호 → 파트(받는 쪽 검사를 통과한 요약의 `glb.node`). 같은 노드가 둘이면 앞의 것. */
export function nodePart<P extends CadPartLike>(parts: P[]): Map<number, P> {
  const m = new Map<number, P>()
  for (const p of parts) if (!m.has(p.glb.node)) m.set(p.glb.node, p)
  return m
}

export interface PartShade {
  value: Map<number, number | null>   // pid → 값(없으면 null — 회색으로 칠한다)
  lo: number
  hi: number
}

/** 고른 각도의 파트별 값(`parts_metrics[pid][metric]`) — 값이 있는 파트만으로 범위를 잡는다. */
export function partShade(parts: CadPartLike[], metrics: Record<string, Record<string, number | null>> | null | undefined,
                          metric: string): PartShade {
  const value = new Map<number, number | null>()
  let lo = Infinity
  let hi = -Infinity
  for (const p of parts) {
    const v = metrics?.[String(p.pid)]?.[metric]
    if (typeof v === 'number' && Number.isFinite(v)) {
      value.set(p.pid, v)
      lo = Math.min(lo, v)
      hi = Math.max(hi, v)
    } else {
      value.set(p.pid, null)
    }
  }
  return lo === Infinity ? { value, lo: 0, hi: 0 } : { value, lo, hi }
}

/** 값 → 0–1. 범위가 0 이면(파트 하나 · 모두 같은 값) 가운데. */
export function shadeOf(v: number, lo: number, hi: number): number {
  return hi > lo ? Math.max(0, Math.min(1, (v - lo) / (hi - lo))) : 0.5
}
