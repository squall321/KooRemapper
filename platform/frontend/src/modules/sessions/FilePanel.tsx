import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, Download, Trash2, ChevronRight, FileText, FolderUp, AlertTriangle } from 'lucide-react'
import { deleteFile, downloadFile, getIncludeStatus, uploadFiles } from '@/shared/api/endpoints'
import type { SessionFile } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Spinner } from '@/shared/ui/ui'
import { fmtBytes } from '@/shared/lib/cn'
import { errorMessage } from '@/shared/api/client'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
import { ConnectivityView } from './ConnectivityView'

export function FilePanel({ sessionId, files }: { sessionId: string; files: SessionFile[] }) {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const dirInputRef = useRef<HTMLInputElement>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<SessionFile | null>(null)

  const inc = useQuery({
    queryKey: ['session', sessionId, 'includes'],
    queryFn: () => getIncludeStatus(sessionId),
  })
  const upload = useMutation({
    mutationFn: (fl: File[]) => uploadFiles(sessionId, fl),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['session', sessionId] }); inc.refetch() },
    onError: (e) => setErr(errorMessage(e)),
  })
  const del = useMutation({
    mutationFn: (id: number) => deleteFile(sessionId, id),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['session', sessionId] }); inc.refetch() },
    onError: (e) => setErr(errorMessage(e)),
  })

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <span className="font-medium text-sm">파일 ({files.length})</span>
        <div className="flex items-center gap-1.5">
          <input ref={inputRef} type="file" multiple hidden onChange={(e) => {
            const fl = Array.from(e.target.files ?? [])
            if (fl.length) upload.mutate(fl)
            e.target.value = ''
          }} />
          {/* 폴더 업로드 — 하위 폴더에 인클루드를 둔 덱은 이쪽으로 올려야 경로가 보존된다.
              webkitdirectory 는 표준 속성이 아니라 React 타입에 없어 확장 속성으로 넘긴다. */}
          <input ref={dirInputRef} type="file" multiple hidden onChange={(e) => {
            const fl = Array.from(e.target.files ?? [])
            if (fl.length) upload.mutate(fl)
            e.target.value = ''
          }} {...({ webkitdirectory: '', directory: '' } as Record<string, string>)} />
          <Button size="sm" variant="ghost" onClick={() => dirInputRef.current?.click()} disabled={upload.isPending}
                  title="폴더째 올립니다 — *INCLUDE 가 하위 폴더를 가리키면 이쪽을 쓰세요">
            <FolderUp size={14} /> 폴더
          </Button>
          <Button size="sm" variant="primary" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
            {upload.isPending ? <Spinner /> : <Upload size={14} />} 업로드
          </Button>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {err && <div className="px-3 py-2 text-xs text-danger border-b border-border">{err}</div>}
        {/* 인클루드가 빠져 있으면 op 은 성공하고 산출물이 깨진다 — 실행 전에 보이게 한다. */}
        {inc.data && !inc.data.ok && (
          <div className="px-3 py-2 text-xs text-warning border-b border-border flex gap-2">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="font-medium">참조된 *INCLUDE 가 세션에 없습니다 — 그 파일도 올리세요(하위 폴더면 '폴더' 버튼).</div>
              {Object.entries(inc.data.missing_by_file).map(([f, v]) => (
                <div key={f} className="mono">{f} → {v.missing.join(', ')}</div>
              ))}
            </div>
          </div>
        )}
        {!files.length ? (
          <EmptyState title="파일 없음" hint="K파일을 업로드하면 자동으로 정보를 분석합니다." />
        ) : (
          <ul className="divide-y divide-border">
            {files.map((f) => {
              const m = f.meta ?? {}
              const open = expanded === f.id
              return (
                <li key={f.id} className="text-sm">
                  <div className="flex items-center gap-2 px-3 py-2">
                    <button onClick={() => setExpanded(open ? null : f.id)} className="text-muted">
                      <ChevronRight size={14} className={open ? 'rotate-90 transition' : 'transition'} />
                    </button>
                    <FileText size={14} className="text-muted shrink-0" />
                    <span className="truncate flex-1">{f.filename}</span>
                    <Badge tone={f.kind === 'output' ? 'succeeded' : 'default'}>{f.kind}</Badge>
                    {typeof m.nodes === 'number' && <span className="text-xs text-muted">{m.nodes}N/{m.elements}E</span>}
                    <Button size="sm" variant="ghost" onClick={() => downloadFile(sessionId, f.id, f.filename)}><Download size={14} /></Button>
                    <Button size="sm" variant="ghost" onClick={() => setPendingDelete(f)}><Trash2 size={14} /></Button>
                  </div>
                  {open && (
                    <div className="px-9 pb-3 text-xs text-muted space-y-1">
                      <div>크기: {fmtBytes(f.size_bytes)}</div>
                      {m.parts !== undefined && <div>노드 {m.nodes} · 요소 {m.elements} · 파트 {m.parts}</div>}
                      {m.bbox_min && m.bbox_max && (
                        <div>bbox: [{m.bbox_min.map((n) => n.toFixed(1)).join(', ')}] → [{m.bbox_max.map((n) => n.toFixed(1)).join(', ')}]</div>
                      )}
                      {!!m.includes?.length && <div>*INCLUDE: {m.includes.join(', ')}</div>}
                      {!!m.part_titles?.length && <div>파트: {m.part_titles.slice(0, 5).join(' · ')}</div>}
                      {m.keyword_counts && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {Object.entries(m.keyword_counts).slice(0, 12).map(([k, v]) => (
                            <span key={k} className="rounded bg-bg px-1.5 py-0.5 mono">{k}:{v}</span>
                          ))}
                        </div>
                      )}
                      {m.info_error && <div className="text-danger">분석 오류: {m.info_error}</div>}
                      {m.modelmeta && !m.modelmeta.error && (
                        <div className="pt-2 mt-1 border-t border-border">
                          <div className="font-medium text-foreground mb-2">파트 연결도 · 메트릭</div>
                          <ConnectivityView sessionId={sessionId} fileId={f.id} meta={m.modelmeta} />
                        </div>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </CardBody>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="파일 삭제"
        message={pendingDelete ? `'${pendingDelete.filename}' 파일을 삭제하시겠습니까?` : undefined}
        confirmLabel="삭제"
        danger
        onConfirm={() => {
          if (pendingDelete) del.mutate(pendingDelete.id)
          setPendingDelete(null)
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  )
}
