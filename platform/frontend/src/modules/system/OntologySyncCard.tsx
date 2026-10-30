// 허브 받기 관리 카드(관리자) — 지금 받기 · 처음부터 · 강제 정리 · 결과와 확인 필요 사유 · 최근 실행 · 타입별 건수 · 합친 과제 옮기기
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, GitMerge, RefreshCw } from 'lucide-react'

import {
  mergedTasks, moveMergedTask, ontologySync, ontologySyncRuns, runOntologySync, type SyncRun,
} from '@/shared/api/endpoints'
import { errorMessage } from '@/shared/api/client'
import { Badge, Button, Card, CardBody, CardHeader, Spinner } from '@/shared/ui/ui'

const RESULT: Record<SyncRun['result'], { tone: string; label: string }> = {
  ok: { tone: 'succeeded', label: '정상' },
  needs_check: { tone: 'canceled', label: '확인 필요' },
  failed: { tone: 'failed', label: '실패' },
  running: { tone: 'running', label: '받는 중' },
}

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : '—')

/** 「절반 넘게 안 옴」 으로 정리를 멈췄나 — 강제 정리는 그때만 연다(키트 §7: 사람이 확인한 뒤에만). */
function heldBack(run: SyncRun | null): boolean {
  if (!run) return false
  const all = [...Object.values(run.counts?.types ?? {}), ...Object.values(run.counts?.relations ?? {})]
  return all.some((c) => (c?.held_back ?? 0) > 0)
}

