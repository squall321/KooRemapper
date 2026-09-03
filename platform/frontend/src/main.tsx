import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '@/shared/auth/AuthContext'
import { ThemeProvider } from '@/shared/theme/ThemeContext'
import { ErrorBoundary } from '@/shared/components/ErrorBoundary'
import { App } from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            {/* 서브패스 배포 대응 — BASE_URL 이 basename 의 기준이되, 실제 주소가 추가
                접두를 이고 있으면(포털 경유 /heax-hub/apps/kooremapper/) 그만큼 앞에
                붙인다. 정적 BASE_URL 만 쓰면 그 경로에서 라우트 매칭 0 → 빈 화면이
                됐다(실사고 2026-09-03: 인증·자산·API 전부 성공인데 셸만 렌더). */}
            <BrowserRouter basename={(() => {
              const base = import.meta.env.BASE_URL            // '/' 또는 '/apps/kooremapper/'
              if (base === '/') return base
              const i = window.location.pathname.indexOf(base)
              return i > 0 ? window.location.pathname.slice(0, i) + base : base
            })()}>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
