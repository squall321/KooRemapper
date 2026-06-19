import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { UserPlus, KeyRound, ShieldCheck, ShieldOff, Power, PowerOff } from 'lucide-react'
import { api, unwrap, errorMessage } from '@/shared/api/client'
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Label, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { fmtDate } from '@/shared/lib/cn'
import { useAuth } from '@/shared/auth/AuthContext'

interface AdminUser {
  id: number
  email: string
  display_name: string | null
  is_system_admin: boolean
  is_active: boolean
  created_at: string
  session_count: number
}

const USERS_KEY = ['admin', 'users'] as const

async function fetchUsers(): Promise<AdminUser[]> {
  const { data } = await api.get('/admin/users', { params: { limit: 200, offset: 0 } })
  return unwrap<AdminUser[]>(data)
}

// ── Modal shell ─────────────────────────────────────────────────────────────
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <Card className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="font-medium text-sm">{title}</CardHeader>
        <CardBody className="space-y-3">{children}</CardBody>
      </Card>
    </div>
  )
}

// ── 새 사용자 ────────────────────────────────────────────────────────────────
function CreateUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/admin/users', {
        email,
        password,
        display_name: displayName || undefined,
        is_system_admin: isAdmin,
      })
      return unwrap<AdminUser>(data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USERS_KEY })
      onClose()
    },
    onError: (e) => setErr(errorMessage(e)),
  })

  const valid = email.trim().length > 0 && password.length > 0

  return (
    <Modal title="새 사용자" onClose={onClose}>
      <div className="space-y-1">
        <Label>이메일</Label>
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" autoFocus />
      </div>
      <div className="space-y-1">
        <Label>비밀번호</Label>
        <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="초기 비밀번호" />
      </div>
      <div className="space-y-1">
        <Label>표시 이름 (선택)</Label>
        <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="홍길동" />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
        시스템 관리자 권한 부여
      </label>
      {err && <div className="text-sm text-danger">{err}</div>}
      <div className="flex justify-end gap-2 pt-1">
        <Button size="sm" variant="ghost" onClick={onClose}>취소</Button>
        <Button size="sm" variant="primary" disabled={!valid || create.isPending} onClick={() => { setErr(null); create.mutate() }}>
          {create.isPending ? <Spinner /> : <UserPlus size={14} />} 생성
        </Button>
      </div>
    </Modal>
  )
}

