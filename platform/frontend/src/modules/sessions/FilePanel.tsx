import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, Download, Trash2, ChevronRight, FileText } from 'lucide-react'
import { deleteFile, downloadFile, uploadFiles } from '@/shared/api/endpoints'
import type { SessionFile } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Spinner } from '@/shared/ui/ui'
import { fmtBytes } from '@/shared/lib/cn'
import { errorMessage } from '@/shared/api/client'

export function FilePanel({ sessionId, files }: { sessionId: string; files: SessionFile[] }) {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (fl: File[]) => uploadFiles(sessionId, fl),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['session', sessionId] }) },
    onError: (e) => setErr(errorMessage(e)),
  })
  const del = useMutation({
    mutationFn: (id: number) => deleteFile(sessionId, id),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ['session', sessionId] }) },
    onError: (e) => setErr(errorMessage(e)),
  })

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <span className="font-medium text-sm">파일 ({files.length})</span>
        <input ref={inputRef} type="file" multiple hidden onChange={(e) => {
          const fl = Array.from(e.target.files ?? [])
          if (fl.length) upload.mutate(fl)
          e.target.value = ''
        }} />
        <Button size="sm" variant="primary" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? <Spinner /> : <Upload size={14} />} 업로드
        </Button>
      </CardHeader>
      <CardBody className="p-0">
        {err && <div className="px-3 py-2 text-xs text-danger border-b border-border">{err}</div>}
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
                    <Button size="sm" variant="ghost" onClick={() => del.mutate(f.id)}><Trash2 size={14} /></Button>
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
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
