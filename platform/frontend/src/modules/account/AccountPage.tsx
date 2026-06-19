import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { KeyRound, Mail, ShieldCheck, User as UserIcon } from 'lucide-react'
import { api, errorMessage, unwrap } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { Badge, Button, Card, CardBody, CardHeader, Input, Label, Spinner } from '@/shared/ui/ui'
import { PageHeader } from '@/shared/components/PageHeader'
import { fmtDate } from '@/shared/lib/cn'

async function changePassword(current_password: string, new_password: string): Promise<string> {
  const { data } = await api.post('/me/password', { current_password, new_password })
  return unwrap<string>(data)
}

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 text-muted">{icon}</div>
      <div>
        <div className="text-xs text-muted">{label}</div>
        <div className="text-sm font-medium">{value}</div>
      </div>
    </div>
  )
}

export function AccountPage() {
  const { user } = useAuth()

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const change = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: (msg) => {
      setOk(msg || '비밀번호가 변경되었습니다.')
      setCurrent('')
      setNext('')
      setConfirm('')
    },
    onError: (e) => setErr(errorMessage(e)),
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setOk(null)
    if (!current || !next) {
      setErr('현재 비밀번호와 새 비밀번호를 입력하세요.')
      return
    }
    if (next !== confirm) {
      setErr('새 비밀번호와 확인이 일치하지 않습니다.')
      return
    }
    change.mutate()
  }

  if (!user) {
    return (
      <div>
        <PageHeader title="계정" />
        <div className="p-10 text-center"><Spinner /></div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="계정" desc="내 계정 정보와 비밀번호를 관리합니다." />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="font-medium text-sm">내 정보</CardHeader>
          <CardBody className="space-y-4">
            <Field icon={<Mail size={16} />} label="이메일" value={user.email} />
            <Field icon={<UserIcon size={16} />} label="이름" value={user.display_name || '—'} />
            <Field
              icon={<ShieldCheck size={16} />}
              label="권한"
              value={
                user.is_system_admin
                  ? <Badge tone="running">시스템 관리자</Badge>
                  : <Badge tone="default">일반 사용자</Badge>
              }
            />
            <Field icon={<UserIcon size={16} />} label="가입일" value={<span className="text-muted">{fmtDate(user.created_at)}</span>} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="font-medium text-sm">비밀번호 변경</CardHeader>
          <CardBody>
            <form onSubmit={submit} className="space-y-3">
              <Label className="block">
                현재 비밀번호
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  className="mt-1"
                />
              </Label>
              <Label className="block">
                새 비밀번호
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  className="mt-1"
                />
              </Label>
              <Label className="block">
                새 비밀번호 확인
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="mt-1"
                />
              </Label>

              {err && <div className="text-sm text-danger">{err}</div>}
              {ok && <div className="text-sm text-success">{ok}</div>}

              <Button type="submit" variant="primary" disabled={change.isPending} className="w-full">
                {change.isPending ? <Spinner /> : <KeyRound size={16} />} 비밀번호 변경
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
