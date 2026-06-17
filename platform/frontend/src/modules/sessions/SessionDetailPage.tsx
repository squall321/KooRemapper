import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Play, Wand2 } from 'lucide-react'
import { createJob, getOperation, getSession, listOperations } from '@/shared/api/endpoints'
import type { OperationDetail } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, Select, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { errorMessage } from '@/shared/api/client'
import { FilePanel } from './FilePanel'
import { JobPanel } from './JobPanel'
import { SchemaForm, type ArgValues } from './SchemaForm'

const CAT_LABEL: Record<string, string> = {
  core: '코어', deform: '변형', mesh: '메쉬', material: '재료', analysis: '해석', bc: '하중/경계', model: '모델',
}

export function SessionDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const session = useQuery({ queryKey: ['session', id], queryFn: () => getSession(id) })
  const ops = useQuery({ queryKey: ['operations'], queryFn: listOperations })

  const [opName, setOpName] = useState('')
  const opDetail = useQuery<OperationDetail>({
    queryKey: ['operation', opName], queryFn: () => getOperation(opName), enabled: !!opName,
  })
  const [args, setArgs] = useState<ArgValues>({})
  const [err, setErr] = useState<string | null>(null)

  const run = useMutation({
    mutationFn: () => createJob(id, opName, args),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['jobs', id] }) },
    onError: (e) => setErr(errorMessage(e)),
  })

  const grouped = useMemo(() => {
    const by: Record<string, typeof ops.data> = {}
    for (const o of ops.data ?? []) (by[o.category] ??= []).push(o)
    return by
  }, [ops.data])

  function selectOp(name: string) {
    setOpName(name)
    setArgs({})
    setErr(null)
  }
  function fillExample() {
    if (opDetail.data) setArgs(opDetail.data.example.args as ArgValues)
  }

  if (session.isLoading) return <div className="p-10 text-center"><Spinner /></div>
  if (!session.data) return <div className="text-muted">세션을 찾을 수 없습니다.</div>

  const files = session.data.files ?? []

  return (
    <div>
      <Link to="/sessions" className="text-xs text-muted flex items-center gap-1 mb-2"><ArrowLeft size={12} /> 세션 목록</Link>
      <PageHeader title={session.data.name} desc={session.data.description ?? `${files.length}개 파일`} />

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="space-y-4">
          <FilePanel sessionId={id} files={files} />
          <JobPanel sessionId={id} />
        </div>

        <Card className="self-start">
          <CardHeader className="font-medium text-sm flex items-center gap-2"><Wand2 size={14} className="text-primary" /> 오퍼레이션 실행</CardHeader>
          <CardBody className="space-y-3">
            <Select value={opName} onChange={(e) => selectOp(e.target.value)}>
              <option value="">오퍼레이션 선택…</option>
              {Object.entries(grouped).map(([cat, list]) => (
                <optgroup key={cat} label={CAT_LABEL[cat] ?? cat}>
                  {list!.map((o) => <option key={o.name} value={o.name}>{o.name} — {o.summary}</option>)}
                </optgroup>
              ))}
            </Select>

            {opName && opDetail.isLoading && <Spinner />}
            {opDetail.data && (
              <>
                <div className="flex items-center gap-2 text-xs text-muted">
                  <Badge>{opDetail.data.invocation}</Badge>
                  {opDetail.data.config_style && <Badge>{opDetail.data.config_style}</Badge>}
                  {opDetail.data.requires_gmsh && <Badge tone="canceled">gmsh 필요</Badge>}
                  <span className="flex-1" />
                  <Button size="sm" variant="ghost" onClick={fillExample}>예제 채우기</Button>
                </div>
                <p className="text-xs text-muted">{opDetail.data.description}</p>
                <SchemaForm op={opDetail.data} files={files} value={args} onChange={setArgs} />
                {err && <div className="text-xs text-danger whitespace-pre-wrap">{err}</div>}
                <Button variant="primary" className="w-full" onClick={() => run.mutate()} disabled={run.isPending}>
                  <Play size={15} /> {run.isPending ? '제출 중…' : '실행'}
                </Button>
              </>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
