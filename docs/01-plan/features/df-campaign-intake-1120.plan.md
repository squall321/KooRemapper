# DF 2차 ① — 캠페인 일괄 적재 · 중복 막기(DF-01) 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-01 이고 설계안 `df-request-1117.design.md` 의 ① 단계다. 체크리스트
`df-campaign-intake-1120.checklist.md` · 맥락 `df-campaign-intake-1120.context-notes.md`. 요청서의 검증 사례(과제 이름 · PC 경로)는 옮기지
않는다.

## 0. 「진행해줘」(사용자 11-20)를 이렇게 읽었다
- 설계안 §5 에서 권고가 붙은 셋을 그대로 쓴다 — 1 새 표 `campaigns` · `campaign_runs`, 2 같은 `run_key` 에 다른 sha256 은 거절, 7 런마다 intake
  (올리는 쪽이 파일을 보낸다 — 지금 길 그대로).
- 이름은 설계안 §3 이름표의 ① 줄 넷만 쓴다(아래 1절). ② ~ ⑥ 단계의 이름은 확인 전 그대로 둔다.
- 권고가 없는 4(건강 문턱) · 6(footprint)은 손대지 않는다. 3(큰 리포트 메모리)은 재서 숫자와 선택지를 내고 상한은 고르지 않는다.
- 짓고 시험해 갈래(`corelink-int`)에 올리는 데까지 한다. main · dev DB 마이그레이션 · Drive 게시는 이 계획 · 이름 · 검증 사례를 확인받은
  뒤다(설계안 §1 「단계마다 계획 · 이름표 · 검증 사례를 따로 확인받고 올린다」).
- 이 읽기가 틀렸으면 이름 · 상태 단어 · 규칙은 갈래 안에서 고친다 — 아직 어디에도 게시하지 않았다.

## 1. 짓는 것
| 겉 | 이름 | 하는 일 |
|---|---|---|
| REST | `POST /campaigns` | 캠페인을 만든다(이름 · 과제 · 판 · 해석 방법 · DOE 전략 · 낙하 높이 · 지속 시간 · 두께 축 · 충격자) |
| REST | `POST /campaigns/{id}/runs` | 런 목록(매니페스트)을 올린다 — `run_key` · `doe` · `pitch` · `roll`. 다시 올리면 새 것만 더하고 있는 것은 그대로 |
| REST | `GET /campaigns/{id}/ingest-status` | 목록 수 · 상태별 수 · 런마다 상태 · report_id · 지문 · 거절 까닭 |
| REST | `POST /reports/intake` 폼 칸 `campaign_id` · `run_key` | 리포트 하나를 그 런의 것으로 받는다 — 같은 내용이면 건너뛰고 다른 내용이면 거절 |
| MCP | `create_campaign` · `ingest_campaign_manifest` · `campaign_ingest_status` | 위 REST 셋을 그대로 부른다(파일 본문은 MCP 로 나르지 않는다) |
| 선언 | `capabilities.intake` | `batch` 를 켜고 캠페인 길(`campaign`) · 분당 호출 한도(`rate_limit_per_min`) · 한 호출의 리포트 수(`reports_per_call`)를 싣는다 |

화면(콘솔)은 이 단계에 없다.

## 2. 표(마이그레이션 `0021_campaigns`)
- `campaigns` — id(ULID) · created_by(사용자, 지워지면 함께) · name(만든 사람 안에서 유일) · project · dev_rev · analysis_method ·
  analysis_target · doe_strategy · drop_height_mm · duration_ms · thickness_axis · impactor(JSONB `{mass_g, height_mm, ke_mj}`) · created_at.
- `campaign_runs` — id · campaign_id(캠페인이 지워지면 함께) · run_key(캠페인 안에서 유일) · report_id(리포트가 지워지면 null) · doe · pitch ·
  roll · content_sha256 · ingest_state · reject_reason · ingested_at · created_at.
- 리포트 표(`impact_reports`)는 건드리지 않는다.

## 3. 동작 규칙
1. **지문** — `content_sha256` 은 저장하는 리포트 HTML 바이트의 sha256 이다(.gz 는 푼 뒤 · 묶음은 그 안의 HTML). 세션에 저장된 리포트 파일의
   sha256 과 같은 값이다. 묶음에 함께 온 그림 · 온톨로지 꾸러미는 지문에 넣지 않는다.
