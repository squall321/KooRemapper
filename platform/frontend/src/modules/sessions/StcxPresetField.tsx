// 각도 프리셋 고르개 — 목록을 **서버에 물어서** 채운다
//
// 코드에 박으면 클러스터에 프리셋이 늘어도 화면에는 안 보이고, 사용자는 있는 것을 못 쓴다.
// 그리고 못 물어본 경우와 정말 없는 경우를 **가려서** 보여 준다 — 둘을 같은 빈 목록으로
// 만들면 화면을 보는 사람이 원인을 영영 모른다.
import { useEffect, useState } from 'react'
import { getStcxOptions, type StcxOptions } from '@/shared/api/endpoints'
import { Input, Select } from '@/shared/ui/ui'

export function StcxPresetField({
  value, onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const [opts, setOpts] = useState<StcxOptions | null>(null)
  const [failed, setFailed] = useState(false)
  const [showCatalog, setShowCatalog] = useState(false)

  useEffect(() => {
    let alive = true
    getStcxOptions()
      .then((o) => { if (alive) setOpts(o) })
      .catch(() => { if (alive) setFailed(true) })
    return () => { alive = false }
  }, [])

  // 못 물어봤으면 **직접 적을 길**은 남긴다 — 프리셋 이름을 아는 사람까지 막을 이유가 없다.
  if (failed || (opts && !opts.available)) {
    return (
      <div>
        <Input
          value={value}
          placeholder="프리셋 이름 (예: fibonacci-100)"
          onChange={(e) => onChange(e.target.value)}
        />
        <div className="text-xs text-warning mt-1">
          프리셋 목록을 못 가져왔습니다{opts?.reason ? ` (${opts.reason})` : ''} — 이름을 직접 적을 수 있습니다.
          {opts?.reason === 'unavailable' && ' 게이트웨이 주소·PAT 설정을 확인하세요.'}
        </div>
      </div>
    )
  }

  if (!opts) return <Select disabled><option>불러오는 중…</option></Select>

  return (
    <div>
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">(기본 — 도구 기본 각도원)</option>
        {opts.presets.map((p) => <option key={p} value={p}>{p}</option>)}
      </Select>
      {opts.presets.length === 0 && (
        <div className="text-xs text-muted mt-1">서버에 등록된 프리셋이 없습니다 — 아래 옵션으로 직접 정하세요.</div>
      )}
      {opts.catalog && (
        <div className="mt-1">
          <button type="button" className="text-xs text-muted underline"
            onClick={() => setShowCatalog((v) => !v)}>
            {showCatalog ? '옵션 카탈로그 접기' : '옵션 카탈로그 보기 (단위·기본값·허용값)'}
          </button>
          {showCatalog && (
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-bg p-2 text-[11px] leading-relaxed">
              {opts.catalog}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
