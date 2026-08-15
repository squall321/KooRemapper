// 낙하/충격 리포트(deep/sphere/impact) 인제스트·요약·최악케이스·DataHub 등재 패널.
import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, Trash2, ChevronRight, FileBarChart, ExternalLink, UploadCloud } from 'lucide-react'
import {
  deleteReport, getReport, ingestReport, listReportCases, listReports, publishReportToDatahub, reportHtmlBlobUrl,
} from '@/shared/api/endpoints'
import type { Report, ReportCase, ReportListItem } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Spinner } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'

const KIND_LABEL: Record<string, string> = {
  deep: '단건 심층', sphere: '전각도 낙하', impact: '전위치 부분충격',
}

function fmt(n: number | null | undefined, d = 1): string {
  return n == null ? '—' : Number(n).toFixed(d)
}

export function ReportsPanel({ sessionId }: { sessionId: string }) {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<ReportListItem | null>(null)

  const reports = useQuery({ queryKey: ['reports', sessionId], queryFn: () => listReports(sessionId) })

  const upload = useMutation({
    mutationFn: (f: File) => ingestReport(sessionId, f),
    onSuccess: (r) => { setErr(null); setOpenId(r.id); qc.invalidateQueries({ queryKey: ['reports', sessionId] }) },
    onError: (e) => setErr(errorMessage(e)),
  })
  const del = useMutation({
    mutationFn: (id: string) => deleteReport(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reports', sessionId] }); setOpenId(null) },
    onError: (e) => setErr(errorMessage(e)),
  })

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <span className="font-medium text-sm flex items-center gap-2">
          <FileBarChart size={14} className="text-primary" /> 낙하/충격 리포트 ({reports.data?.length ?? 0})
        </span>
        <input ref={inputRef} type="file" accept=".html,.htm" hidden onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) upload.mutate(f)
          e.target.value = ''
        }} />
        <Button size="sm" variant="primary" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? <Spinner /> : <Upload size={14} />} 리포트 업로드
        </Button>
      </CardHeader>
      <CardBody className="p-0">
        {err && <div className="px-3 py-2 text-xs text-danger border-b border-border whitespace-pre-wrap">{err}</div>}
        {reports.isLoading ? (
          <div className="p-6 text-center"><Spinner /></div>
        ) : !reports.data?.length ? (
          <EmptyState title="리포트 없음" hint="deep/sphere/impact 리포트 HTML 을 올리면 자동 구조화됩니다." />
        ) : (
          <ul className="divide-y divide-border">
            {reports.data.map((r) => (
              <li key={r.id} className="text-sm">
                <div className="flex items-center gap-2 px-3 py-2">
                  <button onClick={() => setOpenId(openId === r.id ? null : r.id)} className="text-muted">
                    <ChevronRight size={14} className={openId === r.id ? 'rotate-90 transition' : 'transition'} />
                  </button>
                  <Badge tone="running">{KIND_LABEL[r.kind] ?? r.kind}</Badge>
                  <span className="truncate flex-1">{r.label ?? r.project_name ?? r.id}</span>
                  <span className="text-xs text-muted">{r.n_cases} 케이스</span>
                  <button className="text-muted hover:text-danger" onClick={() => setPendingDelete(r)}>
                    <Trash2 size={13} />
                  </button>
                </div>
                {openId === r.id && <ReportDetail sessionId={sessionId} reportId={r.id} />}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
      <ConfirmDialog
        open={!!pendingDelete}
        title="리포트 삭제"
        message={`'${pendingDelete?.label ?? pendingDelete?.id}' 리포트를 삭제할까요? (원본 HTML 포함)`}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete.id); setPendingDelete(null) }}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  )
}

