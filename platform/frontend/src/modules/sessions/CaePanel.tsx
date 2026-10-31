// 리포트에 실은 해석 온톨로지(후처리 꾸러미 — 파트 판정 · 하중 경로 상위 · 경고)를 보이고 꾸러미를 붙이는 칸
import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Network, Upload } from 'lucide-react'

import { attachCae, reportCae, type CaeLoadPath, type CaePart } from '@/shared/api/endpoints'
import { Badge, Button, Spinner } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'
import { identityLabel } from './caseIdentity'

const TOP = 8

function fmt(n: number | null | undefined, d = 1): string {
  return n == null ? '—' : Number(n).toFixed(d)
}

/** 해석 온톨로지 칸 — 후처리(KooD3plotReader)가 리포트 곁에 낸 꾸러미를 캠페인 수준으로 실은 것(사용자 결정 10-31 (가)).
 *
 *  여기 보이는 파트 판정 · 하중 경로가 리포트를 건너는 질의(`/cae/parts` · `/cae/load-paths` · MCP find_cae_*)가
 *  찾는 바로 그 행이다. 안 실었으면 한 줄로 말하고 붙이는 길을 준다 — 조용히 없어지면 "왜 못 찾나" 를 알 수 없다.
 */
export function CaePanel({ reportId }: { reportId: string }) {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [all, setAll] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const view = useQuery({ queryKey: ['report-cae', reportId], queryFn: () => reportCae(reportId) })
  const attach = useMutation({
    mutationFn: (f: File) => attachCae(reportId, f),
    onSuccess: (r) => {
      setErr(null)
      setNote(r.already ? '이미 실은 꾸러미다 — 바뀐 것이 없다' : null)
      qc.invalidateQueries({ queryKey: ['report-cae', reportId] })
    },
    onError: (e) => { setNote(null); setErr(errorMessage(e)) },
  })

  if (view.isLoading) return <div className="text-xs text-muted"><Spinner /> 해석 온톨로지 확인…</div>
  if (view.isError) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-danger">
        <AlertTriangle size={13} /> 해석 온톨로지를 읽지 못했다 — {errorMessage(view.error)}
      </div>
    )
  }
  const d = view.data
  if (!d) return null

  const picker = (
    <>
      <input ref={inputRef} type="file" accept=".json,application/json" className="hidden"
             onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) attach.mutate(f) }} />
      <Button size="sm" variant="ghost" disabled={attach.isPending} onClick={() => inputRef.current?.click()}>
        {attach.isPending ? <Spinner /> : <Upload size={13} />} {d.loaded ? '꾸러미 다시 싣기' : '꾸러미 붙이기'}
      </Button>
    </>
  )
  const msgs = (
    <>
      {err && <div className="text-xs text-danger">{err}</div>}
      {note && <div className="text-xs text-muted">{note}</div>}
    </>
  )

  if (!d.loaded) {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 flex-wrap text-xs text-muted">
          <Network size={13} /> 해석 온톨로지 없음 — 후처리 꾸러미(&lt;리포트 이름&gt;.ontology.json)를 붙이면 파트 판정 · 하중 경로를 리포트를 건너 찾을 수 있다
          {picker}
        </div>
        {msgs}
      </div>
    )
  }

  const s = d.summary
  // 값이 어휘 단위로 바뀌지 않았으면(values_normalized=false) 단위 표시를 붙이지 않는다 — 모델 단위 그대로라 MPa · N 이 거짓말이 된다
  const raw = d.campaign?.values_normalized === false
  const u = (unit: string) => (raw ? '' : ` (${unit})`)
  const more = d.parts.length > TOP || d.load_paths.length > TOP
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="flex items-center gap-1.5 text-sm font-medium"><Network size={14} /> 해석 온톨로지</span>
        <span className="text-muted">
          어휘 {s.vocabulary?.version ?? '?'} · 파트 {d.parts.length} · 하중 경로 {d.load_paths.length} · 접촉 {d.contacts.length} · 소견 {d.findings.length}
          {s.runs && ` · 런 ${s.runs.matched}/${s.runs.package} 맞음`}
        </span>
        {picker}
      </div>
      {raw && (
        <div className="flex items-center gap-1.5 text-xs text-warning">
          <AlertTriangle size={13} /> 값이 어휘 단위로 바뀌지 않았다 — 모델 단위({d.campaign?.unit_system ?? '?'}) 그대로다
          {d.campaign?.unit_note ? ` · ${d.campaign.unit_note}` : ''}
        </div>
      )}
      {(s.warnings ?? []).map((w, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-warning"><AlertTriangle size={13} /> {w}</div>
      ))}
      {msgs}
      <PartTable parts={all ? d.parts : d.parts.slice(0, TOP)} u={u} />
      <PathTable paths={all ? d.load_paths : d.load_paths.slice(0, TOP)} u={u} />
      {more && (
        <button className="text-xs text-primary" onClick={() => setAll(!all)}>
          {all ? `위 ${TOP}개씩만` : '전부 보기'}
        </button>
      )}
    </div>
  )
}

