import { useState } from 'react'
import { Boxes } from 'lucide-react'
import { useAuth } from '@/shared/auth/AuthContext'
import { Button, Card, CardBody, Input, Label } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('admin@kooremapper.local')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setBusy(true)
    try {
      await login(email, password)
    } catch (x) {
      setErr(errorMessage(x))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid place-items-center">
      <Card className="w-80">
        <CardBody>
          <div className="flex items-center gap-2 mb-5">
            <Boxes className="text-primary" />
            <span className="font-semibold text-lg">KooRemapper</span>
          </div>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <Label>이메일</Label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            </div>
            <div>
              <Label>비밀번호</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            {err && <div className="text-xs text-danger">{err}</div>}
            <Button type="submit" variant="primary" className="w-full" disabled={busy}>
              {busy ? '로그인 중…' : '로그인'}
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
