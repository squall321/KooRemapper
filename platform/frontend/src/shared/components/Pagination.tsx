import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/shared/ui/ui'

interface PaginationProps {
  offset: number
  limit: number
  count: number
  onChange: (offset: number) => void
}

export function Pagination({ offset, limit, count, onChange }: PaginationProps) {
  // Hide entirely on any empty page (not just the first) so we never render a
  // nonsensical range like "0–20" on an overshot page.
  if (count === 0) return null
  const from = offset + 1
  const to = offset + count
  const atStart = offset <= 0
  // NOTE: without a total/hasMore input we can't distinguish a full last page
  // from a full middle page, so "다음" stays enabled on an exact-multiple last
  // page (lands on an empty page, which then renders nothing). When wiring this
  // component, pass a real total and compute `offset + limit >= total`.
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
