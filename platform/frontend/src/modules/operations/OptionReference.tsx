// Renders the source-grounded option/key reference for an operation.
import { useState } from 'react'
import type { OperationKey, OperationPreset } from '@/shared/api/types'
import { Badge } from '@/shared/ui/ui'

export function OptionReference({
  keys, presets, collapsible = false,
}: {
  keys?: OperationKey[]
  presets?: OperationPreset[] | null
  collapsible?: boolean
}) {
  const [open, setOpen] = useState(!collapsible)
  if (!keys?.length && !presets?.length) return null

  return (
    <div className="text-xs">
      {collapsible && (
        <button onClick={() => setOpen((o) => !o)} className="text-primary mb-1">
          {open ? '▾' : '▸'} 옵션/키 레퍼런스 ({keys?.length ?? 0})
        </button>
      )}
      {open && (
        <>
          {!!keys?.length && (
            <div className="rounded-md border border-border overflow-hidden mb-2">
              <table className="w-full">
                <thead className="text-muted bg-bg">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium">키</th>
                    <th className="text-left px-2 py-1 font-medium">타입</th>
                    <th className="text-left px-2 py-1 font-medium">기본/허용값</th>
                    <th className="text-left px-2 py-1 font-medium">설명</th>
                  </tr>
                </thead>
                <tbody>
                  {keys.map((k) => (
                    <tr key={k.path} className="border-t border-border align-top">
                      <td className="px-2 py-1">
                        <code className={k.required ? 'text-fg font-medium' : 'text-muted'}>
                          {k.path}{k.required ? '*' : ''}
                        </code>
                      </td>
                      <td className="px-2 py-1 text-muted">{k.type}</td>
                      <td className="px-2 py-1 text-muted">
                        {k.values?.length ? k.values.join(' | ') : k.default != null ? `=${k.default}` : '—'}
                      </td>
                      <td className="px-2 py-1">{k.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!!presets?.length && (
            <div className="mb-1">
              <div className="text-muted mb-1">프리셋</div>
              <div className="flex flex-col gap-1">
                {presets.map((p) => (
                  <div key={p.name} className="flex gap-2">
                    <Badge>{p.name}</Badge>
                    <span className="text-muted">{p.summary}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
