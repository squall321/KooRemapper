// PreFit 기능·도구 카탈로그 — 실제 /operations(MCP와 동일 카탈로그)에 연결된 브랜딩 화면.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Box } from 'lucide-react'
import { getOperation, listOperations } from '@/shared/api/endpoints'
import type { OperationDetail } from '@/shared/api/types'
import { Badge, Card, CardBody, Input, Spinner } from '@/shared/ui/ui'
import { OptionReference } from './OptionReference'

const CAT_LABEL: Record<string, string> = {
  material: '재료', deform: '변형 · 전처리', core: '코어 · 매핑', mesh: '메쉬',
  analysis: '해석 · 솔버', bc: '하중 · 경계 · 접촉', model: '모델 · 정보',
}
const CAT_ORDER = ['material', 'deform', 'core', 'mesh', 'analysis', 'bc', 'model']
// PreFit 서사에서 앞세우는 카테고리(설계 선반영의 두 기둥)
const HOT_CATS = new Set(['material', 'deform'])

// 비전문가용 한국어 요약. 없으면 API의 summary(영문)로 폴백 → 기능이 늘어도 자동 노출.
const KO: Record<string, string> = {
  matdb: '525종 DB에서 부품 재료를 자동으로 찾아 교체',
  matswap: '특정 재료 정의를 다른 재료로 치환',
  prestress: '조립 굽힘 응력을 해석 시작점으로 반영',
  warpage: '제조·조립에서 생긴 휨(워피지)을 모델에 반영',
  bend: '지정한 곡률로 모델을 굽히기',
  formstrain: '성형 이력에 의한 변형·경화 반영',
  strain: '초기 변형 상태를 모델에 부여',
  indent: '국부 압입(인덴트) 형상 반영',
  squeeze: '조립 압착 상태 반영',
  assemble: '여러 파트를 조립 위치로 결합',
  map: '굽은/평평 메시 사이로 결과·상태를 매핑',
  shellmap: '셸 요소 간 데이터 매핑',
  unfold: '굽은 형상을 평평하게 펼치기',
  generate: '기본 형상(토러스 등) 메시 생성',
  'generate-var': '치수를 바꿔가며 형상 자동 생성',
  offset: '벽 두께를 줄이거나 늘려 반영(살파기)',
  refine: '요소를 더 잘게 나누어 정밀도 향상',
  elform: '요소 정식(formulation) 변경',
  disconnect: '붙어있는 파트를 분리',
  convert: '요소·포맷 변환',
  restack: '적층(스택) 구성 재정렬',
  wrap: '표면을 감싸는 메시 생성',
  update: '변경 사항을 모델에 반영·갱신',
  iga: '등기하 해석(IGA)용 변환',
  'extract-surface': '솔리드에서 겉면(셸)만 추출',
  tetremesh: 'gmsh 기반 사면체 재메시',
  meshfix: 'gmsh 기반 결함 메시 보정',
  cnrb2solid: '구속 강체(CNRB)를 솔리드로 변환',
  merge: '메시·파트 병합',
  strip: '불필요 카드·요소 제거',
  load: '하중·초기속도 등 부여',
  boundary: '구속·경계조건 설정',
  rbe: 'RBE/강체 연결 정의',
  contact: '접촉 카드 설정',
  relax: '초기 응력 완화(동적 완화)',
  stabilize: '수치 안정화 설정',
  database: '결과 출력(database) 카드 설정',
  hfdamp: '고주파 진동 감쇠 설정',
  explicit: 'explicit 낙하·충격 해석 제어',
  implicit: 'implicit 정적/준정적 해석 제어',
  modal: '고유진동수·모드 해석 설정',
  ale: '유체-구조(ALE) 설정',
  optimize: '설계 최적화 카드 설정',
  battery: '배터리 셀 모델링 설정',
  info: '노드·요소·파트 등 모델 정보 조회',
}