// ── 비밀번호 재설정 ──────────────────────────────────────────────────────────
function ResetPasswordModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const reset = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/admin/users/${user.id}/password`, { new_password: password })
      return unwrap<unknown>(data)
    },
    onSuccess: () => setDone(true),
    onError: (e) => setErr(errorMessage(e)),
  })

  return (
    <Modal title={`비밀번호 재설정 — ${user.email}`} onClose={onClose}>
      {done ? (
        <>
          <div className="text-sm text-success">비밀번호가 재설정되었습니다.</div>
          <div className="flex justify-end pt-1">
            <Button size="sm" onClick={onClose}>닫기</Button>
          </div>
        </>
      ) : (
        <>
          <div className="space-y-1">
            <Label>새 비밀번호</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="새 비밀번호" autoFocus />
          </div>
          {err && <div className="text-sm text-danger">{err}</div>}
          <div className="flex justify-end gap-2 pt-1">
            <Button size="sm" variant="ghost" onClick={onClose}>취소</Button>
            <Button size="sm" variant="primary" disabled={!password || reset.isPending} onClick={() => { setErr(null); reset.mutate() }}>
              {reset.isPending ? <Spinner /> : <KeyRound size={14} />} 재설정
            </Button>
          </div>
        </>
      )}
    </Modal>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const { data, isLoading, isError, error } = useQuery({ queryKey: USERS_KEY, queryFn: fetchUsers })
  const [creating, setCreating] = useState(false)
  const [resetFor, setResetFor] = useState<AdminUser | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const patch = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Partial<Pick<AdminUser, 'is_active' | 'is_system_admin'>> }) => {
      const { data } = await api.patch(`/admin/users/${id}`, body)
      return unwrap<AdminUser>(data)
    },
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: USERS_KEY }) },
    onError: (e) => setErr(errorMessage(e)),
  })

  const toggleActive = (u: AdminUser) => {
    const next = !u.is_active
    if (!window.confirm(`${u.email} 계정을 ${next ? '활성화' : '비활성화'}하시겠습니까?`)) return
    setErr(null)
    patch.mutate({ id: u.id, body: { is_active: next } })
  }

  const toggleAdmin = (u: AdminUser) => {
    const next = !u.is_system_admin
    if (!window.confirm(`${u.email} 의 관리자 권한을 ${next ? '부여' : '회수'}하시겠습니까?`)) return
    setErr(null)
    patch.mutate({ id: u.id, body: { is_system_admin: next } })
  }

  return (
    <div>
      <PageHeader
        title="사용자 관리"
        desc="시스템 사용자 계정을 생성하고 권한·활성 상태를 관리합니다."
        actions={<Button variant="primary" onClick={() => setCreating(true)}><UserPlus size={16} /> 새 사용자</Button>}
      />

      {err && <div className="text-sm text-danger mb-3">{err}</div>}

      <Card>
        <CardHeader className="font-medium text-sm">사용자 목록</CardHeader>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="p-6 text-center"><Spinner /></div>
          ) : isError ? (
            <EmptyState title="사용자 목록을 불러오지 못했습니다" hint={errorMessage(error)} />
          ) : !data?.length ? (
            <EmptyState title="사용자가 없습니다" />
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs text-muted border-b border-border">
                <tr>
                  <th className="text-left p-3 font-medium">이메일</th>
                  <th className="text-left p-3 font-medium">이름</th>
                  <th className="text-left p-3 font-medium">권한</th>
                  <th className="text-left p-3 font-medium">상태</th>
                  <th className="text-left p-3 font-medium">세션</th>
                  <th className="text-left p-3 font-medium">생성일</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((u) => {
                  const isSelf = me?.id === u.id
                  const busy = patch.isPending && patch.variables?.id === u.id
                  return (
                    <tr key={u.id} className="border-b border-border last:border-0">
                      <td className="p-3">
                        {u.email}
                        {isSelf && <span className="ml-1.5 text-[11px] text-muted">(나)</span>}
                      </td>
                      <td className="p-3 text-muted">{u.display_name || '—'}</td>
                      <td className="p-3">
                        <Badge tone={u.is_system_admin ? 'running' : 'default'}>{u.is_system_admin ? 'admin' : 'user'}</Badge>
                      </td>
                      <td className="p-3">
                        <Badge tone={u.is_active ? 'succeeded' : 'failed'}>{u.is_active ? '활성' : '비활성'}</Badge>
                      </td>
                      <td className="p-3 text-muted">{u.session_count}</td>
                      <td className="p-3 text-xs text-muted">{fmtDate(u.created_at)}</td>
                      <td className="p-3">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" disabled={busy} title={u.is_system_admin ? '관리자 권한 회수' : '관리자 권한 부여'} onClick={() => toggleAdmin(u)}>
                            {u.is_system_admin ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
                          </Button>
                          <Button size="sm" variant="ghost" disabled={busy || isSelf} title={isSelf ? '본인 계정은 비활성화할 수 없습니다' : u.is_active ? '비활성화' : '활성화'} onClick={() => toggleActive(u)}>
                            {u.is_active ? <PowerOff size={14} /> : <Power size={14} />}
                          </Button>
                          <Button size="sm" variant="ghost" title="비밀번호 재설정" onClick={() => setResetFor(u)}>
                            <KeyRound size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {creating && <CreateUserModal onClose={() => setCreating(false)} />}
      {resetFor && <ResetPasswordModal user={resetFor} onClose={() => setResetFor(null)} />}
    </div>
  )
}
