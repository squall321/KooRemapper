// 허브에서 받은 기준정보를 읽기 전용으로 보는 화면 — 타입 · 객체 목록 · 한 객체(칸 · 상태 · 옛 식별자 · 선)
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, GitMerge, History } from 'lucide-react'

import {
  ontologyObject, ontologyObjects, ontologyState, ontologyTypes,
  type OntoEdge, type OntoObjectRow, type OntoState, type OntoTypeOut,
} from '@/shared/api/endpoints'
import { errorMessage } from '@/shared/api/client'
import { PageHeader } from '@/shared/components/PageHeader'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Select, Spinner } from '@/shared/ui/ui'
import { cn } from '@/shared/lib/cn'

const PAGE = 100
const STATES: { value: OntoState; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'active', label: '활성' },
  { value: 'deprecated', label: '그만 씀' },
  { value: 'inactive', label: '사용 안 함' },
]

/** 사라진 것은 지우지 않고 「사용 안 함」, 그만 씀은 그것과 **구별해** 보인다(사용자 결정 10-30 — 지시서 기본안). */
function StateBadge({ o }: { o: Pick<OntoObjectRow, 'active' | 'hidden' | 'status' | 'merged_into'> }) {
  if (!o.active) {
    return <Badge tone="default">{o.hidden ? '안 보이게 됨' : o.merged_into ? '합쳐짐' : '사용 안 함'}</Badge>
  }
  if (o.status === 'deprecated') return <Badge tone="canceled">그만 씀</Badge>
  return <Badge tone="succeeded">활성</Badge>
}

