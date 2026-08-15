---
name: kooremapper
description: >
  LS-DYNA K파일에 메쉬 매핑/응력/재메쉬/해석셋업 등 전체 오퍼레이션을 적용하고 결과를
  내려받는다. "K파일 매핑/prestress/squeeze/assemble/메쉬 변환/접촉/하중/경계조건"
  같은 LS-DYNA 전처리 요청에 사용. KooRemapper MCP 서버(도구)가 연결돼 있어야 한다.
---

# KooRemapper

LS-DYNA `.k` 파일을 다루는 KooRemapper 플랫폼을 Claude에서 사용하는 스킬.
모든 작업은 **세션(프로젝트)** 단위로 파일을 모아두고, **오퍼레이션**을 적용해
산출물(.k/.dynain/.csv)을 만들어 내려받는 흐름이다.

## 표준 워크플로

1. **무엇을 할지 정한다** — `list_operations()` 로 전체 op 요약을 본다.
   원하는 op를 고르면 `describe_operation(op)` 로 **args_schema**(인자 JSON Schema),
   입출력, 예제 args를 확인한다. **args는 반드시 이 스키마를 따른다.**
2. **세션 준비** — 기존 세션은 `list_sessions()`, 없으면 `create_session(name)`.
3. **파일 업로드** — `upload_kfile(session_id, filename, content)`.
   업로드 즉시 백엔드가 `info`로 노드/요소/파트/bbox/`*INCLUDE`를 파싱한다.
   "이 파일 안에 뭐가 있나"는 `list_session_files(session_id)` 또는 `inspect_file(...)`.
4. **실행** — `run_operation(session_id, op, args)` → `job_id`.
   - 파일 인자(예: bent_mesh, flat_mesh, model)는 **세션 내 파일명**을 그대로 쓴다.
   - YAML 계열 op는 args가 곧 설정 키다. `config_style: "freeform"` op는
     `args = {"config": { ... }}` 형태로 전체 설정 객체를 넣는다.
5. **대기/확인** — `get_job(job_id)` 로 status가 `succeeded`/`failed`가 될 때까지 폴링.
   실패면 `get_job(job_id, include_logs=true)` 로 stderr를 보고 args를 고쳐 재시도.
6. **결과 회수** — `get_job_outputs(job_id)` 로 산출 file_id 확인 →
   `download_result(session_id, file_id)` 로 내용을 받는다.

## 인자 작성 팁

- **positional op**(map/shellmap/prestress/strain/info 등): args 키 = 파일/플래그 이름.
  예) map → `{"bent_mesh":"bent.k","flat_mesh":"flat.k","output":"mapped.k"}`
- **structured yaml op**(relax/implicit/modal/database 등): 평평한 키.
  예) relax → `{"model":"m.k","output":"r.k","level":2,"mode":"explicit"}`
- **freeform yaml op**(assemble/contact/ale/offset/merge/battery 등): 전체 설정을 config로.
  예) assemble → `{"config":{"base_model":"model.k","output":"result","operations":[...]}}`
- 잘 모르면 `describe_operation(op)` 의 `example.args` 를 거의 그대로 쓰고 파일명만 바꾼다.

## 자주 쓰는 op

- `map` / `shellmap` : flat → bent 매핑(코어)
- `prestress` / `strain` : 초기응력 / 변형률
- `squeeze` / `wrap` / `bend` / `indent` / `warpage` : 변형 + prestress
- `assemble` : 여러 op 순차 파이프라인
- `convert` / `refine` / `tetremesh` / `meshfix` : 메쉬 변환·재메쉬
- `implicit` / `modal` / `relax` / `ale` / `stabilize` : 해석 셋업
- `contact` / `load` / `boundary` / `rbe` : 접촉·하중·경계조건
- `info` : 메쉬 정보 조회

> meshfix는 gmsh 바이너리가 필요할 수 있다(`requires_gmsh`). 실패 시 로그를 확인하라.

## 낙하/충격 리포트 분석

SmartTwin 파이프라인이 만든 낙하/충격 리포트 HTML(deep 단건 심층 · sphere 전각도 낙하 ·
impact 전위치 부분충격)을 인제스트해 구조화 분석한다.

1. **인제스트** — `ingest_report(session_id, filename, html_content)` 로 리포트 HTML 을 올린다.
   kind 는 자동판별(원하면 kind 명시). 반환 report_id 로 이후 분석한다.
2. **개요 파악** — `report_summary(report_id)` 로 kind·프로젝트·전역 최악값·findings 를 본다.
3. **최악 케이스** — `report_worst_cases(report_id, metric)` (sphere=최악 방향, impact=최악 위치).
   metric ∈ max_stress/max_g/max_disp/min_safety_factor.
4. **파트 리스크** — `report_part_risk(report_id, part_id?)` 로 "어느 파트가 어느 방향/위치에서
   가장 위험한가" 와 최소 안전율을 확인한다.
5. **소견/케이스** — `report_findings(report_id, severity?)`, `report_case(report_id, case_key)`.
6. **리비전 비교** — `compare_reports([id1, id2, ...])` 로 조건/리비전 간 파트별 최악값을 나란히 본다.
