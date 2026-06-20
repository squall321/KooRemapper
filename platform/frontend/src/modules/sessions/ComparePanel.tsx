import { useMemo, useState } from 'react'
import { Card, CardBody, CardHeader, EmptyState, Label, Select } from '@/shared/ui/ui'
import { fmtBytes } from '@/shared/lib/cn'
import type { SessionFile } from '@/shared/api/types'

type Row = {
  label: string
  a: number | null
  b: number | null
  unit?: string
  fmt?: (n: number) => string
}

// bbox extent = max - min per axis; returns null if either bound missing or reversed.
function extent(meta: SessionFile['meta'], axis: number): number | null {
  const lo = meta?.bbox_min?.[axis]
  const hi = meta?.bbox_max?.[axis]
  if (typeof lo !== 'number' || typeof hi !== 'number') return null
  if (lo > hi) return null
  return hi - lo
}

const DASH = '—'

export function ComparePanel({ files }: { files: SessionFile[] }) {
  const [aId, setAId] = useState<number | null>(files[0]?.id ?? null)
  const [bId, setBId] = useState<number | null>(files[1]?.id ?? files[0]?.id ?? null)

  const a = useMemo(() => files.find((f) => f.id === aId) ?? null, [files, aId])
  const b = useMemo(() => files.find((f) => f.id === bId) ?? null, [files, bId])

  // Keep A and B distinct: when one is set to the other's value, shift the other.
  const pickA = (id: number) => {
    setAId(id)
    if (id === bId) setBId(files.find((f) => f.id !== id)?.id ?? null)
  }
  const pickB = (id: number) => {
    setBId(id)
    if (id === aId) setAId(files.find((f) => f.id !== id)?.id ?? null)
  }

  const rows: Row[] = useMemo(() => {
    const num = (v: number | undefined) => (typeof v === 'number' ? v : null)
    return [
      { label: '노드', a: num(a?.meta?.nodes), b: num(b?.meta?.nodes) },
      { label: '요소', a: num(a?.meta?.elements), b: num(b?.meta?.elements) },
      { label: '파트', a: num(a?.meta?.parts), b: num(b?.meta?.parts) },
      { label: '크기', a: a ? a.size_bytes : null, b: b ? b.size_bytes : null, fmt: fmtBytes },
      { label: 'bbox X', a: extent(a?.meta ?? null, 0), b: extent(b?.meta ?? null, 0), fmt: (n) => n.toFixed(2) },
      { label: 'bbox Y', a: extent(a?.meta ?? null, 1), b: extent(b?.meta ?? null, 1), fmt: (n) => n.toFixed(2) },
      { label: 'bbox Z', a: extent(a?.meta ?? null, 2), b: extent(b?.meta ?? null, 2), fmt: (n) => n.toFixed(2) },
    ]
  }, [a, b])

  const show = (v: number | null, fmt?: (n: number) => string) =>
    v === null ? DASH : fmt ? fmt(v) : v.toLocaleString()

  return (
    <Card>
      <CardHeader>
        <span className="font-medium text-sm">파일 비교</span>
      </CardHeader>
      <CardBody>
        {files.length < 2 ? (
          <EmptyState title="비교할 파일 부족" hint="파일이 2개 이상일 때 비교할 수 있습니다." />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="space-y-1">
                <Label>A (기준)</Label>
                <Select value={aId ?? ''} onChange={(e) => pickA(Number(e.target.value))}>
                  {files.map((f) => (
                    <option key={f.id} value={f.id} disabled={f.id === bId}>{f.filename}</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label>B (대상)</Label>
                <Select value={bId ?? ''} onChange={(e) => pickB(Number(e.target.value))}>
                  {files.map((f) => (
                    <option key={f.id} value={f.id} disabled={f.id === aId}>{f.filename}</option>
                  ))}
                </Select>
              </div>
            </div>

            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted border-b border-border">
                  <th className="text-left font-medium py-1.5">항목</th>
                  <th className="text-right font-medium py-1.5">A</th>
                  <th className="text-right font-medium py-1.5">B</th>
                  <th className="text-right font-medium py-1.5 w-28">Δ (B−A)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => {
                  const delta = r.a !== null && r.b !== null ? r.b - r.a : null
                  const eq = delta === 0
                  const dColor = delta === null || eq ? 'text-muted' : delta > 0 ? 'text-success' : 'text-danger'
                  const dMag = delta === null ? '' : r.fmt ? r.fmt(Math.abs(delta)) : Math.abs(delta).toLocaleString()
                  return (
                    <tr key={r.label}>
                      <td className="py-1.5 text-muted">{r.label}</td>
                      <td className="py-1.5 text-right mono">{show(r.a, r.fmt)}</td>
                      <td className="py-1.5 text-right mono">{show(r.b, r.fmt)}</td>
                      <td className={`py-1.5 text-right mono ${dColor}`}>
                        {delta === null || eq ? DASH : `${delta > 0 ? '+' : '−'}${dMag}`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </CardBody>
    </Card>
  )
}