/** 파트 판정 — 위험한 것부터(서버가 판정 · 최소 안전율 · 최대 응력 순으로 매겨 준다). */
function PartTable({ parts, u }: { parts: CaePart[]; u: (unit: string) => string }) {
  if (!parts.length) return null
  return (
    <div className="overflow-x-auto">
      <div className="text-xs text-muted mb-1">파트 판정 (위험한 것부터)</div>
      <table className="w-full text-[11px]">
        <thead className="text-muted">
          <tr className="text-left">
            <th className="py-1 pr-2">파트</th>
            <th className="py-1 px-2">판정</th>
            <th className="py-1 px-2 text-right">최소 안전율</th>
            <th className="py-1 px-2 text-right">최대 σvm{u('MPa')}</th>
            <th className="py-1 px-2">그 런 (각도/위치)</th>
          </tr>
        </thead>
        <tbody>
          {parts.map((p) => (
            <tr key={p.key} className="border-t border-border">
              <td className="py-1 pr-2 truncate max-w-[220px]" title={p.label}>
                {p.label}{p.part_id != null && <span className="text-muted"> · {p.part_id}</span>}
              </td>
              <td className="py-1 px-2">
                {p.severity && (
                  <Badge tone={p.severity === 'CRITICAL' ? 'failed' : p.severity === 'WARNING' ? 'canceled' : 'default'}>
                    {p.severity}
                  </Badge>
                )}
              </td>
              <td className="py-1 px-2 text-right">
                {fmt(p.min_safety_factor, 2)}
                {p.safety_factor_complete === false && <span className="text-muted" title="안전율을 모든 런에서 재지 못했다">*</span>}
              </td>
              <td className="py-1 px-2 text-right">{fmt(p.worst_von_mises)}</td>
              <td className="py-1 px-2 truncate max-w-[160px]">
                {p.worst_von_mises_run_case ? identityLabel(p.worst_von_mises_run_identity, p.worst_von_mises_run_case) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 하중 경로 — 충격량 큰 것부터. 맞닿은 비율은 런 가운데 두 파트가 실제로 힘을 주고받은 몫이다. */
function PathTable({ paths, u }: { paths: CaeLoadPath[]; u: (unit: string) => string }) {
  if (!paths.length) return null
  return (
    <div className="overflow-x-auto">
      <div className="text-xs text-muted mb-1">하중 경로 (충격량 큰 것부터)</div>
      <table className="w-full text-[11px]">
        <thead className="text-muted">
          <tr className="text-left">
            <th className="py-1 pr-2">파트 ↔ 파트</th>
            <th className="py-1 px-2 text-right">맞닿은 비율</th>
            <th className="py-1 px-2 text-right">최대 충격량{u('N·s')}</th>
            <th className="py-1 px-2 text-right">최대 힘{u('N')}</th>
          </tr>
        </thead>
        <tbody>
          {paths.map((p) => (
            <tr key={p.key} className="border-t border-border">
              <td className="py-1 pr-2 truncate max-w-[260px]" title={p.label}>
                {p.part_a_name ?? '?'} <span className="text-muted">↔</span> {p.part_b_name ?? '?'}
              </td>
              <td className="py-1 px-2 text-right">
                {p.engage_ratio == null ? '—' : `${Math.round(p.engage_ratio * 100)}%`}
                {p.n_runs_engaged != null && <span className="text-muted"> ({p.n_runs_engaged})</span>}
              </td>
              <td className="py-1 px-2 text-right">{fmt(p.impulse_max, 3)}</td>
              <td className="py-1 px-2 text-right">{fmt(p.peak_force_max, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
