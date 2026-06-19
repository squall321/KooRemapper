import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/shared/ui/ui'

interface PaginationProps {
  offset: number
  limit: number
  count: number
  onChange: (offset: number) => void
}

export function Pagination({ offset, limit, count, onChange }: PaginationProps) {
  const from = count === 0 ? 0 : offset + 1
  const to = offset + count
  const atStart = offset <= 0
  const atEnd = count < limit

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={atStart}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        <ChevronLeft className="h-4 w-4" />
        이전
      </Button>
      <span className="text-sm text-muted tabular-nums">
        {from}–{to}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={atEnd}
        onClick={() => onChange(offset + limit)}
      >
        다음
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  )
}
