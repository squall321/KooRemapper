// 낙하/충격 리포트(deep/sphere/impact) 인제스트·요약·최악케이스·DataHub 등재 패널.
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, Trash2, ChevronRight, FileBarChart, ExternalLink, UploadCloud, Pencil } from 'lucide-react'
import {
  attachReportScenario, deleteReport, getReport, ingestReport, listReportCases, listReports,
  patchReportMeta, publishReportToDatahub, reportHtmlBlobUrl,
} from '@/shared/api/endpoints'
import type { Report, ReportCase, ReportFinding, ReportListItem, SessionFile } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Spinner } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
import { ReportAnalysis } from './ReportAnalysis'

const KIND_LABEL: Record<string, string> = {
  deep: '단건 심층', sphere: '전각도 낙하', impact: '전위치 부분충격',
}

function fmt(n: number | null | undefined, d = 1): string {
  return n == null ? '—' : Number(n).toFixed(d)
}

export function ReportsPanel({ sessionId, files = [] }: { sessionId: string; files?: SessionFile[] }) {
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
                {openId === r.id && <ReportDetail sessionId={sessionId} reportId={r.id} files={files} />}
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

function ReportDetail({ sessionId, reportId, files }: { sessionId: string; reportId: string; files: SessionFile[] }) {
  const report = useQuery<Report>({ queryKey: ['report', reportId], queryFn: () => getReport(reportId) })
  const cases = useQuery<ReportCase[]>({
    queryKey: ['report-cases', reportId], queryFn: () => listReportCases(reportId, 'max_stress', 'desc', 10),
  })
  const [htmlUrl, setHtmlUrl] = useState<string | null>(null)
  // blob URL 은 교체·언마운트 시 해제(메모리 누수 방지).
  useEffect(() => () => { if (htmlUrl) URL.revokeObjectURL(htmlUrl) }, [htmlUrl])

  if (report.isLoading || !report.data) return <div className="px-4 py-3"><Spinner /></div>
  const r = report.data
  const findings = r.findings ?? []
  const em = (r.eng_meta ?? {}) as { project?: string; dev_revision?: { code?: string }; design_variation?: string }
  const kfileName = files.find((f) => f.id === r.source_kfile_id)?.filename

  return (
    <div className="px-4 py-3 bg-muted/10 space-y-3 text-xs">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
        {(em.project || r.project_name) && <span>과제 <b className="text-fg">{em.project ?? r.project_name}</b></span>}
        {em.dev_revision?.code && <span>rev <b className="text-fg">{em.dev_revision.code}</b></span>}
        {em.design_variation && <span>설계안 <b className="text-fg">{em.design_variation}</b></span>}
        {kfileName && <span>K파일 <b className="text-fg">{kfileName}</b></span>}
        {r.doe_strategy && <span>DOE <b className="text-fg">{r.doe_strategy}</b></span>}
        <span>케이스 <b className="text-fg">{r.n_cases}</b></span>
        {r.generator && <span>{r.generator}</span>}
      </div>
      {scenarioLabel(r.scenario) && (
        <div className="text-muted">시뮬 조건 — <span className="text-fg">{scenarioLabel(r.scenario)}</span></div>
      )}

      {/* key: 메타/링크가 갱신되면 리마운트해 편집기·프리필 상태가 낡지 않게 한다 */}
      <MetaEditor key={metaKey(r)} report={r} files={files} />

      {findings.length > 0 && <Findings items={findings} />}

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

      <ReportAnalysis report={r} cases={cases.data ?? []} />

      <div className="flex items-center gap-2 flex-wrap">
        {r.source_file_id != null && (
          <Button size="sm" variant="ghost" onClick={async () => setHtmlUrl(await reportHtmlBlobUrl(sessionId, r.source_file_id!))}>
            <ExternalLink size={13} /> 원본 리포트 보기
          </Button>
        )}
        <PublishDatahub key={metaKey(r)} reportId={reportId}
                        defaultProject={em.project ?? ''}
                        defaultStage={em.dev_revision?.code ?? ''} />
      </div>

      {htmlUrl && (
        <iframe title="report" src={htmlUrl} className="w-full h-[480px] border border-border rounded bg-white" />
      )}
    </div>
  )
}

/** 발견사항 — 심각도 높은 것부터, 접으면 권고까지 읽힌다.
 *  예전에는 상위 5건의 제목만 보여 줘서 "무엇을 하라"는 부분(recommendation)이 화면에 없었다. */
function Findings({ items }: { items: ReportFinding[] }) {
  const [open, setOpen] = useState<number | null>(null)
  const rank = (s: string) => (s === 'CRITICAL' ? 0 : s === 'WARNING' ? 1 : 2)
  const sorted = [...items].sort((a, b) => rank(a.severity) - rank(b.severity))
  const crit = sorted.filter((f) => f.severity === 'CRITICAL').length
  return (
    <div className="space-y-1">
      <div className="text-muted">
        발견사항 {sorted.length}건{crit > 0 && <span className="text-danger"> · CRITICAL {crit}</span>}
      </div>
      {sorted.map((f, i) => (
        <div key={i} className="rounded border border-border">
          <button className="w-full flex items-start gap-2 px-2 py-1 text-left"
                  onClick={() => setOpen(open === i ? null : i)}>
            <Badge tone={f.severity === 'CRITICAL' ? 'failed' : f.severity === 'WARNING' ? 'canceled' : 'default'}>
              {f.severity}
            </Badge>
            <span className="text-fg flex-1">{f.title}</span>
            <ChevronRight size={12} className={`text-muted mt-0.5 ${open === i ? 'rotate-90 transition' : 'transition'}`} />
          </button>
          {open === i && (
            <div className="px-2 pb-2 space-y-1 text-muted">
              {f.detail && <div className="whitespace-pre-wrap">{f.detail}</div>}
              {f.recommendation && (
                <div className="text-fg"><span className="text-muted">권고 — </span>{f.recommendation}</div>
              )}
            </div>
          )}
        </div>
      ))}
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

/** 메타 상태 키 — 이 값이 바뀌면 편집기/등재폼을 리마운트해 낡은 state 를 버린다. */
function metaKey(r: Report): string {
  const em = (r.eng_meta ?? {}) as { project?: string; dev_revision?: { code?: string }; design_variation?: string }
  return [em.project ?? '', em.dev_revision?.code ?? '', em.design_variation ?? '',
          r.source_kfile_id ?? '', r.scenario_file_id ?? ''].join('|')
}

/** 시뮬 조건 요약 한 줄 — scenario.json 요약(source_type·tolerance·예상 run). */
function scenarioLabel(scenario: Record<string, unknown> | null | undefined): string | null {
  const sc = (scenario as { scenarios?: Array<Record<string, unknown>> } | null)?.scenarios?.[0]
  if (!sc) return null
  const parts: string[] = []
  if (sc.source_type) parts.push(String(sc.source_type))
  const tol = sc.tolerance as { doe_count?: number; doe_type?: string } | null
  if (tol?.doe_count) parts.push(`섭동 ×${tol.doe_count}${tol.doe_type ? ` (${tol.doe_type})` : ''}`)
  if (sc.expected_runs != null) parts.push(`예상 ${sc.expected_runs} run`)
  return parts.length ? parts.join(' · ') : null
}

/** 과제명·rev·원본 K파일·scenario.json 수동 설정 — 접힌 편집기. */
function MetaEditor({ report, files }: { report: Report; files: SessionFile[] }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const em = (report.eng_meta ?? {}) as { project?: string; dev_revision?: { code?: string }; design_variation?: string }
  const [project, setProject] = useState(em.project ?? '')
  const [devRev, setDevRev] = useState(em.dev_revision?.code ?? '')
  const [variation, setVariation] = useState(em.design_variation ?? '')
  const [kfileId, setKfileId] = useState<string>(report.source_kfile_id != null ? String(report.source_kfile_id) : '')
  const [err, setErr] = useState<string | null>(null)
  const scenRef = useRef<HTMLInputElement>(null)
  const kFiles = files.filter((f) => /\.(k|key|dyn|dynain|inc)$/i.test(f.filename))

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['report', report.id] })
    qc.invalidateQueries({ queryKey: ['reports', report.session_id] })
  }
  const save = useMutation({
    // ""=삭제 시맨틱 — 칸을 비우고 저장하면 그 필드가 지워진다(조용한 no-op 방지).
    mutationFn: () => patchReportMeta(report.id, {
      project, dev_rev: devRev, variation,
      ...(kfileId ? { kfile_id: Number(kfileId) } : {}),
    }),
    onSuccess: () => { setErr(null); setOpen(false); refresh() },
    onError: (e) => setErr(errorMessage(e)),
  })
  const attach = useMutation({
    mutationFn: (f: File) => attachReportScenario(report.id, f),
    onSuccess: () => { setErr(null); refresh() },
    onError: (e) => setErr(errorMessage(e)),
  })

  if (!open) {
    return (
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Pencil size={12} /> 과제/조건 설정
      </Button>
    )
  }
  return (
    <div className="rounded border border-border p-2 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="과제명 (S26-X)" className="w-28 text-xs" />
        <Input value={devRev} onChange={(e) => setDevRev(e.target.value)} placeholder="rev (dv1)" className="w-20 text-xs" />
        <Input value={variation} onChange={(e) => setVariation(e.target.value)} placeholder="설계안" className="w-20 text-xs" />
        <select value={kfileId} onChange={(e) => setKfileId(e.target.value)}
                className="h-8 rounded border border-border bg-surface px-2 text-xs">
          <option value="">원본 K파일 선택…</option>
          {kFiles.map((f) => <option key={f.id} value={f.id}>{f.filename}</option>)}
        </select>
        <input ref={scenRef} type="file" accept=".json" hidden onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) attach.mutate(f)
          e.target.value = ''
        }} />
        <Button size="sm" variant="ghost" onClick={() => scenRef.current?.click()} disabled={attach.isPending}>
          {attach.isPending ? <Spinner /> : 'scenario.json 첨부'}
        </Button>
        <Button size="sm" variant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? <Spinner /> : '저장'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>닫기</Button>
      </div>
      {err && <div className="text-danger whitespace-pre-wrap">{err}</div>}
      <div className="text-muted">scenario.json 을 첨부하면 시뮬 조건이 요약되고 template(.k 이름)으로 원본 K파일이 자동 연결됩니다.</div>
    </div>
  )
}

function PublishDatahub({ reportId, defaultProject, defaultStage = 'dv1' }:
  { reportId: string; defaultProject: string; defaultStage?: string }) {
  const [open, setOpen] = useState(false)
  const [project, setProject] = useState(defaultProject)
  const [stage, setStage] = useState(defaultStage)
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
      {/* 비워도 등재 가능 — 서버가 리포트에 설정된 과제 메타(eng_meta)로 폴백한다 */}
      <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="과제(비우면 메타)" className="w-28 text-xs" />
      <Input value={stage} onChange={(e) => setStage(e.target.value)} placeholder="rev(비우면 메타)" className="w-24 text-xs" />
      <Button size="sm" variant="primary" onClick={() => pub.mutate()} disabled={pub.isPending}>
        {pub.isPending ? <Spinner /> : '등재'}
      </Button>
      {result && <span className="text-success">✓ {result}</span>}
      {err && <span className="text-danger">{err}</span>}
    </div>
  )
}
