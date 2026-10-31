// 리포트 케이스의 identity(각도 · 충격 위치)를 사람이 읽는 이름으로 — 케이스 표와 해석 온톨로지 칸이 같이 쓴다

/** 전각도 낙하는 각도 이름, 부분충격은 위치(pos_id, 없으면 면) — 둘 다 없으면 fallback(보통 case_key). */
export function identityLabel(identity: unknown, fallback: string): string {
  const id = (identity ?? {}) as { angle?: { name?: string }; face?: string; pos_id?: string }
  if (id.angle?.name) return id.angle.name
  if (id.face || id.pos_id) return id.pos_id ?? id.face ?? fallback
  return fallback
}