/** SP 키트 2026-10-21 §7 의 관리 화면. 받기 실행은 MCP 에 없다 — 전사 데이터를 움직이는 길은 시스템 관리자다. */
export function OntologySyncCard() {
  const qc = useQueryClient()
  const [err, setErr] = useState<string | null>(null)
  const [showRuns, setShowRuns] = useState(false)
  const state = useQuery({ queryKey: ['ontology-sync'], queryFn: ontologySync, refetchInterval: 15_000 })
  const runs = useQuery({ queryKey: ['ontology-sync-runs'], queryFn: () => ontologySyncRuns(10), enabled: showRuns })
  const merged = useQuery({ queryKey: ['ontology-merged'], queryFn: mergedTasks })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['ontology-sync'] })
    qc.invalidateQueries({ queryKey: ['ontology-sync-runs'] })
    qc.invalidateQueries({ queryKey: ['ontology-merged'] })
  }
  const run = useMutation({
    mutationFn: (o: { full?: boolean; allowShrink?: boolean }) => runOntologySync(o),
    onSuccess: () => { setErr(null); refresh() },
    onError: (e) => { setErr(errorMessage(e)); refresh() },
  })
  const move = useMutation({
    mutationFn: (key: string) => moveMergedTask(key),
    onSuccess: () => { setErr(null); refresh(); qc.invalidateQueries({ queryKey: ['report-revision'] }) },
    onError: (e) => setErr(errorMessage(e)),
  })

  const s = state.data
  const last = s?.last_run ?? null
  const busy = run.isPending || move.isPending

  return (
    <Card className="mb-6">
      <CardHeader className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-medium text-sm">허브 받기 (관리자)</span>
        <span className="flex items-center gap-2 text-xs text-muted">
          {last && <Badge tone={RESULT[last.result].tone}>{RESULT[last.result].label}</Badge>}
          {s?.catalog && <span>정의 판 <span className="mono">{s.catalog.revision}</span></span>}
          {s?.catalog?.system && <span>· {s.catalog.system}</span>}
        </span>
      </CardHeader>
      <CardBody className="space-y-4 text-sm">
        {state.isLoading ? <Spinner /> : state.isError ? (
          <div className="text-danger">받기 상태를 읽지 못했다 — {errorMessage(state.error)}</div>
        ) : s && (
          <>
            {!s.enabled && (
              <div className="text-warning">
                허브 주소 · 토큰이 없어 받기가 꺼져 있다 — <span className="mono">KOORM_SP_CORE_URL</span> ·{' '}
                <span className="mono">KOORM_SP_CORE_TOKEN</span> 을 넣으면 시간마다 받고 {s.full_every_days}일마다 처음부터 받는다
              </div>
            )}

            <div className="flex items-center gap-2 flex-wrap">
              <Button size="sm" variant="primary" disabled={!s.enabled || busy} onClick={() => run.mutate({})}>
                {run.isPending ? <Spinner /> : <><RefreshCw size={13} /> 지금 받기</>}
              </Button>
              <Button size="sm" disabled={!s.enabled || busy} onClick={() => {
                if (window.confirm('처음부터 다시 받습니다. 허브에서 안 온 것은 「사용 안 함」 으로 바뀝니다(지우지는 않는다). 계속할까요?')) run.mutate({ full: true })
              }}>처음부터 다시 받기</Button>
              {heldBack(last) && (
                <Button size="sm" variant="danger" disabled={!s.enabled || busy} onClick={() => {
                  if (window.confirm('절반 넘게 안 온 것을 정말 「사용 안 함」 으로 바꿉니다. 토큰의 부서 · 공개 범위가 줄어든 것이 아님을 허브에 확인했나요?')) run.mutate({ full: true, allowShrink: true })
                }}>강제 정리</Button>
              )}
              {/* 실행 기록에 남은 실패는 아래 「마지막 실행」 이 말한다 — 기록이 없는 거절(받는 중 · 꺼짐)만 여기 */}
              {err && err !== last?.error && <span className="text-danger text-xs">{err}</span>}
            </div>

            {last && (
              <div className="space-y-1 text-xs">
                <div className="text-muted">
                  마지막 실행 {when(last.finished_at ?? last.started_at)} · {last.mode === 'full' ? '처음부터' : '증분'}
                  {last.allow_shrink && ' · 강제 정리'} · {last.trigger === 'admin' ? '관리자' : '주기'}
                </div>
                {!!last.problems.length && (
                  <div className="rounded border border-warning/50 bg-warning/5 px-2 py-1.5 space-y-0.5">
                    <div className="flex items-center gap-1 text-warning"><AlertTriangle size={12} /> 확인 필요</div>
                    {last.problems.map((p, i) => <div key={i} className="text-fg">{p}</div>)}
                  </div>
                )}
                {last.error && <div className="text-danger">{last.error}</div>}
                {!!last.notes.length && (
                  <ul className="text-muted list-disc pl-4">{last.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                )}
              </div>
            )}

            {/* 타입별 건수 — 사라진 것도 지우지 않았으므로 「사용 안 함」 으로 센다 */}
            {!!s.types.length && (
              <div className="overflow-x-auto">
                <table className="text-xs w-full">
                  <thead className="text-muted">
                    <tr className="text-left">
                      <th className="pr-3 font-medium">타입</th>
                      <th className="pr-3 font-medium text-right">활성</th>
                      <th className="pr-3 font-medium text-right">그만 씀</th>
                      <th className="pr-3 font-medium text-right">사용 안 함</th>
                      <th className="pr-3 font-medium">상태</th>
                      <th className="pr-3 font-medium">기준 시각</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.types.map((t) => {
                      const c = s.object_states[t.type_slug]
                      return (
                        <tr key={t.type_slug} className="border-t border-border">
                          <td className="pr-3 py-1 mono">{t.type_slug}</td>
                          <td className="pr-3 text-right mono">{c?.active ?? 0}</td>
                          <td className="pr-3 text-right mono">{c?.deprecated ?? 0}</td>
                          <td className="pr-3 text-right mono">{c?.inactive ?? 0}</td>
                          <td className="pr-3">
                            {t.last_status === 'skipped' ? <span className="text-warning" title={t.last_error ?? ''}>공개 안 됨</span>
                              : t.last_status === 'error' ? <span className="text-danger" title={t.last_error ?? ''}>오류</span>
                              : t.last_status ?? '—'}
                          </td>
                          <td className="pr-3 mono text-muted">{t.objects_as_of ?? '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* 합쳐진 과제 — 저절로 옮기지 않는다(사용자 결정 10-30). 누르면 우리 개정 · 별칭을 합쳐진 곳으로 */}
            {!!merged.data?.length && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1 text-xs text-warning">
                  <GitMerge size={12} /> 허브에서 합쳐진 과제 {merged.data.length}건 — 우리 개정이 아직 진 쪽에 있다
                </div>
                {merged.data.map((m) => (
                  <div key={m.key} className="flex items-center gap-2 flex-wrap text-xs">
                    <b className="mono">{m.key}</b>
                    <span className="text-muted">→</span>
                    <b className="mono">{m.into}</b>
                    {m.into_label && <span className="text-muted">({m.into_label})</span>}
                    <span className="text-muted">· 개정 {m.revisions.length} · 리포트 {m.reports} · 별칭 {m.aliases}</span>
                    {m.into_active ? (
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => {
                        if (window.confirm(`${m.key} 의 개정 ${m.revisions.length}개 · 별칭 ${m.aliases}개를 ${m.into} 로 옮깁니다.`)) move.mutate(m.key)
                      }}>{m.into} 로 옮기기</Button>
                    ) : <span className="text-danger">합쳐진 곳도 사라졌다 — 옮길 곳이 없다</span>}
                  </div>
                ))}
              </div>
            )}

            <div>
              <button type="button" className="text-xs text-muted hover:text-fg" onClick={() => setShowRuns((v) => !v)}>
                {showRuns ? '▾' : '▸'} 최근 실행
              </button>
              {showRuns && (runs.isLoading ? <Spinner /> : (
                <table className="mt-1 text-xs w-full">
                  <tbody>
                    {(runs.data ?? []).map((r) => (
                      <tr key={r.id} className="border-t border-border align-top">
                        <td className="pr-3 py-1 text-muted whitespace-nowrap">{when(r.started_at)}</td>
                        <td className="pr-3">{r.mode === 'full' ? '처음부터' : '증분'}{r.allow_shrink ? ' · 강제' : ''}</td>
                        <td className="pr-3 text-muted">{r.trigger === 'admin' ? r.requested_by || '관리자' : '주기'}</td>
                        <td className="pr-3"><Badge tone={RESULT[r.result].tone}>{RESULT[r.result].label}</Badge></td>
                        <td className="text-muted">{r.problems.length ? `사유 ${r.problems.length}` : ''}{r.error ? ` ${r.error}` : ''}</td>
                      </tr>
                    ))}
                    {!runs.data?.length && <tr><td className="py-1 text-muted">아직 실행이 없다</td></tr>}
                  </tbody>
                </table>
              ))}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}
