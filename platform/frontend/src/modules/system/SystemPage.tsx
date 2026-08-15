import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, Database, Cpu, Box, Boxes, ShieldCheck, ShieldOff,
  UserPlus, UserX, Check, X, Copy, Plug, Terminal, Monitor, ListChecks,
} from 'lucide-react'
import { api, unwrap, errorMessage } from '@/shared/api/client'
import { Badge, Card, CardBody, CardHeader, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { cn } from '@/shared/lib/cn'

// ---- API response shapes (from /system/status & /system/capabilities) ----
type SystemStatus = {
  version: string
  env: string
  api: { ok: boolean; port: number }
  database: { ok: boolean }
  worker: { concurrency: number; queued: number; running: number }
  binary: { present: boolean; path: string }
  gmsh: { available: boolean; note?: string }
  mcp: { port: number; url: string }
  rate_limit: { enabled: boolean }
  signup: { enabled: boolean }
  operations: number
}
type ParityRow = { feature: string; web: boolean; mcp: boolean; note?: string }
type Capabilities = {
  operations: number
  mcp_tools?: number
  parity: ParityRow[]
  mcp_add_hint: string
  mcp_desktop_hint: string
}

const getStatus = async () => unwrap<SystemStatus>((await api.get('/system/status')).data)
const getCapabilities = async () => unwrap<Capabilities>((await api.get('/system/capabilities')).data)

// ---- small presentational helpers ----
function OkBadge({ ok, on = '정상', off = '오류' }: { ok: boolean; on?: string; off?: string }) {
  return (
    <Badge tone={ok ? 'succeeded' : 'failed'}>
      {ok ? <Check size={11} className="mr-0.5" /> : <X size={11} className="mr-0.5" />}
      {ok ? on : off}
    </Badge>
  )
}

function StatCard({
  icon, label, value, badge,
}: { icon: React.ReactNode; label: string; value?: React.ReactNode; badge?: React.ReactNode }) {
  return (
    <Card>
      <CardBody className="flex items-start gap-3">
        <div className="text-muted mt-0.5">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-muted">{label}</div>
          {value !== undefined && <div className="text-lg font-semibold leading-tight mt-0.5 truncate">{value}</div>}
          {badge && <div className="mt-1.5">{badge}</div>}
        </div>
      </CardBody>
    </Card>
  )
}

function CopyBtn({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  const onCopy = async () => {
    try { await navigator.clipboard.writeText(text) } catch { return }
    setDone(true)
    if (timer.current) clearTimeout(timer.current)  // reset, don't orphan, on rapid re-copy
    timer.current = setTimeout(() => setDone(false), 1500)
  }
  return (
    <button
      type="button"
      onClick={onCopy}
      className="inline-flex items-center gap-1 shrink-0 rounded-md border border-border px-2.5 h-8 text-xs font-medium hover:bg-surface transition"
    >
      {done ? <Check size={13} className="text-success" /> : <Copy size={13} />}
      {done ? '복사됨' : '복사'}
    </button>
  )
}

function ConnectBlock({ icon, title, cmd }: { icon: React.ReactNode; title: string; cmd: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted mb-1.5">{icon}{title}</div>
      <div className="flex items-start gap-2">
        <code className="flex-1 mono text-xs bg-bg rounded-md px-3 py-2 break-all whitespace-pre-wrap">{cmd}</code>
        <CopyBtn text={cmd} />
      </div>
    </div>
  )
}

export function SystemPage() {
  const status = useQuery({ queryKey: ['system', 'status'], queryFn: getStatus, refetchInterval: 3000 })
  const caps = useQuery({ queryKey: ['system', 'capabilities'], queryFn: getCapabilities })

  const s = status.data
  const c = caps.data

  return (
    <div>
      <PageHeader
        title="시스템 상태"
        desc="플랫폼 헬스 · 웹/MCP 기능 패리티 · Claude 연결 방법."
        actions={
          s && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <Badge tone="default">{s.env}</Badge>
              <span className="mono">v{s.version}</span>
            </div>
          )
        }
      />

      {/* ---------- Health cards ---------- */}
      {status.isLoading ? (
        <div className="p-10 text-center"><Spinner /></div>
      ) : status.isError ? (
        <Card className="mb-6 border-danger">
          <CardBody className="text-sm text-danger">상태를 불러오지 못했습니다: {errorMessage(status.error)}</CardBody>
        </Card>
      ) : s ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-7">
          <StatCard
            icon={<Activity size={20} />}
            label={`API · :${s.api.port}`}
            badge={<OkBadge ok={s.api.ok} />}
          />
          <StatCard
            icon={<Database size={20} />}
            label="데이터베이스"
            badge={<OkBadge ok={s.database.ok} on="연결됨" off="끊김" />}
          />
          <StatCard
            icon={<Cpu size={20} />}
            label={`워커 · 동시 ${s.worker.concurrency}`}
            value={
              <span className="flex items-center gap-2 text-base">
                <span className="text-primary">{s.worker.running}</span><span className="text-muted text-xs font-normal">실행</span>
                <span className="text-muted">·</span>
                <span>{s.worker.queued}</span><span className="text-muted text-xs font-normal">대기</span>
              </span>
            }
            badge={
              status.isFetching
                ? <span className="inline-flex items-center gap-1 text-[11px] text-muted"><Spinner className="h-3 w-3" /> 실시간</span>
                : <span className="text-[11px] text-muted">실시간 (3s)</span>
            }
          />
          <StatCard
            icon={<ListChecks size={20} />}
            label="오퍼레이션"
            value={s.operations}
          />
          <StatCard
            icon={<Box size={20} />}
            label="바이너리"
            value={<span className="mono text-xs text-muted block truncate" title={s.binary.path}>{s.binary.path || '—'}</span>}
            badge={<OkBadge ok={s.binary.present} on="존재" off="없음" />}
          />
          <StatCard
            icon={<Boxes size={20} />}
            label="gmsh"
            value={s.gmsh.note ? <span className="text-xs text-muted block truncate" title={s.gmsh.note}>{s.gmsh.note}</span> : undefined}
            badge={<OkBadge ok={s.gmsh.available} on="사용 가능" off="미설치" />}
          />
          <StatCard
            icon={s.rate_limit.enabled ? <ShieldCheck size={20} /> : <ShieldOff size={20} />}
            label="Rate limit"
            badge={<Badge tone={s.rate_limit.enabled ? 'succeeded' : 'default'}>{s.rate_limit.enabled ? '활성' : '비활성'}</Badge>}
          />
          <StatCard
            icon={s.signup.enabled ? <UserPlus size={20} /> : <UserX size={20} />}
            label="회원가입"
            badge={<Badge tone={s.signup.enabled ? 'succeeded' : 'default'}>{s.signup.enabled ? '허용' : '차단'}</Badge>}
          />
        </div>
      ) : null}

      {/* ---------- Parity matrix ---------- */}
      <Card className="mb-6">
        <CardHeader className="flex items-center justify-between">
          <span className="font-medium text-sm">웹 / MCP 기능 패리티</span>
          {c && (
            <span className="flex items-center gap-2 text-xs text-muted">
              <Badge tone="default">오퍼레이션 {c.operations}</Badge>
              <Badge tone="running">{c.mcp_tools != null ? `MCP 도구 ${c.mcp_tools}` : "MCP 도구"}</Badge>
            </span>
          )}
        </CardHeader>
        <CardBody className="p-0">
          {caps.isLoading ? (
            <div className="p-6 text-center"><Spinner /></div>
          ) : caps.isError ? (
            <div className="p-4 text-sm text-danger">패리티 정보를 불러오지 못했습니다: {errorMessage(caps.error)}</div>
          ) : !c?.parity.length ? (
            <div className="p-6 text-sm text-muted text-center">패리티 정보가 없습니다.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs text-muted border-b border-border">
                <tr>
                  <th className="text-left p-3 font-medium">기능</th>
                  <th className="p-3 font-medium w-16 text-center">웹</th>
                  <th className="p-3 font-medium w-16 text-center">MCP</th>
                  <th className="text-left p-3 font-medium">비고</th>
                </tr>
              </thead>
              <tbody>
                {c.parity.map((r) => (
                  <tr key={r.feature} className="border-b border-border last:border-0">
                    <td className="p-3 font-medium">{r.feature}</td>
                    <td className="p-3 text-center"><MarkCell on={r.web} /></td>
                    <td className="p-3 text-center"><MarkCell on={r.mcp} /></td>
                    <td className="p-3 text-xs text-muted">{r.note ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {/* ---------- Claude connect ---------- */}
      <Card>
        <CardHeader className="flex items-center gap-1.5 font-medium text-sm">
          <Plug size={15} /> Claude 연결
        </CardHeader>
        <CardBody className="space-y-4">
          {caps.isLoading ? (
            <Spinner />
          ) : caps.isError ? (
            <div className="text-sm text-danger">연결 정보를 불러오지 못했습니다: {errorMessage(caps.error)}</div>
          ) : c ? (
            <>
              <ConnectBlock icon={<Terminal size={13} />} title="Claude Code" cmd={c.mcp_add_hint} />
              <ConnectBlock icon={<Monitor size={13} />} title="Claude Desktop" cmd={c.mcp_desktop_hint} />
              <p className="text-xs text-muted">
                연결 후 MCP 도구를 Claude에서 바로 사용할 수 있습니다.
                토큰 발급은 <span className="font-medium text-fg">MCP 토큰</span> 메뉴에서 진행하세요.
              </p>
            </>
          ) : (
            <div className="text-sm text-muted">연결 정보를 불러오지 못했습니다.</div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function MarkCell({ on }: { on: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded-full',
        on ? 'bg-success/15 text-success' : 'bg-muted/10 text-muted',
      )}
      aria-label={on ? '지원' : '미지원'}
    >
      {on ? <Check size={14} /> : <X size={14} />}
    </span>
  )
}