2. **상태 단어** — `pending`(목록에만 있다) · `received`(받았다) · `skipped`(같은 내용이라 건너뛰었다) · `rejected`(거절 — 까닭은
   `reject_reason`). `ingest_state` 는 **마지막 시도의 결과**다. `report_id` · `content_sha256` · `ingested_at` 은 그 런이 **가진 리포트**를
   말하고, 뒤의 시도가 거절돼도 남는다.
3. **받음** — 런이 리포트를 갖지 않았으면 지금 intake 와 똑같이 받고 런에 묶는다. 응답(201)에 `campaign_id` · `run_key` ·
   `ingest_state: "received"` · `content_sha256` 이 더 실린다.
4. **건너뜀** — 런이 리포트를 가졌고 지문이 같으면 아무것도 저장하지 않는다(세션 · K 파일 · 리포트 모두). 응답은 200 이고 가진 리포트의
   `report_id` · `session_id` 와 `ingest_state: "skipped"` 를 준다.
5. **거절(다른 내용)** — 런이 리포트를 가졌는데 지문이 다르면 409 다. 가진 리포트는 그대로 두고, 까닭에 두 지문을 적는다.
6. **거절(그 밖)** — 런을 찾은 뒤에 난 4xx(리포트 해석 실패 · 케이스 없음 · 크기 상한 · 깨진 gzip · 묶음 오류 · 없는 세션 …)는 그 글을 까닭으로
   런에 적고 원래 응답 그대로 돌려준다. 5xx 는 적지 않는다(런 상태는 앞 그대로다). 런을 찾기 전이거나 라우트에 닿지 않은 실패 — 401 ·
   429(분당 한도) · 요청 꼴 오류 422(`file` 칸 없음) · 게이트웨이가 막은 요청 — 도 적히지 않는다.
7. **목록에 없는 run_key** — 400 이고 런 행을 만들지 않는다(목록을 먼저 올린다). `campaign_id` · `run_key` 는 함께 와야 한다(하나만 오면 400).
8. **동시에 같은 런** — 저장 직전에 런 행을 잠근다. 늦은 쪽은 아무것도 쓰기 전에 물러나 4 · 5 의 답을 한다 — 리포트는 하나만 생긴다.
9. **리포트 · 세션을 지우면** — 런의 `report_id` 가 비고(FK), 상태는 읽을 때 `pending` 으로 보인다(받았거나 건너뛴 런만 — 거절된 런은 까닭과
   함께 `rejected` 로 남는다). 그 런은 다시 받을 수 있다.
10. **수 맞춤** — `counts` 는 `listed = pending + received + skipped + rejected` 이고 `with_report`(리포트를 가진 런 수)를 따로 준다.
11. **권한** — 캠페인은 만든 사람만 본다(남의 것 · 없는 것은 404). 리포트 읽기 공유(같은 소속)는 지금 그대로다.
12. **목록 다시 올리기** — 새 `run_key` 는 `pending` 으로 더하고, 있는 것은 상태 · 리포트를 그대로 둔 채 `doe` · `pitch` · `roll` 가운데 **보낸
    칸만** 온 값으로 맞춘다(안 보낸 칸은 그대로 · null 을 보내면 비운다). 한 요청 안에 같은 `run_key` 가 둘이면 422 다. 목록에서 런을 빼는 길은
    없다. 한 요청에 5,000 런까지.
13. **세션** — `session_id` 를 보내면 그 세션에, 안 보내면 지금처럼 호출마다 새 세션에 담긴다.

## 4. 선택지 문장이 말하지 않아 조정 세션이 고른 읽기(확인받을 것)
- 상태 단어 넷과 「마지막 시도의 결과」 라는 뜻(3절 2). 설계안은 받음 · 건너뜀 · 거절만 적었고 `pending` 은 여기서 더했다.
- 지문이 HTML 바이트라는 것(3절 1) · 묶음의 그림은 지문 밖.
- 목록에 없는 `run_key` 는 거절(3절 7) · 목록 다시 올리기가 `doe` · `pitch` · `roll` 을 덮는 것(3절 12) · 모르는 칸은 422.
- 리포트를 지우면 런이 다시 열리는 것(3절 9) — 권고 문장은 「판을 바꾸려면 새 설정 세대로」 인데 설정 세대는 ② 단계 칸이다. ① 에서는 주인이
  리포트를 지우는 것이 판을 바꾸는 유일한 길이다.
