// 세션의 허브 과제 · 개발 단계를 보고 고치는 칸 — 자동 파이프라인이 이 세션의 과제 · 차수로 읽는다(KR-AP1)
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Workflow } from 'lucide-react'
import { updateSession } from '@/shared/api/endpoints'
import { errorMessage } from '@/shared/api/client'
import type { SessionSummary } from '@/shared/api/types'
import { Button, Card, CardBody, CardHeader, Input, Spinner } from '@/shared/ui/ui'

// 과제 칸은 과제명 · 과제코드 · 옛 과제명 · 별칭 무엇이든 — 서버가 판 확정과 같은 규칙으로 풀어 과제명을 남기고 못 풀면 후보와 함께
// 거절한다. 개발 단계는 pre · dv1 … · pv1 … · pra · mp. 비우고 저장하면 지운다(자동 파이프라인은 그 세션을 막힘으로 세운다).
export function SessionSubjectPanel({ session }: { session: SessionSummary }) {
  const qc = useQueryClient()
  const [task, setTask] = useState(session.task_key ?? '')
  const [rev, setRev] = useState(session.dev_rev ?? '')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setTask(session.task_key ?? ''); setRev(session.dev_rev ?? '') }, [session.task_key, session.dev_rev])

  const save = useMutation({
    mutationFn: () => updateSession(session.id, { task_key: task.trim() || null, dev_rev: rev.trim() || null }),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['session', session.id] }) },
    onError: (e) => setErr(errorMessage(e)),
  })
  const empty = !session.task_key || !session.dev_rev

  return (
    <Card>
      <CardHeader className="font-medium text-sm flex items-center gap-2">
        <Workflow size={14} className="text-primary" /> 허브 과제 · 개발 단계
      </CardHeader>
      <CardBody className="space-y-2 text-xs">
        <div className="text-muted">
          {empty
            ? '비어 있으면 자동 파이프라인이 이 세션을 「과제 · 단계 없음」 으로 막는다.'
            : `과제 ${session.task_key} · 단계 ${session.dev_rev}`}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Input value={task} onChange={(e) => setTask(e.target.value)} placeholder="과제명 · 과제코드" className="w-48 text-xs" />
          <Input value={rev} onChange={(e) => setRev(e.target.value)} placeholder="dv1 · pv2 · pre · mp" className="w-32 text-xs" />
          <Button size="sm" variant="primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? <Spinner /> : <><Check size={13} /> 저장</>}
          </Button>
        </div>
        {err && <div className="text-danger">{err}</div>}
      </CardBody>
    </Card>
  )
}
