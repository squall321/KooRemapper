// 리포트가 어느 과제의 어느 **개발 개정**인가 — 어긋남을 보여 주고 사람이 확정한다
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, GitBranch } from 'lucide-react'

import {
  reportRevision, setReportRevision, taskRevisions,
  type RevisionCandidate,
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

  const info = useQuery({
    queryKey: ['report-revision', reportId],
    queryFn: () => reportRevision(reportId),
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

  if (info.isLoading) return <div className="text-xs text-muted"><Spinner /> 개정 확인…</div>
  if (info.isError || !info.data) return null
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
    queryFn: () => taskRevisions(taskKey),
  })
  if (line.isLoading || !line.data || line.data.revisions.length === 0) return null
  return (
    <div className="space-y-1">
      <div className="text-muted">이 과제의 개정 줄</div>
      <div className="flex flex-wrap items-center gap-1.5">
        {line.data.revisions.map((r, i) => (
          <span key={r.key} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-muted">→</span>}
            <span className={`rounded px-1.5 py-0.5 border ${
              r.reports.includes(here) ? 'border-accent text-accent' : 'border-border text-muted'}`}>
              {r.code}
              <span className="ml-1 text-muted">{r.reports.length}건</span>
              {r.rev_source === 'manual' && <span className="ml-1" title="사람이 확정">✓</span>}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}