- 캠페인은 만든 사람만(3절 11) · 캠페인 이름은 만든 사람 안에서 유일(같은 이름이면 409 — 글과 `data.campaign_id` 에 있는 id 를 준다).
- 어휘 칸(analysis_method · analysis_target · doe_strategy)은 온 글 그대로 둔다 — 길이만 본다(목록은 요청 쪽 것이고 이 리포 · SP 거울에 없다).
  `thickness_axis` 만 X · Y · Z 로 본다. `impactor` 의 열쇠 이름 `mass_g` · `height_mm` · `ke_mj`.
- `doe` 는 글로 둔다(숫자가 와도 글로 바꾼다 — 리포트 수동 메타의 `doe` 와 같은 꼴).
- (지으며 더함) `capabilities.intake` 의 새 칸 이름 — `reports_per_call`(값 1) · `rate_limit_per_min` · `campaign` 아래 `create` · `manifest` ·
  `status` · `form_fields` · `states`. `batch: true` 는 「캠페인 묶음 적재가 있다」 는 뜻이고 한 호출은 여전히 리포트 하나다. 이름표에 없던
  칸이다.
- (지으며 더함) 응답 칸 — 받음 · 건너뜀 응답의 `campaign_id` · `run_key` · `ingest_state` · `content_sha256`, 거절(409) 응답 `data` 의
  `offered_sha256`, 목록 올리기 응답의 `added` · `updated` · `unchanged` · `listed`, 상태 응답의 `counts`(`with_report` 포함) · `matched` ·
  `runs`.
- (지으며 더함) `ingest-status` 가 받는 것 — `state`(상태 단어 하나) · `limit`(기본 200 · 최대 5,000) · `offset`. 런은 올린 차례로 온다.
- (지으며 더함) 캠페인의 `dev_rev` 는 intake 폼과 같은 꼴만 받는다(틀리면 422) · `project` 는 64 자까지 · `run_key` 는 128 자까지고 빈칸 · 제어
  문자가 없어야 한다(`stcx:<잡 id>:<DOE>` 꼴은 권할 뿐 검사하지 않는다).
- (지으며 더함) 런에 적히지 않는 실패(3절 6) — 올린 쪽이 「보냈는데 pending 그대로」 를 보면 이 갈래다.

## 5. 하지 않는 것
- 캠페인 목록 · 한 건 읽기 · 고침 · 지우기 · 런 빼기(이름표에 없다). id 를 잊었으면 같은 이름으로 만들기를 부르면 409 가 id 를 준다.
- 캠페인의 project · dev_rev 를 리포트 수동 메타로 물려주기 — intake 폼의 `project` · `dev_rev` 가 지금처럼 리포트 메타를 정한다.
- 서버가 경로에서 당겨 오기 · 한 호출에 리포트 여럿(정할 것 7 의 다른 갈래).
- KC-01 매니페스트 파일을 그대로 읽기 — 그 꼴을 보지 못했다. 목록은 JSON `{"runs": [...]}` 로 받는다.
- 출처 · 설정 세대 · 건강 · 추출 칸(② · ③ 단계).

## 6. 검증 사례(시험 `tests/test_campaign_intake.py` — 10 · 12 · 13 은 그 밖)
1. 같은 `run_key` · 같은 지문을 다시 올리면 `skipped` 이고 리포트 수가 늘지 않는다(중복 0) — .gz 로 다시 올려도 같다.
2. 같은 `run_key` 에 다른 지문은 409 `rejected` · 까닭에 두 지문 · 가진 리포트는 그대로.
3. 해석 못 하는 파일은 400 이고 런에 `rejected` + 까닭이 남는다. 그 뒤 바른 파일을 올리면 `received` 로 바뀌고 까닭이 지워진다.
4. 목록 n 건에 받음 · 건너뜀 · 거절 · 안 올린 것을 섞어 `listed = pending + received + skipped + rejected` 를 잰다.
5. 목록에 없는 `run_key` 는 400 이고 행이 늘지 않는다 · `campaign_id` 만 오면 400 · 남의 캠페인은 404.
6. 리포트를 지우면 그 런이 `pending` 으로 보이고 다시 받을 수 있다.
7. 같은 런을 동시에 둘 올리면 리포트는 하나고 다른 하나는 `skipped` 다(세션 · K 파일 찌꺼기 없음).
8. 목록을 다시 올리면 `added` · `updated` · `unchanged` 가 맞고 받은 런의 상태가 그대로다 · 한 요청 안 겹친 `run_key` 는 422.
9. 캠페인 없이 부른 intake 는 응답 칸 · 동작이 그대로다(기존 시험).
10. 큰 리포트(합성 47 ~ 441 MB)를 지금 상한 안에서 해석할 때의 시간 · 최대 메모리를 잰다 — 파싱 구간 네 크기와 실제 HTTP intake 한 번(441 MB).
    시험 밖이고 숫자는 맥락 문서에 있다.
