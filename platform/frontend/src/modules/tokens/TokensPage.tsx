import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Plus, Trash2, Check } from 'lucide-react'
import { createToken, listTokens, revokeToken } from '@/shared/api/endpoints'
import type { TokenCreated } from '@/shared/api/types'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { fmtDate } from '@/shared/lib/cn'
import { errorMessage } from '@/shared/api/client'

function CopyBtn({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <Button size="sm" onClick={() => { navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500) }}>
      {done ? <Check size={14} /> : <Copy size={14} />} {done ? '복사됨' : '복사'}
    </Button>
  )
}

export function TokensPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['tokens'], queryFn: listTokens })
  const [name, setName] = useState('')
  const [created, setCreated] = useState<TokenCreated | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => createToken(name || 'MCP 토큰'),
    onSuccess: (d) => { setCreated(d); setName(''); qc.invalidateQueries({ queryKey: ['tokens'] }) },
    onError: (e) => setErr(errorMessage(e)),
  })
  const revoke = useMutation({
    mutationFn: (id: number) => revokeToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  })

  return (
    <div>
      <PageHeader title="MCP 토큰" desc="Claude(MCP)에서 KooRemapper를 쓰기 위한 개인 액세스 토큰을 발급·관리합니다." />

      <Card className="mb-4">
        <CardHeader className="font-medium text-sm">새 토큰 발급</CardHeader>
        <CardBody className="flex gap-2">
          <Input placeholder="토큰 이름 (예: 내 노트북)" value={name} onChange={(e) => setName(e.target.value)} />
          <Button variant="primary" onClick={() => { setErr(null); create.mutate() }} disabled={create.isPending}>
            <Plus size={16} /> 발급
          </Button>
        </CardBody>
      </Card>

      {err && <div className="text-sm text-danger mb-3">{err}</div>}

      {created && (
        <Card className="mb-4 border-primary">
          <CardHeader className="font-medium text-sm text-primary">발급 완료 — 이 값은 다시 표시되지 않습니다</CardHeader>
          <CardBody className="space-y-3">
            <div>
              <div className="text-xs text-muted mb-1">토큰</div>
              <div className="flex gap-2">
                <code className="flex-1 mono text-xs bg-bg rounded-md px-3 py-2 break-all">{created.token}</code>
                <CopyBtn text={created.token} />
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Claude Code 등록 명령</div>
              <div className="flex gap-2">
                <code className="flex-1 mono text-xs bg-bg rounded-md px-3 py-2 break-all">{created.mcp_add}</code>
                <CopyBtn text={created.mcp_add} />
              </div>
            </div>
            <Button size="sm" onClick={() => setCreated(null)}>닫기</Button>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader className="font-medium text-sm">발급된 토큰</CardHeader>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="p-6 text-center"><Spinner /></div>
          ) : !data?.length ? (
            <EmptyState title="아직 발급된 토큰이 없습니다" />
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs text-muted border-b border-border">
                <tr><th className="text-left p-3 font-medium">이름</th><th className="text-left p-3 font-medium">prefix</th><th className="text-left p-3 font-medium">상태</th><th className="text-left p-3 font-medium">마지막 사용</th><th className="text-left p-3 font-medium">만료</th><th /></tr>
              </thead>
              <tbody>
                {data.map((t) => (
                  <tr key={t.id} className="border-b border-border last:border-0">
                    <td className="p-3">{t.name}</td>
                    <td className="p-3 mono text-xs">{t.token_prefix}…</td>
                    <td className="p-3"><Badge tone={t.status === 'active' ? 'succeeded' : t.status === 'revoked' ? 'failed' : 'canceled'}>{t.status}</Badge></td>
                    <td className="p-3 text-xs text-muted">{fmtDate(t.last_used_at)}</td>
                    <td className="p-3 text-xs text-muted">{fmtDate(t.expires_at)}</td>
                    <td className="p-3 text-right">
                      {t.status === 'active' && (
                        <Button size="sm" variant="ghost" onClick={() => revoke.mutate(t.id)}><Trash2 size={14} /></Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