function ReportDetail({ sessionId, reportId }: { sessionId: string; reportId: string }) {
  const report = useQuery<Report>({ queryKey: ['report', reportId], queryFn: () => getReport(reportId) })
  const cases = useQuery<ReportCase[]>({
    queryKey: ['report-cases', reportId], queryFn: () => listReportCases(reportId, 'max_stress', 'desc', 10),
  })
  const [htmlUrl, setHtmlUrl] = useState<string | null>(null)

  if (report.isLoading || !report.data) return <div className="px-4 py-3"><Spinner /></div>
  const r = report.data
  const findings = r.findings ?? []

  return (
    <div className="px-4 py-3 bg-muted/10 space-y-3 text-xs">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
        {r.project_name && <span>프로젝트 <b className="text-fg">{r.project_name}</b></span>}
        {r.doe_strategy && <span>DOE <b className="text-fg">{r.doe_strategy}</b></span>}
        <span>케이스 <b className="text-fg">{r.n_cases}</b></span>
        {r.generator && <span>{r.generator}</span>}
      </div>

      {findings.length > 0 && (
        <div className="space-y-1">
          {findings.slice(0, 5).map((f, i) => (
            <div key={i} className="flex items-start gap-2">
              <Badge tone={f.severity === 'CRITICAL' ? 'failed' : f.severity === 'WARNING' ? 'canceled' : 'default'}>{f.severity}</Badge>
              <span className="text-fg">{f.title}</span>
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="text-muted mb-1">최악 케이스 (최대 응력순)</div>
        {cases.isLoading ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="text-muted">
                <tr className="text-left">
                  <th className="py-1 pr-2">케이스 (각도/위치)</th>
                  <th className="py-1 px-2 text-right">최대응력</th>
                  <th className="py-1 px-2 text-right">최대 G</th>
                  <th className="py-1 px-2 text-right">최대변위</th>
                </tr>
              </thead>
              <tbody>
                {(cases.data ?? []).map((c) => (
                  <tr key={c.id} className="border-t border-border">
                    <td className="py-1 pr-2 truncate max-w-[180px]">{caseLabel(c)}</td>
                    <td className="py-1 px-2 text-right">{fmt(c.max_stress)}</td>
                    <td className="py-1 px-2 text-right">{fmt(c.max_g, 0)}</td>
                    <td className="py-1 px-2 text-right">{fmt(c.max_disp, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {r.source_file_id != null && (
          <Button size="sm" variant="ghost" onClick={async () => setHtmlUrl(await reportHtmlBlobUrl(sessionId, r.source_file_id!))}>
            <ExternalLink size={13} /> 원본 리포트 보기
          </Button>
        )}
        <PublishDatahub reportId={reportId} defaultProject={r.project_name ?? ''} />
      </div>

      {htmlUrl && (
        <iframe title="report" src={htmlUrl} className="w-full h-[480px] border border-border rounded bg-white" />
      )}
    </div>
  )
}

function caseLabel(c: ReportCase): string {
  const id = c.identity ?? {}
  const angle = (id as { angle?: { name?: string } }).angle
  if (angle?.name) return angle.name
  const face = (id as { face?: string; pos_id?: string }).face
  const pos = (id as { pos_id?: string }).pos_id
  if (face || pos) return pos ?? face ?? c.case_key
  return c.case_key
}

function PublishDatahub({ reportId, defaultProject }: { reportId: string; defaultProject: string }) {
  const [open, setOpen] = useState(false)
  const [project, setProject] = useState(defaultProject)
  const [stage, setStage] = useState('dv1')
  const [result, setResult] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const pub = useMutation({
    mutationFn: () => publishReportToDatahub(reportId, { project, stage }),
    onSuccess: (res) => { setErr(null); setResult(res.record_id) },
    onError: (e) => setErr(errorMessage(e)),
  })

  if (!open) {
    return <Button size="sm" variant="ghost" onClick={() => setOpen(true)}><UploadCloud size={13} /> DataHub 등재</Button>
  }
  return (
    <div className="flex items-center gap-2 flex-wrap w-full">
      <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="과제코드" className="w-28 text-xs" />
      <Input value={stage} onChange={(e) => setStage(e.target.value)} placeholder="개발단계(dv1)" className="w-24 text-xs" />
      <Button size="sm" variant="primary" onClick={() => pub.mutate()} disabled={pub.isPending || !project}>
        {pub.isPending ? <Spinner /> : '등재'}
      </Button>
      {result && <span className="text-success">✓ {result}</span>}
      {err && <span className="text-danger">{err}</span>}
    </div>
  )
}
