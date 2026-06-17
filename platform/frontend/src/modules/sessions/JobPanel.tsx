import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText, ScrollText, X, Ban } from 'lucide-react'
import { cancelJob, downloadFile, getJobLogs, getJobOutputs, listSessionJobs } from '@/shared/api/endpoints'
import type { Job } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Spinner } from '@/shared/ui/ui'
import { fmtDate } from '@/shared/lib/cn'

export function JobPanel({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['jobs', sessionId],
    queryFn: () => listSessionJobs(sessionId),
    // poll while any job is active
    refetchInterval: (q) => {
      const jobs = q.state.data as Job[] | undefined
      return jobs?.some((j) => j.status === 'queued' || j.status === 'running') ? 1500 : false
    },
  })
  const [logsFor, setLogsFor] = useState<string | null>(null)

  return (
    <Card>
      <CardHeader className="font-medium text-sm">작업 히스토리</CardHeader>
      <CardBody className="p-0">
        {isLoading ? <div className="p-6 text-center"><Spinner /></div>
          : !data?.length ? <EmptyState title="아직 실행한 작업이 없습니다" />
          : (
            <ul className="divide-y divide-border">
              {data.map((j) => <JobRow key={j.id} job={j} sessionId={sessionId} onLogs={() => setLogsFor(j.id)} />)}
            </ul>
          )}
      </CardBody>
      {logsFor && <LogModal jobId={logsFor} onClose={() => setLogsFor(null)} />}
    </Card>
  )
}

function JobRow({ job, sessionId, onLogs }: { job: Job; sessionId: string; onLogs: () => void }) {
  const qc = useQueryClient()
  const active = job.status === 'queued' || job.status === 'running'
  const outs = useQuery({
    queryKey: ['joboutputs', job.id],
    queryFn: () => getJobOutputs(job.id),
    enabled: job.status === 'succeeded',
  })
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Badge tone={job.status}>{job.status}</Badge>
        <code className="font-medium">{job.operation}</code>
        {job.status === 'running' && <Spinner className="text-primary" />}
        <span className="flex-1" />
        {job.exit_code !== null && <span className="text-xs text-muted">exit {job.exit_code}</span>}
        <span className="text-xs text-muted">{fmtDate(job.created_at)}</span>
        <Button size="sm" variant="ghost" onClick={onLogs}><ScrollText size={14} /></Button>
        {active && <Button size="sm" variant="ghost" onClick={() => cancelJob(job.id).then(() => qc.invalidateQueries({ queryKey: ['jobs', sessionId] }))}><Ban size={14} /></Button>}
      </div>
      {job.status === 'running' && (
        <div className="mt-1.5 h-1.5 rounded-full bg-bg overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: `${job.progress ?? 8}%` }}
          />
        </div>
      )}
      {job.status === 'failed' && job.error_summary && (
        <pre className="mono text-xs text-danger bg-bg rounded p-2 mt-1 max-h-24 overflow-auto whitespace-pre-wrap">{job.error_summary}</pre>
      )}
      {job.status === 'succeeded' && !!outs.data?.length && (
        <div className="flex flex-wrap gap-1 mt-1">
          {outs.data.map((f) => (
            <button key={f.id} onClick={() => downloadFile(sessionId, f.id, f.filename)}
              className="inline-flex items-center gap-1 text-xs rounded bg-success/15 text-success px-2 py-0.5 hover:opacity-80">
              <Download size={11} /> {f.filename}
            </button>
          ))}
        </div>
      )}
    </li>
  )
}

function LogModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({ queryKey: ['joblogs', jobId], queryFn: () => getJobLogs(jobId) })
  return (
    <div className="fixed inset-0 bg-black/50 grid place-items-center p-6 z-50" onClick={onClose}>
      <Card className="max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="flex items-center justify-between">
          <span className="font-medium text-sm flex items-center gap-2"><FileText size={14} /> 로그 — {jobId}</span>
          <Button size="sm" variant="ghost" onClick={onClose}><X size={14} /></Button>
        </CardHeader>
        <CardBody className="overflow-auto">
          {isLoading ? <Spinner /> : <pre className="mono text-xs whitespace-pre-wrap">{data || '(로그 없음)'}</pre>}
        </CardBody>
      </Card>
    </div>
  )
}
