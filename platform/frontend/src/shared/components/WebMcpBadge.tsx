import { Badge } from '@/shared/ui/ui'

interface WebMcpBadgeProps {
  web?: boolean
  mcp?: boolean
}

export function WebMcpBadge({ web = true, mcp = true }: WebMcpBadgeProps) {
  return (
    <span className="inline-flex items-center gap-1">
      <Badge tone={web ? 'succeeded' : 'default'}>웹</Badge>
      <Badge tone={mcp ? 'succeeded' : 'default'}>MCP</Badge>
    </span>
  )
}
