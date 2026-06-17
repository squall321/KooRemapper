import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FolderOpen, BookOpen, KeyRound, ArrowRight } from 'lucide-react'
import { listOperations, listSessions } from '@/shared/api/endpoints'
import { Card, CardBody, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { fmtDate } from '@/shared/lib/cn'

export function DashboardPage() {
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: listSessions })
  const ops = useQuery({ queryKey: ['operations'], queryFn: listOperations })

  const stat = (label: string, value: number | string, icon: React.ReactNode, to: string) => (
    <Link to={to}>
      <Card className="hover:border-primary transition">
        <CardBody className="flex items-center gap-3">
          <div className="text-primary">{icon}</div>
          <div>
            <div className="text-2xl font-semibold">{value}</div>
            <div className="text-xs text-muted">{label}</div>
          </div>
        </CardBody>
      </Card>
    </Link>
  )

  return (
    <div>
      <PageHeader title="대시보드" desc="KooRemapper 플랫폼 — LS-DYNA K파일 메쉬/응력/해석 전처리." />
      <div className="grid gap-3 sm:grid-cols-3 mb-6">
        {stat('세션', sessions.data?.length ?? '–', <FolderOpen size={28} />, '/sessions')}
        {stat('오퍼레이션', ops.data?.length ?? '–', <BookOpen size={28} />, '/operations')}
        {stat('MCP 토큰', 'Claude 연결', <KeyRound size={28} />, '/tokens')}
      </div>

      <Card>
        <CardBody>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">최근 세션</h2>
            <Link to="/sessions" className="text-xs text-primary flex items-center gap-1">전체 보기 <ArrowRight size={12} /></Link>
          </div>
          {sessions.isLoading ? (
            <Spinner />
          ) : !sessions.data?.length ? (
            <p className="text-sm text-muted">세션이 없습니다. <Link to="/sessions" className="text-primary">새로 만들기</Link></p>
          ) : (
            <div className="divide-y divide-border">
              {sessions.data.slice(0, 6).map((s) => (
                <Link key={s.id} to={`/sessions/${s.id}`} className="flex items-center justify-between py-2 text-sm hover:text-primary">
                  <span className="truncate">{s.name}</span>
                  <span className="text-xs text-muted">{s.file_count ?? 0} 파일 · {fmtDate(s.updated_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
