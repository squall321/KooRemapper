import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText, ScrollText, X, Ban, AlertTriangle, ClipboardCopy, LifeBuoy, Image as ImageIcon } from 'lucide-react'
import {
  cancelJob, downloadFile, downloadJobDiagnostics, getJobDiagnostics, getJobLogs, svgBlobUrl,
  getJobOutputs, listSessionJobs,
} from '@/shared/api/endpoints'
import type { Job } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Spinner } from '@/shared/ui/ui'
import { fmtDate } from '@/shared/lib/cn'
import { errorMessage } from '@/shared/api/client'

// 그림마다 **있는 숫자가 다르다** — 한 캡션을 세 그림에 돌려 쓰면 없는 것을 읽으라고 말한다.
//   · 단면: 확대 배율·최소피처가 그림에 있다. 축 선택 근거는 **매니페스트·콘솔**에 있다(그림 아님).
//   · 자유면: **등축**이라 배율이 없다. 자유면 비율·등진 삼각형 수가 요지다.
//   · 층 모식도: 배율도 최소피처도 없다. 바닥 처리한 층과 감싸는 파트가 요지다.
function figAlt(name: string): string {
  if (/_surface\.svg$/i.test(name)) return '자유면 뷰'
  if (/_stackdiagram\.svg$/i.test(name)) return '층 모식도'
  if (/_section\.svg$/i.test(name)) return '단면 그림'
  return '그림'
}