function show(v: unknown): string {
  if (v == null) return '—'
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'object' ? JSON.stringify(x) : String(x))).join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** 정본은 허브다 — 여기에는 고치는 길이 없다. 우리 것(개발 개정)도 같은 표에 살아 함께 보인다(`source`). */
export function OntologyPage() {
  const feat = useQuery({ queryKey: ['ontology-state'], queryFn: ontologyState, staleTime: 60_000 })
  const on = feat.data?.enabled === true
  const [params, setParams] = useSearchParams()
  const [draft, setDraft] = useState('')
  const [q, setQ] = useState('')
  const [state, setState] = useState<OntoState>('all')
  const [offset, setOffset] = useState(0)

  const types = useQuery({ queryKey: ['onto-types'], queryFn: ontologyTypes, enabled: on })
  const list = types.data?.types ?? []
  const type = params.get('type') || list.find((t) => t.counts.total)?.slug || list[0]?.slug || ''
  const key = params.get('key') ?? ''
  const objects = useQuery({
    queryKey: ['onto-objects', type, q, state, offset],
    queryFn: () => ontologyObjects({ type, q, state, limit: PAGE, offset }),
    enabled: on && !!type,
  })

  const open = (t: string, k?: string) => {
    if (t !== type) { setOffset(0); setQ(''); setDraft('') }
    setParams(k ? { type: t, key: k } : { type: t })
  }
  const known = new Set(list.map((t) => t.slug))

  if (feat.isLoading) return <div className="p-10 text-center"><Spinner /></div>
  return (
    <div>
      <PageHeader title="온톨로지"
                  desc="SP 허브에서 받은 기준정보 — 읽기 전용입니다(정본은 허브). 사라진 것은 지우지 않고 「사용 안 함」 으로 둡니다." />
      {!on ? (
        <Card><CardBody className="text-sm text-warning">과제·개정 기능이 꺼져 있다 — {feat.data?.reason}</CardBody></Card>
      ) : types.isError ? (
        <Card><CardBody className="text-sm text-danger">타입을 읽지 못했다 — {errorMessage(types.error)}</CardBody></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-[15rem_minmax(0,1fr)]">
          <Card className="self-start">
            <CardHeader className="text-sm font-medium">타입</CardHeader>
            <CardBody className="p-1">
              {types.isLoading ? <div className="p-3"><Spinner /></div> : !list.length ? (
                <EmptyState title="받은 것이 없다" hint="허브 받기가 아직 한 번도 돌지 않았다" />
              ) : list.map((t) => (
                <button key={t.slug} type="button" onClick={() => open(t.slug)}
                        className={cn('w-full rounded-md px-2.5 py-1.5 text-left text-xs transition',
                                      t.slug === type ? 'bg-primary/15 text-primary' : 'hover:bg-bg')}>
                  <div className="font-medium truncate">{t.label || t.slug}
                    {t.source === 'dynaforge' && <span className="ml-1 text-muted font-normal">(우리 것)</span>}
                  </div>
                  <div className="text-muted mono">{t.slug}</div>
                  <div className="text-muted">
                    활성 {t.counts.active ?? 0}
                    {!!t.counts.deprecated && <> · 그만 씀 {t.counts.deprecated}</>}
                    {!!t.counts.inactive && <> · 사용 안 함 {t.counts.inactive}</>}
                  </div>
                </button>
              ))}
            </CardBody>
          </Card>

          <div className="space-y-4 min-w-0">
            {type && (
              <Card>
                <CardHeader className="flex items-center gap-2 flex-wrap">
                  <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); setOffset(0); setQ(draft.trim()) }}>
                    <div className="w-56"><Input value={draft} onChange={(e) => setDraft(e.target.value)}
                                                 placeholder="key · 이름 일부 (Enter)" className="h-8 text-xs" /></div>
                  </form>
                  <div className="w-32">
                    <Select value={state} className="h-8 text-xs"
                            onChange={(e) => { setOffset(0); setState(e.target.value as OntoState) }}>
                      {STATES.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                    </Select>
                  </div>
                  {objects.data && (
                    <span className="ml-auto text-xs text-muted">
                      {objects.data.total ? `${offset + 1}–${offset + objects.data.items.length}` : 0} / {objects.data.total}
                    </span>
                  )}
                </CardHeader>
                <CardBody className="p-0">
                  {objects.isLoading ? <div className="p-6 text-center"><Spinner /></div>
                    : objects.isError ? <div className="p-4 text-sm text-danger">{errorMessage(objects.error)}</div>
                    : !objects.data?.items.length ? <EmptyState title="없다" hint={q ? `「${q}」 에 걸린 것이 없다` : undefined} />
                    : (
                      <table className="w-full text-xs">
                        <tbody>
                          {objects.data.items.map((o) => (
                            <tr key={o.key} onClick={() => open(type, o.key)}
                                className={cn('border-b border-border last:border-0 cursor-pointer hover:bg-bg',
                                              o.key === key && 'bg-primary/10')}>
                              <td className="px-3 py-1.5 mono">{o.key}</td>
                              <td className="px-3 py-1.5">{o.label}</td>
                              <td className="px-3 py-1.5 text-right whitespace-nowrap"><StateBadge o={o} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  {objects.data && objects.data.total > PAGE && (
                    <div className="flex justify-end gap-2 p-2 border-t border-border">
                      <Button size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>이전</Button>
                      <Button size="sm" disabled={offset + PAGE >= objects.data.total} onClick={() => setOffset(offset + PAGE)}>다음</Button>
                    </div>
                  )}
                </CardBody>
              </Card>
            )}
            {type && key && <ObjectCard type={type} objKey={key} def={list.find((t) => t.slug === type)}
                                        rels={types.data?.relation_types ?? []} known={known} open={open} />}
          </div>
        </div>
      )}
    </div>
  )
}

function ObjectCard({ type, objKey, def, rels, known, open }: {
  type: string; objKey: string; def?: OntoTypeOut
  rels: { slug: string; label: string; inverse_label: string }[]
  known: Set<string>; open: (t: string, k?: string) => void
}) {
  const one = useQuery({ queryKey: ['onto-object', type, objKey], queryFn: () => ontologyObject(type, objKey) })
  if (one.isLoading) return <Card><CardBody><Spinner /></CardBody></Card>
  if (one.isError) return <Card><CardBody className="text-sm text-danger">{errorMessage(one.error)}</CardBody></Card>
  const d = one.data
  if (!d) return null
  if (!d.object) {
    // 옛 식별자로 물었다 — 「없다」 가 아니라 지금 것을 알려 준다
    return (
      <Card><CardBody className="text-sm flex items-center gap-2 flex-wrap">
        <History size={14} className="text-muted" />
        <span><b className="mono">{objKey}</b> 는 허브에서 <b className="mono">{d.renamed_to}</b> 로 바뀌었다</span>
        {d.renamed_to && <Button size="sm" onClick={() => open(type, d.renamed_to)}>그리로 가기</Button>}
      </CardBody></Card>
    )
  }
  const o = d.object
  const propDef = new Map((def?.properties ?? []).map((p) => [p.key, p]))
  const relLabel = (slug: string, inbound: boolean) => {
    const r = rels.find((x) => x.slug === slug)
    return (inbound ? r?.inverse_label : r?.label) || slug
  }
  const end = (e: OntoEdge) => known.has(e.type)
    ? <button type="button" className="mono text-primary hover:underline" onClick={() => open(e.type, e.key)}>{e.key}</button>
    : <span className="mono">{e.key}</span>       // 리포트 같은 우리 1급 표는 이 화면 밖이다
  const edges = (rows: OntoEdge[], inbound: boolean) => rows.map((e, i) => (
    <div key={`${e.relation}:${e.type}:${e.key}:${i}`} className="flex items-center gap-1.5 flex-wrap" title={e.evidence_note ?? ''}>
      <span className="text-muted">{relLabel(e.relation, inbound)}</span>
      {inbound ? <ArrowLeft size={11} className="text-muted" /> : <ArrowRight size={11} className="text-muted" />}
      {end(e)}
      {e.label && <span className="text-muted">{e.label}</span>}
      <span className="text-muted">· {e.type}</span>
      {e.source !== 'hub' && <Badge tone="default">우리 것</Badge>}
      {e.evidence_note && <span className="text-muted italic truncate max-w-[16rem]">— {e.evidence_note}</span>}
    </div>
  ))
  return (
    <Card>
      <CardHeader className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-sm">{o.label || o.key}</span>
        <span className="mono text-xs text-muted">{o.type} · {o.key}</span>
        <StateBadge o={o} />
        {o.source !== 'hub' && <Badge tone="default">우리 것</Badge>}
      </CardHeader>
      <CardBody className="space-y-3 text-xs">
        {o.merged_into && (
          <div className="flex items-center gap-1.5 text-warning">
            <GitMerge size={12} /> 허브에서 합쳐졌다 →
            {d.merged_into_now && known.has(type)
              ? <button type="button" className="mono text-primary hover:underline" onClick={() => open(type, d.merged_into_now!)}>{d.merged_into_now}</button>
              : <span className="mono">{d.merged_into_now ?? o.merged_into}</span>}
          </div>
        )}
        {!!d.previous.length && (
          <div className="text-muted">옛 식별자 — <span className="mono">{d.previous.join(', ')}</span></div>
        )}
        {Object.keys(o.properties).length ? (
          <table className="w-full">
            <tbody>
              {Object.entries(o.properties).map(([k, v]) => {
                const p = propDef.get(k)
                const ref = p?.ref_type_slug && typeof v === 'string' && known.has(p.ref_type_slug)
                return (
                  <tr key={k} className="border-t border-border align-top">
                    <td className="py-1 pr-3 text-muted whitespace-nowrap">{p?.label || k}</td>
                    <td className="py-1 break-all">
                      {ref
                        ? <button type="button" className="mono text-primary hover:underline" onClick={() => open(p!.ref_type_slug!, v as string)}>{v as string}</button>
                        : show(v)}
                      {p?.unit && <span className="text-muted"> {p.unit}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : <div className="text-muted">칸이 없다</div>}
        {!!d.out.length && <div className="space-y-1"><div className="font-medium">나가는 선</div>{edges(d.out, false)}</div>}
        {!!d.in.length && <div className="space-y-1"><div className="font-medium">들어오는 선</div>{edges(d.in, true)}</div>}
        <div className="text-muted">허브 갱신 {o.updated_at ?? '—'} · 받은 때 {new Date(o.synced_at).toLocaleString()}</div>
      </CardBody>
    </Card>
  )
}
