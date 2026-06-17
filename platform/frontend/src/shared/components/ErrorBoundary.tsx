import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State { error: Error | null }

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-full grid place-items-center p-6">
          <div className="max-w-md text-center">
            <h1 className="text-lg font-semibold text-danger mb-2">문제가 발생했습니다</h1>
            <p className="text-sm text-muted mb-4">{this.state.error.message}</p>
            <button
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface"
              onClick={() => { this.setState({ error: null }); location.reload() }}
            >
              새로고침
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