function figCaption(name: string): string {
  if (/_surface\.svg$/i.test(name))
    return '이 뷰는 등축이다 — 배율이 없고, 얇은 적층은 얇게 보이는 것이 사실이다. 층 두께는 단면 그림이 답한다.'
  if (/_stackdiagram\.svg$/i.test(name))
    return '모식도다(파트 축 범위로 그린다) — 바닥 처리한 층은 두께가 과장되므로 옆에 적힌 숫자가 참이다.'
  if (/_section\.svg$/i.test(name))
    return '그림 안의 확대 배율·최소피처를 함께 읽으라 — 축을 고른 근거는 매니페스트(JSON)와 잡 로그에 있다.'
  return '그림과 함께 잡 로그의 숫자를 읽으라 — 그것이 그림이 거짓말하지 않게 하는 장치다.'
}

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
  // 그림 산출물을 받기 전에 볼 수 있게 — blob URL 은 닫을 때 반드시 해제한다(누수).
  const [figUrl, setFigUrl] = useState<string | null>(null)
  const [figName, setFigName] = useState<string>('')
  const qc = useQueryClient()
  const active = job.status === 'queued' || job.status === 'running'
  const outs = useQuery({
    queryKey: ['joboutputs', job.id],
    queryFn: () => getJobOutputs(job.id),
    enabled: job.status === 'succeeded',
  })
  const cancel = useMutation({
    mutationFn: () => cancelJob(job.id),
    onSettled: () => qc.invalidateQueries({ queryKey: ['jobs', sessionId] }),
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
        {active && <Button size="sm" variant="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate()}><Ban size={14} /></Button>}
      </div>
      {job.status === 'running' && (
        <div className="mt-1.5 h-1.5 rounded-full bg-bg overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: `${job.progress ?? 8}%` }}
          />
        </div>
      )}
      {cancel.isError && <div className="text-xs text-danger mt-1">취소 실패: {errorMessage(cancel.error)}</div>}
      {job.status === 'failed' && job.error_summary && (
        <pre className="mono text-xs text-danger bg-bg rounded p-2 mt-1 max-h-24 overflow-auto whitespace-pre-wrap">{job.error_summary}</pre>
      )}
      {job.status === 'failed' && <DiagnosticsActions jobId={job.id} />}
      {/* ⚠ status 조건을 걸지 않는다 — **성공한 잡**에 떠야 하는 경고다. rc=0 인데 산출 덱이
          상한 것이 실제 사고의 모양이었다(요소 소실·개행 소실). 실패 자리에 숨기면 못 본다. */}
      {!!job.warnings?.length && (
        <ul className="mt-1 space-y-0.5">
          {job.warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-warning bg-warning/10 rounded px-2 py-1">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span className="break-all">{w}</span>
            </li>
          ))}
        </ul>
      )}
      {job.status === 'succeeded' && !!outs.data?.length && (
        <div className="flex flex-wrap gap-1 mt-1">
          {outs.data.map((f) => (
            <span key={f.id} className="inline-flex items-center gap-1">
              <button onClick={() => downloadFile(sessionId, f.id, f.filename)}
                className="inline-flex items-center gap-1 text-xs rounded bg-success/15 text-success px-2 py-0.5 hover:opacity-80">
                <Download size={11} /> {f.filename}
              </button>
              {/* 그림 산출물은 받기 전에 **볼 수** 있어야 한다 — 지금까지 프런트에 서버가 구운
                  그림을 띄울 자리가 아예 없었다(`<img` 태그 0건). */}
              {/\.svg$/i.test(f.filename) && (
                <button onClick={async () => { setFigName(f.filename); setFigUrl(await svgBlobUrl(sessionId, f.id)) }}
                  className="inline-flex items-center gap-1 text-xs rounded bg-accent/15 text-accent px-2 py-0.5 hover:opacity-80">
                  <ImageIcon size={11} /> 그림 보기
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      {figUrl && (
        <div className="mt-2">
          {/* ⚠ `<img>` 로만 띄운다 — SVG 안 스크립트가 실행되지 않는 유일한 경로다.
              `dangerouslySetInnerHTML`·`<object>`·`<iframe>` 으로 바꾸면 저장형 XSS 가 된다. */}
          <img src={figUrl} alt={figAlt(figName)} className="max-w-full border border-border rounded bg-white" />
          <div className="mt-1 flex items-center gap-2">
            <button onClick={() => { URL.revokeObjectURL(figUrl); setFigUrl(null) }}
              className="text-xs text-muted hover:underline">닫기</button>
            <span className="text-[11px] text-muted">{figCaption(figName)}</span>
          </div>
        </div>
      )}
    </li>
  )
}

/** 실패한 잡의 진단 정보를 넘기는 자리 — 짧은 요약은 클립보드, 전문은 .zip 이다.
 *
 *  ⚠ **덱 본문은 사용자가 켤 때만** 담는다. 고객 CAE 모델이라 형상·물성이 IP 다.
 *  ⚠ 클립보드는 거부될 수 있다(권한·비보안 컨텍스트). 그때 조용히 실패하면 사용자는 복사된 줄
 *     알고 빈 것을 붙인다 — 그래서 선택 가능한 텍스트로 되돌아간다. */
function DiagnosticsActions({ jobId }: { jobId: string }) {
  const [deckLines, setDeckLines] = useState(false)
  const [copied, setCopied] = useState(false)
  const [fallback, setFallback] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const copy = useMutation({
    mutationFn: () => getJobDiagnostics(jobId, deckLines),
    onSuccess: async ({ summary }) => {
      setErr(null)
      try {
        await navigator.clipboard.writeText(summary)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch {
        setFallback(summary)
      }
    },
    onError: (e) => setErr(errorMessage(e)),
  })
  const save = useMutation({
    mutationFn: () => downloadJobDiagnostics(jobId, deckLines),
    onError: (e) => setErr(errorMessage(e)),
  })

  return (
    <div className="mt-1.5 rounded bg-bg px-2 py-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-xs text-muted"><LifeBuoy size={12} /> 진단</span>
        <Button size="sm" variant="ghost" disabled={copy.isPending} onClick={() => copy.mutate()}>
          <ClipboardCopy size={13} /> {copied ? '복사됨' : '정보 복사'}
        </Button>
        <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate()}>
          <Download size={13} /> 파일 받기
        </Button>
        <label className="inline-flex items-center gap-1 text-xs text-muted cursor-pointer">
          <input type="checkbox" checked={deckLines} onChange={(e) => setDeckLines(e.target.checked)} />
          덱 발췌 더 담기
        </label>
      </div>
      {/* ⚠ 약속을 정확히 적는다. 처음엔 "덱의 문제 줄 포함" 이라고 써서 **끄면 덱 본문이 안
          나간다**는 뜻으로 읽혔는데 그것이 거짓이었다 — 도구가 참조 문제를 보고할 때 덱 원문
          줄을 stdout 에 그대로 찍고, 로그 꼬리는 이 체크박스와 무관하게 실린다. */}
      <div className="text-[11px] text-muted mt-1">
        로그에는 도구가 출력한 덱 줄이 이미 포함될 수 있습니다. 이 항목은 <b>그 밖의 발췌</b>를 더할지만 정합니다.
      </div>
      {err && <div className="text-xs text-danger mt-1">진단 정보를 가져오지 못했습니다: {err}</div>}
      {fallback && (
        <div className="mt-1">
          <div className="text-xs text-muted mb-1">클립보드를 쓸 수 없습니다 — 아래 내용을 직접 복사해 주세요.</div>
          <textarea readOnly value={fallback} onFocus={(e) => e.currentTarget.select()}
            className="mono w-full h-40 text-xs bg-surface border border-border rounded p-2" />
        </div>
      )}
    </div>
  )
}

function LogModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ['joblogs', jobId], queryFn: () => getJobLogs(jobId) })
  return (
    <div className="fixed inset-0 bg-black/50 grid place-items-center p-6 z-50" onClick={onClose}>
      <Card className="max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="flex items-center justify-between">
          <span className="font-medium text-sm flex items-center gap-2"><FileText size={14} /> 로그 — {jobId}</span>
          <Button size="sm" variant="ghost" onClick={onClose}><X size={14} /></Button>
        </CardHeader>
        <CardBody className="overflow-auto">
          {isLoading ? <Spinner /> : error ? <div className="text-sm text-danger">로그를 불러오지 못했습니다: {errorMessage(error)}</div> : <pre className="mono text-xs whitespace-pre-wrap">{data || '(로그 없음)'}</pre>}
        </CardBody>
      </Card>
    </div>
  )
}
