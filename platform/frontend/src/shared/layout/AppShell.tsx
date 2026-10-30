import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Boxes, FolderOpen, LayoutDashboard, KeyRound, BookOpen, Moon, Sun, LogOut, Activity, UserCog, Users, Network } from 'lucide-react'
import { ontologyState } from '@/shared/api/endpoints'
import { useAuth } from '@/shared/auth/AuthContext'
import { useTheme } from '@/shared/theme/ThemeContext'
import { cn } from '@/shared/lib/cn'

const nav = [
  { to: '/', label: '대시보드', icon: LayoutDashboard, end: true },
  { to: '/sessions', label: '세션', icon: FolderOpen },
  { to: '/operations', label: '기능 · 도구', icon: BookOpen },
  { to: '/system', label: '시스템 상태', icon: Activity },
  { to: '/tokens', label: 'MCP 토큰', icon: KeyRound },
  { to: '/account', label: '내 계정', icon: UserCog },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  // 과제·개정 기능이 꺼져 있으면 메뉴도 **없어진다**(개정 패널과 같은 규율 — 포탈 옵션이 정한다)
  const onto = useQuery({ queryKey: ['ontology-state'], queryFn: ontologyState, staleTime: 60_000, enabled: !!user })
  const base = onto.data?.enabled
    ? [...nav.slice(0, 3), { to: '/ontology', label: '온톨로지', icon: Network }, ...nav.slice(3)]
    : nav
  const items = user?.is_system_admin
    ? [...base, { to: '/admin/users', label: '사용자 관리', icon: Users }]
    : base
  return (
    <div className="flex h-full">
      <aside className="w-56 shrink-0 border-r border-border bg-surface flex flex-col">
        <div className="px-4 h-14 flex items-center gap-2 border-b border-border">
          <Boxes className="text-primary" size={20} />
          <span className="font-semibold">KooRemapper</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition',
                  isActive ? 'bg-primary/15 text-primary font-medium' : 'text-muted hover:bg-bg hover:text-fg',
                )
              }
            >
              <n.icon size={16} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-2 border-t border-border space-y-1">
          <button onClick={toggle} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted hover:bg-bg hover:text-fg">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            {theme === 'dark' ? '라이트 모드' : '다크 모드'}
          </button>
          <div className="px-3 py-1 text-xs text-muted truncate">{user?.email}</div>
          <button onClick={logout} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted hover:bg-bg hover:text-fg">
            <LogOut size={16} /> 로그아웃
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
