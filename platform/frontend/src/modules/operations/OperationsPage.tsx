import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Box } from 'lucide-react'
import { getOperation, listOperations } from '@/shared/api/endpoints'
import type { OperationDetail } from '@/shared/api/types'
import { Badge, Card, CardBody, Input, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { OptionReference } from './OptionReference'

const CAT_LABEL: Record<string, string> = {
  core: '코어', deform: '변형', mesh: '메쉬', material: '재료',
  analysis: '해석', bc: '하중/경계', model: '모델',
}

export function OperationsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['operations'], queryFn: listOperations })
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<string | null>(null)

  const groups = useMemo(() => {
    const filtered = (data ?? []).filter(
      (o) => o.name.includes(q) || o.summary.toLowerCase().includes(q.toLowerCase()),
    )
    const by: Record<string, typeof filtered> = {}
    for (const o of filtered) (by[o.category] ??= []).push(o)
    return by
  }, [data, q])

  return (
    <div>
      <PageHeader title="오퍼레이션 카탈로그" desc={`KooRemapper가 지원하는 ${data?.length ?? ''}개 작업. 각 작업의 인자/입출력/예제를 확인하세요.`} />
      <div className="relative mb-4 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <Input className="pl-9" placeholder="검색 (이름/설명)" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="p-10 text-center"><Spinner /></div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).map(([cat, ops]) => (
            <div key={cat}>
              <h2 className="text-sm font-semibold text-muted mb-2">{CAT_LABEL[cat] ?? cat} ({ops.length})</h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {ops.map((o) => (
                  <Card key={o.name} className="cursor-pointer hover:border-primary transition" onClick={() => setSel(o.name)}>
                    <CardBody className="py-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Box size={14} className="text-primary" />
                        <code className="text-sm font-medium">{o.name}</code>
                        {o.requires_gmsh && <Badge tone="canceled">gmsh</Badge>}
                      </div>
                      <p className="text-xs text-muted line-clamp-2">{o.summary}</p>
                    </CardBody>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {sel && <OperationDetailModal op={sel} onClose={() => setSel(null)} />}
    </div>
  )
}

function OperationDetailModal({ op, onClose }: { op: string; onClose: () => void }) {
  const { data, error } = useQuery<OperationDetail>({ queryKey: ['operation', op], queryFn: () => getOperation(op) })
  return (
    <div className="fixed inset-0 bg-black/50 grid place-items-center p-6 z-50" onClick={onClose}>
      <Card className="max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <CardBody>
          {error ? <div className="text-sm text-danger">불러오기 실패: {String((error as Error).message)}</div> : !data ? <Spinner /> : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <code className="text-lg font-semibold">{data.name}</code>
                <Badge>{data.invocation}</Badge>
                {data.config_style && <Badge>{data.config_style}</Badge>}
              </div>
              <p className="text-sm text-muted mb-3">{data.description}</p>
              <h3 className="text-xs font-semibold text-muted mb-1">인자</h3>
              <div className="space-y-1 mb-3">
                {data.params.map((p) => (
                  <div key={p.name} className="text-xs flex gap-2">
                    <code className={p.required ? 'text-fg font-medium' : 'text-muted'}>{p.name}{p.required ? '*' : ''}</code>
                    <span className="text-muted">{p.type}</span>
                    <span className="text-muted flex-1">{p.description}</span>
                  </div>
                ))}
              </div>
              {(data.keys?.length || data.presets?.length) ? (
                <>
                  <h3 className="text-xs font-semibold text-muted mb-1 mt-3">옵션/키 레퍼런스</h3>
                  <OptionReference keys={data.keys} presets={data.presets} />
                </>
              ) : null}
              <h3 className="text-xs font-semibold text-muted mb-1 mt-3">예제 args</h3>
              <pre className="mono text-xs bg-bg rounded-md p-3 overflow-auto">{JSON.stringify(data.example.args, null, 2)}</pre>
              {data.notes && <p className="text-xs text-muted mt-3">{data.notes}</p>}
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