export function OperationsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['operations'], queryFn: listOperations })
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<string | null>(null)

  const { groups, shown } = useMemo(() => {
    const ql = q.trim().toLowerCase()
    const filtered = (data ?? []).filter(
      (o) => o.name.toLowerCase().includes(ql) || o.summary.toLowerCase().includes(ql) || (KO[o.name] ?? '').includes(q),
    )
    const by: Record<string, typeof filtered> = {}
    for (const o of filtered) (by[o.category] ??= []).push(o)
    const ordered = [
      ...CAT_ORDER.filter((c) => by[c]),
      ...Object.keys(by).filter((c) => !CAT_ORDER.includes(c)),
    ]
    return { groups: ordered.map((c) => [c, by[c]] as const), shown: filtered.length }
  }, [data, q])

  return (
    <div>
      {/* PreFit MCP 히어로 */}
      <div
        className="relative overflow-hidden rounded-xl p-6 mb-5 text-white"
        style={{ background: 'linear-gradient(135deg,#0E1A54,#141E3B 60%,#0B1440)' }}
      >
        <div className="mono text-[11px] tracking-[0.2em] uppercase" style={{ color: '#8FA0F0' }}>
          Capabilities · Model Context Protocol
        </div>
        <h1 className="mt-2 text-2xl font-extrabold leading-tight" style={{ letterSpacing: '-0.02em' }}>
          PreFit의 모든 기능은 <span style={{ color: '#FF8A6B' }}>MCP 도구로 열려 있습니다.</span>
        </h1>
        <p className="mt-2 text-sm leading-relaxed" style={{ color: '#B7C2E6', maxWidth: 640 }}>
          재료 교체부터 굽힘 응력 반영·메시 변환·해석 설정까지 — 모든 기능을 Claude 같은 AI에서 자연어로 호출할 수 있습니다.
          소수의 MCP 도구가 전체 기능을 감싸므로, 기능이 늘어도 같은 방식으로 바로 쓸 수 있습니다.
        </p>
        <div
          className="mono mt-4 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-[12.5px]"
          style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(143,160,240,0.3)', color: '#DDE4FF' }}
        >
          <span style={{ color: '#8592BC' }}>mcp ▸</span> run_operation(<b style={{ color: '#7FE0A0' }}>"matdb"</b>, {'{'} materials: […] {'}'})
        </div>
        <div className="mt-5 flex flex-wrap gap-6">
          {[
            [data?.length ?? '—', '기능 (op)'],
            [22, 'MCP 도구'],
            [525, '재료 DB'],
            [3, 'CLI · 웹 · MCP'],
          ].map(([n, l]) => (
            <div key={l as string}>
              <div className="mono text-xl font-extrabold tabular-nums">{n}</div>
              <div className="mono text-[11px] uppercase tracking-wide" style={{ color: '#8FA0F0' }}>{l}</div>
            </div>
          ))}
        </div>
        <div className="mt-5 h-1 rounded-full" style={{ background: 'linear-gradient(90deg,#2E5BFF,#23A7D6,#46C36A,#F4C33E,#F6883E,#E8402C)' }} />
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder="기능 검색 — 재료, 굽힘, 메시, prestress…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <span className="mono text-xs text-muted whitespace-nowrap"><b className="text-fg">{shown}</b> 개 기능</span>
      </div>

      {isLoading ? (
        <div className="p-10 text-center"><Spinner /></div>
      ) : (
        <div className="space-y-6">
          {groups.map(([cat, ops]) => (
            <div key={cat}>
              <h2 className="text-sm font-semibold text-muted mb-2">
                {CAT_LABEL[cat] ?? cat} ({ops.length})
              </h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {ops.map((o) => (
                  <Card
                    key={o.name}
                    className="cursor-pointer hover:border-primary transition"
                    onClick={() => setSel(o.name)}
                  >
                    <CardBody className="py-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Box size={14} style={{ color: HOT_CATS.has(o.category) ? '#FF5A3C' : undefined }} className={HOT_CATS.has(o.category) ? '' : 'text-primary'} />
                        <code className="text-sm font-medium">{o.name}</code>
                        <span className="ml-auto inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide mono" style={{ color: '#1E9E63', border: '1px solid rgba(30,158,99,0.4)' }}>
                          MCP
                        </span>
                        {o.requires_gmsh && <Badge tone="canceled">gmsh</Badge>}
                      </div>
                      <p className="text-xs text-muted line-clamp-2">{KO[o.name] ?? o.summary}</p>
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
                <span className="ml-auto inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide mono" style={{ color: '#1E9E63', border: '1px solid rgba(30,158,99,0.4)' }}>MCP</span>
              </div>
              {KO[data.name] && <p className="text-sm mb-1">{KO[data.name]}</p>}
              <p className="text-sm text-muted mb-3">{data.description}</p>
              <div className="mono text-[11px] text-muted mb-3 rounded-md p-2" style={{ background: 'var(--tw-prose-pre-bg,rgba(127,127,127,0.06))' }}>
                run_operation("{data.name}", {'{'} … {'}'})  <span className="opacity-60">· MCP로 동일 호출</span>
              </div>
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
