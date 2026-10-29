// Dynamic argument form generated from an operation's JSON Schema.
// - file-typed params (x-kind=session_file) render as a session-file dropdown
// - enums render as <select>, booleans as checkbox, numbers/strings as inputs
// - freeform yaml ops (single `config` object param) render a JSON/YAML textarea
import { useState } from 'react'
import yaml from 'js-yaml'
import type { OperationDetail, PropDef, SessionFile } from '@/shared/api/types'
import { Input, Label, Select, Textarea } from '@/shared/ui/ui'
import { StcxPresetField } from './StcxPresetField'

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
  // Selecting the empty option deletes the key (don't send '' — it traps
  // optional enums and turns an optional file arg like matdb's database into '').
  const setOpt = (k: string, v: string) => {
    if (v === '') { const next = { ...value }; delete next[k]; onChange(next) }
    else set(k, v)
  }

  // freeform config object → raw editor
  const isFreeform = op.invocation === 'yaml' && op.config_style === 'freeform'
  if (isFreeform) {
    return <ConfigEditor value={value} onChange={onChange} example={op.example.args} />
  }

  const props = schema.properties
  const required = new Set(schema.required)

  // 칸을 묶는다 — 옵션이 수십 개인 작업(전각도 낙하 등)에서 한 줄로 늘어놓으면 아무도 못 쓴다.
  // group 이 없는 작업은 예전처럼 평평하게 그린다(기존 48개 작업은 아무것도 안 바뀐다).
  const entries = Object.entries(props)
  const groups: string[] = []
  for (const [, d] of entries) {
    const g = d['x-group']
    if (g && !groups.includes(g)) groups.push(g)
  }
  const field = ([name, def]: [string, PropDef]) => {
        const isFile = def['x-kind'] === 'session_file'
        const req = required.has(name)
        const label = (
          <Label className="flex items-center gap-1">
            {name}{req && <span className="text-danger">*</span>}
            <span className="text-muted/70 font-normal">— {def.description}</span>
          </Label>
        )
        // 각도 프리셋만은 목록이 **서버에 있다** — 평범한 문자열 칸으로 두면
        // 사용자가 이름을 외워서 타이핑해야 하고, 서버에 새 프리셋이 생겨도 모른다.
        if (name === 'angle_preset') {
          return (
            <div key={name}>
              {label}
              <StcxPresetField value={(value[name] as string) ?? ''}
                onChange={(v) => setOpt(name, v)} />
            </div>
          )
        }
        if (def.type === 'boolean') {
          return (
            <label key={name} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!value[name]} onChange={(e) => set(name, e.target.checked)} />
              <span>{name}</span>
              <span className="text-xs text-muted">— {def.description}</span>
            </label>
          )
        }
        if (def.type === 'object' || def.type === 'array') {
          // config/object/array param → YAML editor (e.g. squeeze.config, convert.config)
          return (
            <div key={name}>
              {label}
              <ObjectField value={value[name]} onChange={(v) => set(name, v)} />
            </div>
          )
        }
        return (
          <div key={name}>
            {label}
            {def.enum ? (
              <Select value={(value[name] as string) ?? ''} onChange={(e) => setOpt(name, e.target.value)}>
                <option value="">(선택)</option>
                {def.enum.map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}
              </Select>
            ) : isFile ? (
              <Select value={(value[name] as string) ?? ''} onChange={(e) => setOpt(name, e.target.value)}>
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
                  if (raw === '') {
                    const next = { ...value }
                    delete next[name]
                    onChange(next)
                    return
                  }
                  if (def.type === 'number' || def.type === 'integer') {
                    const n = def.type === 'integer' ? parseInt(raw, 10) : parseFloat(raw)
                    if (!Number.isNaN(n)) set(name, n)
                  } else {
                    set(name, raw)
                  }
                }}
              />
            )}
          </div>
        )
  }

  if (groups.length === 0) {
    return <div className="space-y-3">{entries.map((e) => field(e))}</div>
  }
  return (
    <div className="space-y-2">
      {groups.map((g, i) => {
        const mine = entries.filter(([, d]) => d['x-group'] === g)
        // 첫 묶음(필수·기본)은 펼쳐 둔다 — 아무것도 안 보이는 폼은 고장처럼 보인다.
        const hasRequired = mine.some(([n]) => required.has(n))
        return (
          <details key={g} open={i === 0 || hasRequired}
            className="rounded border border-muted/25 px-3 py-2">
            <summary className="cursor-pointer text-sm font-medium">
              {g} <span className="text-xs text-muted font-normal">({mine.length})</span>
            </summary>
            <div className="space-y-3 pt-2">{mine.map((e) => field(e))}</div>
          </details>
        )
      })}
    </div>
  )
}

// YAML editor for a single object/array-typed parameter (initialized once;
// the parent remounts SchemaForm via key when the op changes or example is filled).
function ObjectField({ value, onChange }: { value: unknown; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(() => (value == null ? '' : yaml.dump(value, { lineWidth: 100 })))
  const [err, setErr] = useState<string | null>(null)
  return (
    <div>
      <Textarea
        rows={10}
        value={text}
        placeholder="YAML 또는 JSON"
        onChange={(e) => {
          setText(e.target.value)
          if (e.target.value.trim() === '') { onChange(undefined); setErr(null); return }
          try { onChange(yaml.load(e.target.value)); setErr(null) }
          catch (x) { setErr((x as Error).message) }
        }}
      />
      {err && <div className="text-xs text-danger mt-1">파싱 오류: {err}</div>}
    </div>
  )
}

function ConfigEditor({ value, onChange, example }: { value: ArgValues; onChange: (v: ArgValues) => void; example: Record<string, unknown> }) {
  // Default to YAML (KooRemapper-native). Accepts YAML or JSON (YAML is a superset).
  const initial = yaml.dump((value.config ?? example.config ?? {}), { lineWidth: 100 })
  const [text, setText] = useState(initial)
  const [err, setErr] = useState<string | null>(null)
  return (
    <div>
      <Label>config (YAML/JSON) — 이 작업은 자유 형식 설정 객체를 받습니다</Label>
      <Textarea
        rows={14}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          try {
            const parsed = yaml.load(e.target.value)
            if (parsed && typeof parsed === 'object') { onChange({ config: parsed }); setErr(null) }
            else setErr('설정은 객체여야 합니다')
          } catch (x) { setErr((x as Error).message) }
        }}
      />
      {err && <div className="text-xs text-danger mt-1">파싱 오류: {err}</div>}
    </div>
  )
}
