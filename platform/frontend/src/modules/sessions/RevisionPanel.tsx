// 리포트가 어느 과제의 어느 **개발 개정**인가 — 어긋남을 보여 주고 사람이 확정한다
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, GitBranch, Unlink } from 'lucide-react'

import {
  compareTaskRevisions, ontologyState, reportRevision, setReportRevision,
  unlinkReportRevision, type RevisionCandidate,
} from '@/shared/api/endpoints'
import { Badge, Button, Input, Spinner } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'

/** 개정 패널.
 *
 *  ★**이 패널이 없으면 설계가 사라진다.** 서버는 `eng_meta` 와 이어진 개정이 다를 때
 *  조용히 맞추지 않고 `mismatch` 로 말한다 — 그 말을 받아 보여 주는 자리가 화면이다.
 *  보여 주지 않으면 서버가 "말했다" 는 사실에 아무 의미가 없다.
 *
 *  그리고 **후보를 고르지 않는다.** 근거를 함께 띄우고 사람이 누른다 — 짐작으로 붙이면
 *  틀려도 그럴듯하고, 그럴듯한 오류는 몇 달 뒤 결과를 비교할 때 발견된다.
 */
export function RevisionPanel({ reportId }: { reportId: string }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [task, setTask] = useState('')
  const [code, setCode] = useState('')
  const [err, setErr] = useState<string | null>(null)

  // ★기능이 꺼져 있으면 **없어진다**(포탈 옵션이 정한다). 상태는 한 번만 받아 공유한다.
  const feat = useQuery({ queryKey: ['ontology-state'], queryFn: ontologyState, staleTime: 60_000 })
  const on = feat.data?.enabled === true

  const info = useQuery({
    queryKey: ['report-revision', reportId],
    queryFn: () => reportRevision(reportId),
    enabled: on,        // 꺼져 있으면 **부르지도 않는다** — 409 를 받아 숨기는 것과 다르다
  })

  const drop = useMutation({
    mutationFn: () => unlinkReportRevision(reportId),
    onSuccess: () => {
      setErr(null)
      qc.invalidateQueries({ queryKey: ['report-revision', reportId] })
      qc.invalidateQueries({ queryKey: ['task-revisions'] })
    },
    onError: (e) => setErr(errorMessage(e)),
  })

  const save = useMutation({
    mutationFn: () => setReportRevision(reportId, { task_key: task.trim(), code: code.trim() }),
    onSuccess: () => {
      setErr(null)
      setOpen(false)
      qc.invalidateQueries({ queryKey: ['report-revision', reportId] })
      qc.invalidateQueries({ queryKey: ['task-revisions'] })
    },
    onError: (e) => setErr(errorMessage(e)),
  })

  if (feat.isLoading) return null
  if (!on) return null          // 꺼짐 — 조용히 없어진다(그것이 「없어져야」의 뜻이다)
  if (info.isLoading) return <div className="text-xs text-muted"><Spinner /> 개정 확인…</div>
  // ★꺼짐과 **고장**을 같은 모양으로 만들지 않는다. 기능이 켜져 있는데 못 읽었으면
  //   사라지지 않고 **말한다** — 조용히 사라지면 "왜 안 보이나" 를 아무 데서도 알 수 없다.
  if (info.isError) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-danger">
        <AlertTriangle size={13} /> 개정을 읽지 못했다 — {errorMessage(info.error)}
      </div>
    )
  }
  if (!info.data) return null
  const d = info.data

  const start = (c?: RevisionCandidate) => {
    setTask(d.resolved_task ?? d.free_task ?? '')
    setCode(c?.code ?? d.mismatch?.linked?.split('@')[1] ?? '')
    setErr(null)
    setOpen(true)
  }

  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2 flex-wrap">
        <GitBranch size={13} className="text-muted" />
        <span className="text-muted">개정</span>
        {d.mismatch ? (
          <b className="text-fg">{d.mismatch.linked}</b>
        ) : d.resolved_task ? (
          <span className="text-muted">
            과제 <b className="text-fg">{d.resolved_task}</b>
            <span className="ml-1 text-muted">({d.resolved_how === 'alias' ? '별칭' : '코드 일치'})</span>
          </span>
        ) : d.free_task ? (
          // 자유 문자열만 있다 — **붙이지 않았다**고 말한다(붙은 것처럼 보이면 안 된다)
          <span className="text-muted">「{d.free_task}」 — <span className="text-warning">정본 과제에 아직 안 붙었다</span></span>
        ) : (
          <span className="text-muted">과제 메타가 없다</span>
        )}
        {!open && (
          <Button size="sm" variant="ghost" onClick={() => start()}>
            {d.mismatch ? '다시 확정' : '확정'}
          </Button>
        )}
        {/* ★확정하는 기능에 되돌리는 길이 없으면 반쪽이다. 개정 **객체는 남는다** —
            그 판에 다른 리포트가 달려 있을 수 있다. */}
        {!open && d.mismatch && (
          <Button size="sm" variant="ghost" onClick={() => drop.mutate()} disabled={drop.isPending}>
            {drop.isPending ? <Spinner /> : <><Unlink size={13} /> 연결 끊기</>}
          </Button>
        )}
      </div>

      {/* ★어긋남 — 서버가 조용히 맞추지 않은 것을 사람이 보는 자리 */}
      {d.mismatch && (
        <div className="flex items-start gap-2 rounded border border-danger/50 bg-danger/5 px-2 py-1.5">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-danger" />
          <div className="space-y-0.5">
            <div className="text-danger">{d.mismatch.said}</div>
            <div className="text-muted">
              이어진 것 <b className="text-fg">{d.mismatch.linked}</b>
              {d.mismatch.eng_meta && <> · 수동 메타 <b className="text-fg">{d.mismatch.eng_meta}</b></>}
            </div>
          </div>
        </div>
      )}

      {/* 후보 — 근거와 함께. 서버가 고르지 않았으므로 화면도 고르지 않는다 */}
      {!!d.candidates.length && (
        <div className="space-y-1">
          <div className="text-muted">개정 후보 — 근거를 보고 고른다</div>
          {d.candidates.map((c) => (
            <div key={`${c.source}:${c.code}`} className="flex items-center gap-2 flex-wrap">
              <Badge tone={c.valid ? 'default' : 'canceled'}>{c.code}</Badge>
              <span className="text-muted">{c.evidence}</span>
              {c.valid ? (
                <Button size="sm" variant="ghost" onClick={() => start(c)}>이것으로</Button>
              ) : (
                // ★형식이 아닌 것도 **버리지 않고** 보여 준다 — 사람이 고칠 수 있어야 한다
                <span className="text-warning">쓸 수 없다 — {c.why}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 과제 후보 — 자유 문자열이 정본에 안 붙었을 때 */}
      {!!d.task_candidates.length && (
        <div className="space-y-1">
          <div className="text-muted">과제 후보 — 관리자가 별칭을 적으면 다음부터 자동으로 붙는다</div>
          {d.task_candidates.map((t) => (
            <div key={t.key} className="flex items-center gap-2 flex-wrap">
              <b className="text-fg">{t.key}</b>
              <span className="text-muted">{t.label} — {t.why}</span>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="flex items-center gap-2 flex-wrap rounded border border-border px-2 py-1.5">
          <Input value={task} onChange={(e) => setTask(e.target.value)}
                 placeholder="과제코드" className="w-40 text-xs" />
          <Input value={code} onChange={(e) => setCode(e.target.value)}
                 placeholder="dv1 · pv2 · pre · mp" className="w-32 text-xs" />
          <Button size="sm" variant="primary" disabled={!task.trim() || !code.trim() || save.isPending}
                  onClick={() => save.mutate()}>
            {save.isPending ? <Spinner /> : <><Check size={13} /> 확정</>}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>취소</Button>
          <span className="text-muted">확정하면 재인제스트에도 지워지지 않는다</span>
          {err && <span className="text-danger">{err}</span>}
        </div>
      )}

      {d.resolved_task && <Chain taskKey={d.resolved_task} here={reportId} />}
    </div>
  )
}

/** 같은 과제의 개정 줄 — 어느 판에 결과가 몇 건 달렸는지. 판끼리 견주려면 여기서 고른다. */
function Chain({ taskKey, here }: { taskKey: string; here: string }) {
  const line = useQuery({
    queryKey: ['task-revisions', taskKey],
    queryFn: () => compareTaskRevisions(taskKey),
  })
  if (line.isLoading || !line.data || line.data.revisions.length === 0) return null
  return (
    <div className="space-y-1">
      <div className="text-muted">이 과제의 개정 줄 — 판끼리 견준다</div>
      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead className="text-muted">
            <tr>
              <th className="pr-3 text-left">판</th>
              <th className="pr-3 text-right">최악 응력</th>
              <th className="pr-3 text-right">앞 판 대비</th>
              <th className="pr-3 text-right">최악 G</th>
              <th className="pr-3 text-left">심각도</th>
              <th className="pr-3 text-right">케이스</th>
              <th className="pr-3 text-right">리포트</th>
            </tr>
          </thead>
          <tbody>
            {line.data.revisions.map((r) => {
              const mine = r.reports.includes(here)
              return (
                <tr key={r.key} className={mine ? 'text-accent' : 'text-muted'}>
                  <td className="pr-3 py-0.5">
                    {r.code}
                    {r.rev_source === 'manual' && <span className="ml-1" title="사람이 확정">✓</span>}
                    {mine && <span className="ml-1" title="이 리포트">◂</span>}
                  </td>
                  {/* ★`null` 을 0 으로 그리지 않는다 — 0 은 「쟀는데 0」 으로 읽힌다 */}
                  <td className="pr-3 text-right mono">{r.worst_stress ?? '—'}</td>
                  <td className={`pr-3 text-right mono ${
                    r.d_worst_stress == null ? '' : r.d_worst_stress > 0 ? 'text-danger' : 'text-success'}`}>
                    {r.d_worst_stress == null ? '—'
                      : `${r.d_worst_stress > 0 ? '+' : ''}${r.d_worst_stress}`}
                  </td>
                  <td className="pr-3 text-right mono">{r.worst_g ?? '—'}</td>
                  <td className="pr-3">{r.max_severity ?? '—'}</td>
                  <td className="pr-3 text-right mono">{r.n_cases || '—'}</td>
                  <td className="pr-3 text-right mono" title={`최악값을 ${r.measured_from}건에서 모았다`}>
                    {r.n_reports}
                    {r.measured_from !== r.n_reports && <span className="text-warning"> (읽은 것 {r.measured_from})</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
