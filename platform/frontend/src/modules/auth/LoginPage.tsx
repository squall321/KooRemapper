import { useEffect, useState } from 'react'
import { Boxes } from 'lucide-react'
import { useAuth } from '@/shared/auth/AuthContext'
import { Button, Card, CardBody, Input, Label } from '@/shared/ui/ui'
import { errorMessage } from '@/shared/api/client'
import { getAuthConfig } from '@/shared/api/endpoints'

export function LoginPage() {
  const { login, signup } = useAuth()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [allowSignup, setAllowSignup] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getAuthConfig().then((c) => setAllowSignup(c.allow_signup)).catch(() => {})
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!email || !password) {
      setErr('이메일과 비밀번호를 입력하세요.')
      return
    }
    if (mode === 'signup' && password.length < 8) {
      setErr('비밀번호는 최소 8자 이상이어야 합니다.')
      return
    }
    setBusy(true)
    try {
      if (mode === 'signup') await signup(email, password, displayName || undefined)
      else await login(email, password)
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
            {mode === 'signup' && (
              <div>
                <Label>이름 (선택)</Label>
                <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              </div>
            )}
            <div>
              <Label>비밀번호</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
            </div>
            {err && <div className="text-xs text-danger">{err}</div>}
            <Button type="submit" variant="primary" className="w-full" disabled={busy}>
              {busy ? '처리 중…' : mode === 'signup' ? '회원가입' : '로그인'}
            </Button>
          </form>
          {allowSignup && (
            <button
              className="mt-3 text-xs text-primary w-full text-center"
              onClick={() => { setErr(null); setEmail(''); setPassword(''); setDisplayName(''); setMode(mode === 'login' ? 'signup' : 'login') }}
            >
              {mode === 'login' ? '계정이 없으신가요? 회원가입' : '이미 계정이 있으신가요? 로그인'}
            </button>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
