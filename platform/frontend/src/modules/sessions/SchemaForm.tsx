// Dynamic argument form generated from an operation's JSON Schema.
// - file-typed params (x-kind=session_file) render as a session-file dropdown
// - enums render as <select>, booleans as checkbox, numbers/strings as inputs
// - freeform yaml ops (single `config` object param) render a JSON/YAML textarea
import { useState } from 'react'
import type { OperationDetail, SessionFile } from '@/shared/api/types'
import { Input, Label, Select, Textarea } from '@/shared/ui/ui'

export type ArgValues = Record<string, unknown>

export function SchemaForm({
  op, files, value, onChange,
}: {
  op: OperationDetail
  files: SessionFile[]
  value: ArgValues
  onChange: (v: ArgValues) => void
}) {
  const schema = op.args_schema
  const set = (k: string, v: unknown) => onChange({ ...value, [k]: v })

  // freeform config object → raw editor
  const isFreeform = op.invocation === 'yaml' && op.config_style === 'freeform'
  if (isFreeform) {
    return <ConfigEditor value={value} onChange={onChange} example={op.example.args} />
  }

  const props = schema.properties
  const required = new Set(schema.required)

  return (
    <div className="space-y-3">
      {Object.entries(props).map(([name, def]) => {
        const isFile = def['x-kind'] === 'session_file'
        const req = required.has(name)
        const label = (
          <Label className="flex items-center gap-1">
            {name}{req && <span className="text-danger">*</span>}
            <span className="text-muted/70 font-normal">— {def.description}</span>
          </Label>
        )
        if (def.type === 'boolean') {
          return (
            <label key={name} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!value[name]} onChange={(e) => set(name, e.target.checked)} />
              <span>{name}</span>
              <span className="text-xs text-muted">— {def.description}</span>
            </label>
          )
        }
        return (
          <div key={name}>
            {label}
            {def.enum ? (
              <Select value={(value[name] as string) ?? ''} onChange={(e) => set(name, e.target.value)}>
                <option value="">(선택)</option>
                {def.enum.map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}
              </Select>
            ) : isFile ? (
              <Select value={(value[name] as string) ?? ''} onChange={(e) => set(name, e.target.value)}>
                <option value="">(파일 선택)</option>
                {files.map((f) => <option key={f.id} value={f.filename}>{f.filename}</option>)}
              </Select>
            ) : (
              <Input
                type={def.type === 'number' || def.type === 'integer' ? 'number' : 'text'}
                value={(value[name] as string | number) ?? ''}
                placeholder={def.default !== undefined ? `기본값: ${String(def.default)}` : ''}
                onChange={(e) => {
                  const raw = e.target.value
                  set(name, def.type === 'number' ? parseFloat(raw) : def.type === 'integer' ? parseInt(raw, 10) : raw)
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

function ConfigEditor({ value, onChange, example }: { value: ArgValues; onChange: (v: ArgValues) => void; example: Record<string, unknown> }) {
  const initial = JSON.stringify((value.config ?? example.config ?? {}), null, 2)
  const [text, setText] = useState(initial)
  const [err, setErr] = useState<string | null>(null)
  return (
    <div>
      <Label>config (JSON) — 이 작업은 자유 형식 설정 객체를 받습니다</Label>
      <Textarea
        rows={14}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          try { onChange({ config: JSON.parse(e.target.value) }); setErr(null) }
          catch (x) { setErr((x as Error).message) }
        }}
      />
      {err && <div className="text-xs text-danger mt-1">JSON 오류: {err}</div>}
    </div>
  )
}
