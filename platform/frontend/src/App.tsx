import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '@/shared/auth/AuthContext'
import { AppShell } from '@/shared/layout/AppShell'
import { Spinner } from '@/shared/ui/ui'
import { LoginPage } from '@/modules/auth/LoginPage'
import { DashboardPage } from '@/modules/dashboard/DashboardPage'
import { SessionsPage } from '@/modules/sessions/SessionsPage'
import { SessionDetailPage } from '@/modules/sessions/SessionDetailPage'
import { OperationsPage } from '@/modules/operations/OperationsPage'
import { TokensPage } from '@/modules/tokens/TokensPage'
import { AccountPage } from '@/modules/account/AccountPage'
import { SystemPage } from '@/modules/system/SystemPage'
import { UsersPage } from '@/modules/admin/UsersPage'

export function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="h-full grid place-items-center text-muted">
        <Spinner className="text-primary" />
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/sessions/:id" element={<SessionDetailPage />} />
        <Route path="/operations" element={<OperationsPage />} />
        <Route path="/tokens" element={<TokensPage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/account" element={<AccountPage />} />
        {user.is_system_admin && <Route path="/admin/users" element={<UsersPage />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
