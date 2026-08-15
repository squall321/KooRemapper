# AI Data Hub `sim_report` 레코드 양식 (모든 시뮬레이션 forge 공용)

DynaForge 는 "여러 시뮬레이션의 forge" 로 확장된다(툴마다 forge). 각 forge 가 결과
리포트를 데이터 허브에 올릴 때 **동일한 레코드 양식**을 쓰도록 여기 표준을 고정한다.
현재 낙하/충격(drop_impact) forge 가 이 양식으로 등재한다.

## 원칙
- `data_type = "SIM"`, `doc_type = "sim_report"` — 도메인 무관 고정값.
- 실제 시험 종류는 **판별자**로 구분: `sim_domain`(예 drop_impact, thermal, vibration, cfd),
  `report_kind`(도메인 내 세부 종류; 낙하는 deep/sphere/impact).
- 판별자는 **AIDataHub SimContent 정의 필드가 아니라** 정규화에서 떨어지므로,
  **생존하는 3곳**에 중복 기입한다.
  1. `content.inputs.sim_domain` / `content.inputs.report_kind` (자유 dict → 보존)
  2. `tags`: `sim:<domain>`, `kind:<report_kind>` (태그 필터 질의용)
  3. 첨부 `extra.sim_domain` / `extra.report_kind`
- `eng_meta.doe` 는 **DoeRef 규격**만 허용: `study`(필수)·`case`·`factors`(dict).
  DOE 전략 같은 부가정보는 `factors` 에 넣는다(예 `{"strategy":"cuboid_26"}`). study 가
  없으면 `doe` 자체를 만들지 않는다(빈 doe 금지).
- `source_system` = forge 이름(현재 "DynaForge"), `agents` = 등재 주체.
- 첨부 규약: 원본 리포트 HTML 은 `kind="document"`, `file_path="{record_id}/{파일명}"`,
  zip 번들 안에 같은 경로로 담는다.

## 레코드 골격
```json
{
  "id": "SIM-<TEAM>-<GROUP>-<year>-<seq(10)>",
  "data_type": "SIM",
  "doc_type": "sim_report",
  "title": "...",
  "summary": "<domain>/<kind> ... 검색 승격어 포함",
  "project": "<과제코드>",
  "tags": ["sim:<domain>", "kind:<report_kind>", "stage:<stage>", "part:<...>", "finding:<SEV>"],
  "subject_keywords": ["<파트명>", ...],
  "related_record_ids": [],
  "source_system": "<forge>",
  "agents": ["<forge>-report"],
  "content": {
    "solver": "LS-DYNA",
    "inputs": { "sim_domain": "...", "report_kind": "...", "generator": "...",
                "test_dir": "...", "doe_strategy": "..." },
    "outputs": { "sim_params": {...}, "summary": {...}, "findings": [...],
                 "worst_cases": [ {case_key, identity, max_stress, max_g, max_disp, min_safety_factor} ],
                 "n_cases": N },
    "eng_meta": { "project": "...", "dev_revision": {"phase":"dv","round":"1"},
                  "design_variation": "...",
                  "doe": {"study":"...", "case":"...", "factors": {"strategy":"..."}} },
    "components": [ {pid, title, group} ],
    "attachments": [ {id, record_id, number, kind:"document",
                      caption, file_name, file_path:"{id}/{name}",
                      extra:{sim_domain, report_kind, generator, format:"html", role:"report", unit_system}} ]
  }
}
```

## 개발단계(stage) → dev_revision
`(pre|dv|pv|pra|mp)([123r])?` — dv/pv 는 차수 필수, pre/pra/mp 는 차수 금지.
예: dv1→{phase:dv,round:1}, pvr→{phase:pv,round:r}, pre→{phase:pre}.

## 번들 업로드
record.json + `{record_id}/<첨부>` 를 ZIP 으로 묶어 `POST /api/ingest/bundle` (multipart).
record.id 는 클라이언트가 생성한다(서버 자동부여 아님). seq 는 (team,group,year) 자연키별 max+1.

## 새 forge 추가 절차
1. 파서에 새 `sim_domain`/`report_kind` 노멀라이저 추가(공통 NormalizedStudy 반환).
2. 등재 시 위 판별자 3곳만 채우면 이 양식 그대로 재사용 — 스키마 변경 불필요.
3. 검색: `tags=sim:<domain>` 또는 `kind:<report_kind>` 로 도메인 슬라이스 질의.
