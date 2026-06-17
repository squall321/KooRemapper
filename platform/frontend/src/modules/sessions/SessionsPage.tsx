import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FolderOpen, Plus, FileText } from 'lucide-react'
import { createSession, listSessions } from '@/shared/api/endpoints'
import { Button, Card, CardBody, EmptyState, Input, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { fmtDate } from '@/shared/lib/cn'

export function SessionsPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: listSessions })
  const [name, setName] = useState('')
  const [open, setOpen] = useState(false)
  const create = useMutation({
    mutationFn: () => createSession(name || '새 세션'),
    onSuccess: () => { setName(''); setOpen(false); qc.invalidateQueries({ queryKey: ['sessions'] }) },
  })

  return (
    <div>
      <PageHeader
        title="세션"
        desc="업로드한 K파일과 작업 결과를 묶어 관리하는 프로젝트 단위입니다."
        actions={<Button variant="primary" onClick={() => setOpen((o) => !o)}><Plus size={16} /> 새 세션</Button>}
      />

      {open && (
        <Card className="mb-4">
          <CardBody className="flex gap-2">
            <Input autoFocus placeholder="세션 이름" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && create.mutate()} />
            <Button variant="primary" onClick={() => create.mutate()} disabled={create.isPending}>생성</Button>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="p-10 text-center"><Spinner /></div>
      ) : !data?.length ? (
        <EmptyState title="세션이 없습니다" hint="새 세션을 만들어 K파일을 업로드하세요." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => (
            <Link key={s.id} to={`/sessions/${s.id}`}>
              <Card className="hover:border-primary transition h-full">
                <CardBody>
                  <div className="flex items-center gap-2 mb-2">
                    <FolderOpen size={18} className="text-primary" />
                    <span className="font-medium truncate">{s.name}</span>
                  </div>
                  {s.description && <p className="text-xs text-muted line-clamp-2 mb-2">{s.description}</p>}
                  <div className="flex items-center gap-3 text-xs text-muted">
                    <span className="flex items-center gap-1"><FileText size={12} /> {s.file_count ?? 0} 파일</span>
                    <span>{fmtDate(s.updated_at)}</span>
                  </div>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