11. 요청 꼴 오류(422) · 분당 한도(429)는 런에 적히지 않는다(런은 `pending` 그대로).
12. 임시 스택(임시 DB 의 API + 이 갈래의 MCP 서버)에서 MCP 도구 셋을 실제 프로토콜로 불러 값으로 잰다 — 시험 밖이고 28 항이 맥락 문서에 있다.
13. MCP 계약 시험 — 도구 셋의 인자 설명 · 허용 값이 백엔드 제약과 같고 `create_campaign` 의 인자가 REST 본문의 칸과
    같다(`tests/test_mcp_tools_contract.py`).

## 7. 올리는 차례(확인받은 뒤)
1. 갈래를 main 에 합친다 → dev DB 에 `alembic upgrade head`(0021) → 살아 있는 잡이 없을 때 API · MCP 재기동 → 스모크.
2. Drive 게시(코드만 — 바이너리는 그대로) → cae00 점검 문서에 한 줄.
3. 요청 쪽에 알릴 것 — 이름 넷 · 상태 단어 · 응답 꼴 · 분당 한도(429 `Retry-After`).

## 8. 재지 못한 것
- 요청서의 런 폴더 실물 — 그 `report.html` 이 데이터를 품은 한 파일인지(우리가 받는 꼴) 보지 못했다. 큰 JSON 은 합성 sphere 리포트로 대신 쟀다.
- 1,393 건을 실제로 올린 때의 디스크(cae00) · 걸리는 시간 · 운영 게이트웨이의 본문 크기 · 시간 한도. 게이트웨이가 앞에서 막은 요청은 우리에게
  닿지 않아 런에 적히지 않는다.
- KC-01 매니페스트의 꼴.
- dev · 운영 스택에서의 값 — 임시 스택(임시 DB · 워커 없음 · 같은 박스)에서만 쟀다. dev 에는 main 에 합치고 0021 을 올린 뒤에 잰다.

## 9. 사용자 확인(11-20) 뒤 — 이름은 지은 그대로 · 파싱은 줄을 세운다
- 4절의 읽기와 이름 — 사용자가 「지은 그대로」 를 골랐다. 이름 여섯(MCP `create_campaign` · `ingest_campaign_manifest` ·
  `campaign_ingest_status` · REST 셋) · 상태 넷 · 목록에 없는 `run_key` 거절 · 같은 `run_key` 에 다른 내용 거절 · 만든 사람만 본다. 고칠 것이
  없다.
- 리포트 상한(설계안 정할 것 3) — 사용자가 「줄만 세운다」 를 골랐다. 상한(`max_upload_mb` 512 · `max_report_mb` 2,048)은 그대로 두고 리포트
  받기를 한 번에 하나로 한다.
  - 자리 — `reports/services.py` 에 `_PARSE_LOCK` 을 두고 `ingest_report` 전체와 `attach_media` 의 파싱을 그 안에서 한다. 파싱 호출만 묶지 않는
    까닭은 풀린 데이터(파일의 약 8 배)가 받기가 끝날 때까지 살아 있어서다(곁파일 쓰기가 같은 데이터를 쓴다) — 호출만 묶으면 풀린 데이터 둘이
    겹친다.
  - 닿지 않는 것 — 잡 워커의 후처리 반입(다른 프로세스 — 그 안에서만 줄이 선다) · 상세 조회가 원본 HTML 을 다시 푸는 길(`_load_html_data`).
    줄을 기다리는 올리기는 제 파일 바이트(1 배)를 쥔 채 기다린다. gzip 한 건이 풀린 2,048 MB 까지 가면 어림 16 GB 다(비율로 늘린 값 —
    그 크기는 돌려 보지 않았다).
  - 잠금 차례 — 받기 줄 → 캠페인 런 행 잠금 → 곁파일 줄(`_BLOCK_BUILD_LOCK`). 거꾸로 잡는 길은 없다.
  - 검증 — 동시 호출 셋의 최대 겹침이 1 · `attach_media` 가 잠금 안에서 파싱한다 · 잠금을 빼면 시험이 빨갛다 · 임시 스택에서 동시 올리기 둘의
    최고 RSS 를 한 건과 견준다.
