// 구면 위험도 맵의 셈 — 방향 벡터 · 대원 역거리 가중 보간 · 허용비 판정 · 상위 N(화면과 떼어 시험한다)
//
// ⚠ 보간은 **표본 사이의 추정**이다. 판정 · 순위 · 최악은 표본 값으로만 한다(지어내지 않는다).
// 계획 docs/01-plan/features/sphere-risk-map-1029.plan.md

export type Vec3 = [number, number, number]

export interface Sample {
  key: string     // case_key
  name: string    // 각도 이름(없으면 case_key)
  lon: number     // 도
  lat: number     // 도
  value: number   // 표본 값(정본)
}

export type Level = 'exceed' | 'warn' | 'ok'

/** 경도 · 위도(도) → 단위 방향 벡터. 백엔드 `_angle_vec` · sphere 리포트와 같은 틀 — 위도 90° = +Z, 경도 90° = +Y. */
export function dirOf(lon: number, lat: number): Vec3 {
  const la = (Math.max(-90, Math.min(90, lat)) * Math.PI) / 180
  const lo = (lon * Math.PI) / 180
  return [Math.cos(la) * Math.cos(lo), Math.cos(la) * Math.sin(lo), Math.sin(la)]
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

export interface Field {
  dirs: Vec3[]
  values: number[]
}

/** 표본 → 보간용 장. 같은 방향(벡터를 1e-9 로 반올림해 같으면)의 표본은 하나로 모으고 **큰 값**을 둔다 —
 *  위험도 맵은 보수적으로 그린다(섭동 DOE 처럼 한 방향에 표본이 여럿일 수 있다). 극점 · ±180° 경도도 한 방향이 된다. */
export function makeField(samples: Sample[]): Field {
  const byDir = new Map<string, { d: Vec3; v: number }>()
  for (const s of samples) {
    if (!Number.isFinite(s.value)) continue
    const d = dirOf(s.lon, s.lat)
    const k = d.map((c) => Math.round(c * 1e9)).join(',')
    const hit = byDir.get(k)
    if (!hit || s.value > hit.v) byDir.set(k, { d, v: s.value })
  }
  const items = [...byDir.values()]
  return { dirs: items.map((i) => i.d), values: items.map((i) => i.v) }
}

/** 방향 하나의 보간 값 — 가까운 `k` 개 표본에 대원 거리의 `p` 제곱 역수로 가중 평균한다.
 *  표본 자리(각 1e-6 rad 안)면 그 표본 값 그대로. 가중 평균이라 표본 범위를 넘지 않는다. 표본이 없으면 NaN. */
export function interpolate(field: Field, d: Vec3, k = 6, p = 2): number {
  const n = field.dirs.length
  if (n === 0) return NaN
  const kk = Math.min(k, n)
  const bestDot: number[] = []
  const bestIdx: number[] = []
  for (let i = 0; i < n; i++) {
    const c = dot(field.dirs[i], d)
    if (bestDot.length < kk || c > bestDot[bestDot.length - 1]) {
      let j = bestDot.length < kk ? bestDot.length : kk - 1
      while (j > 0 && bestDot[j - 1] < c) {
        bestDot[j] = bestDot[j - 1]
        bestIdx[j] = bestIdx[j - 1]
        j--
      }
      bestDot[j] = c
      bestIdx[j] = i
    }
  }
  const nearest = Math.acos(Math.max(-1, Math.min(1, bestDot[0])))
  if (nearest < 1e-6) return field.values[bestIdx[0]]
  let wsum = 0
  let vsum = 0
  for (let j = 0; j < bestDot.length; j++) {
    const ang = Math.acos(Math.max(-1, Math.min(1, bestDot[j])))
    const w = 1 / Math.pow(ang, p)
    wsum += w
    vsum += w * field.values[bestIdx[j]]
  }
  return vsum / wsum
}

/** 등장방형 격자(위도 90° → -90° 행, 경도 -180° → 180° 열, 칸 가운데)의 보간 값. */
export function lonLatGrid(field: Field, stepDeg: number): { w: number; h: number; values: Float64Array } {
  const w = Math.round(360 / stepDeg)
  const h = Math.round(180 / stepDeg)
  const values = new Float64Array(w * h)
  for (let r = 0; r < h; r++) {
    const lat = 90 - (r + 0.5) * stepDeg
    for (let c = 0; c < w; c++) {
      const lon = -180 + (c + 0.5) * stepDeg
      values[r * w + c] = interpolate(field, dirOf(lon, lat))
    }
  }
  return { w, h, values }
}

/** 허용비 = 값 ÷ 허용값. 허용값이 없거나 0 이하 · 유한하지 않으면 null(비율을 지어내지 않는다). */
export function ratioOf(value: number, allowable: number | null | undefined): number | null {
  if (allowable == null || !Number.isFinite(allowable) || allowable <= 0 || !Number.isFinite(value)) return null
  return value / allowable
}

/** 판정 — 허용비 ≥ 1 초과 · ≥ 경고 비율 경고 · 그 밖 정상. 비율이 없으면 null. */
export function levelOf(ratio: number | null, warnRatio: number): Level | null {
  if (ratio == null) return null
  if (ratio >= 1) return 'exceed'
  if (ratio >= warnRatio) return 'warn'
  return 'ok'
}

/** 표본 값이 큰 순서 n 개(같으면 이름 순). 보간 값은 쓰지 않는다. */
export function topN(samples: Sample[], n: number): Sample[] {
  return samples
    .filter((s) => Number.isFinite(s.value))
    .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name))
    .slice(0, Math.max(0, n))
}
