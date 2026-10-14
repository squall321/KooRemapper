# 계획 — StandardPlatform 의 「과제 + 온톨로지」를 DynaForge 에 보강

받은 것 `vendor/StandardPlatform` (`f7485c0`, 버전 0.4.52, 2026-10-14 clone, 916 파일 18MB)
· 추적하지 않는다(`.gitignore` 에 `vendor/`) — **읽기 전용 참조**다.

> 이 문서는 **계획**이다. 아직 아무것도 심지 않았다. §6 의 질문에 답을 받고 시작한다.

---

## 0. 실측 — 양쪽을 재고 시작한다

### 받은 쪽 (StandardPlatform)

사내 플랫폼 **공통 틀**이다. 도메인은 비어 있고, 포크해서 도메인을 얹게 돼 있다
(`docs/새-플랫폼-만들기.md` 가 절차의 정본). 이미 다섯이 이 틀로 서 있다 —
MatNexus · TestScope · StandardPlatform · AutoJigGenerator · SimEngBay.

온톨로지는 **데이터로 정의하면 화면이 생기는** 메타모델이다.

| 표 | 무엇 |
|---|---|
| `nav_groups` | 사이드바 묶음(색은 **타입이 아니라 묶음**의 것 — 팔레트가 열둘이다) |
| `object_types` | 의미 = 축. `slug`·`kind_class`·`key_policy`·`key_scope`·`temporal_kind`·`list_view`·**`managed_by`** |
| `property_defs` | 속성 정의. **폴리모픽** — `owner_kind`가 `type`\|`relation` 이라 **관계에도 속성이 붙는다** |
| `relation_types` | `slug`·`inverse_label`·`directed`·`transitive`·`acyclic`·`src/dst_type_slugs` |
| `objects` · `object_relations` · `object_links` · `object_years` | 객체와 선. `object_links` 는 한쪽 끝이 `objects` 밖일 때(=`system` 타입) |

규모(실측) —

| | 백엔드 py | 프런트 tsx |
|---|---|---|
| `ontology` | 11,222 | — |
| `objects` | 22,958 | — |
| 둘의 프런트(`modules/ontology`+`modules/objects`) | — | 22,158 (97 파일) |
| **합** | **34,180** | **22,158** |

그리고 **의존 폐쇄가 사실상 플랫폼 전체다.** `ontology`·`objects` 가 바깥에서 끌어오는 것 —
`accounts.models`(31회) · `shared.errors`(29) · `shared.permissions`(20) · `shared.batches`(10) ·
`workspaces.models`(6) · `metrics.models`(5) · `files.models`(5) · `jobs`(4) · `datasources.models`(3) ·
`shared.system_sources`·`shared.extensions`·`audit.models`·`review.registry`·`shared.sheets` …

MCP 서버(`mcp_server/server.py`, 3,245줄, 도구 74개)는 **백엔드 API 를 감싸는 얇은 프록시**다
(`PLATFORM_API_BASE`). DynaForge 의 MCP 와 **같은 짜임새**다.

### 우리 쪽 (DynaForge)

★**이미 과제와 revision 이 있다.** 빠진 것은 그 둘이 아니다.

`ImpactReport.eng_meta` (JSONB, `app/models.py:162`) —

```
{project: str,
 dev_revision: {phase: pre|dv|pv|pra|mp, round?: 1|2|3|r, code: str},
 design_variation?: str,
 doe?: {study, case?}}
```

- 형식 검증이 **이미 있다** — `_STAGE_RE = (pre|dv|pv|pra|mp)([123r])?`,
  `dv`/`pv` 는 차수 필수, `pre`/`pra`/`mp` 는 금지(`app/reports/datahub.py:31`·`:38`)
- `build_eng_meta()`(`modules/reports/services.py:92`)가 한자리에서 만든다
- 필터·패싯·세기가 이미 붙어 있다 — `project`·`dev_rev`·`design_variation`·`doe`
  (`services.py:826-910`)
- `eng_meta.project` 가 비면 리포트에 박힌 `project_name` 으로 **폴백**한다(`:232`)
- DataHub 등재가 **같은 모양**을 쓴다(`reports/datahub.py:89`·`:179`)

그래서 진짜 빈 곳은 셋이다.

| 빈 곳 | 지금 | 결과 |
|---|---|---|
| **정체성** | `project` 가 자유 문자열 | 오타 하나가 같은 과제를 둘로 쪼갠다. 정본 목록이 없다 |
| **관계** | 없음 | "이 과제의 개발모델은" · "이 부서가 가진 과제는" · "같은 revision 의 리포트는" 을 못 묻는다 |
| **플랫폼 간 동일성** | 각자 문자열 | DataHub·RA·SP 가 같은 과제를 다른 말로 부른다 |

---

## 1. 가장 중요한 사실 — SP 가 이미 **허브/쌍둥이**를 정해 놨다

`backend/app/modules/ontology/managed.py` 머리말이 못박고 있다.

> PLM 기준정보는 **허브 플랫폼이 원천(PLM)에서 받아 쌍둥이 플랫폼에 내려준다.** 쌍둥이가 받은
> 정의·객체를 제 화면에서 고치면 다음 받기가 그 값을 덮어쓰고, 그 사실은 고친 사람에게 안
> 보인다 — 그래서 **고치는 길 자체를 막는다.**

`managed_by`(String(40))가 `object_types`·`relation_types`·`object_interfaces` 에 있고,
그 값이 내 `source` 와 다르면 **만들기·고치기·지우기·합치기·별칭·연도·파일입력·동기화가
전부 거절**된다. 막지 않는 것은 딱 하나다 —

> 막지 않는 것: 이 설치의 관계가 그 객체를 **가리키는 것**(참여 과제 · 근거 문서)

★ **DynaForge 는 쌍둥이 자리다.** 과제를 PLM 에서 직접 긁는 것이 아니라 **받아야** 하고,
우리 것은 **그 과제를 가리키는 관계**다. 사용자가 말한 "자체 온톨로지 정보로 같은 과제라도
revision 을 포함" 이 이 구조와 정확히 맞는다 — 과제는 허브 것(못 고침), revision 은 우리 것.

---

## 2. "심는다" 가 뜻할 수 있는 것 셋 — 지우지 않고 전부 올린다

| | A. 통째로 포팅 | B. SP 인스턴스를 띄우고 DynaForge 가 쓴다 | C. 최소 발췌 — 얇은 온톨로지를 DynaForge 안에 |
|---|---|---|---|
| 하는 일 | `ontology`+`objects`+의존 폐쇄를 DynaForge 로 옮긴다 | SP 를 포크/인스턴스로 띄우고 게이트웨이에 등재, DynaForge 가 API·MCP 로 읽는다 | 과제·개발리비전·관계만 DynaForge 표로. SP 의 **설계를 베끼고 코드는 안 옮긴다** |
| 새 코드 | **56,000줄+** 이식 + 마이그레이션 + MCP | 거의 없음(클라이언트 1개) | 1,000~2,000줄 추정 |
| 부딪히는 것 | DynaForge 에 `Workspace`(부서)가 **없다**. `User`·`Job` 이 양쪽에 있어 두 벌이 된다 | 없음 | 없음 |
| 유지 | 영구 포크 — SP 가 고쳐질 때마다 따라가야 한다 | SP 쪽 그대로 받는다 | 우리가 만든 것만 |
| 화면 | 자동 생성 화면이 그대로 온다(큰 이득) | DynaForge 화면은 **직접 만든다** | 직접 만든다 |
| revision 자유도 | 높음 | **허브가 관리하는 타입은 못 고친다** — revision 타입은 우리 것으로 따로 세워야 함 | 높음(전부 우리 것) |
| 다른 플랫폼과의 정합 | 어긋날 수 있음 | **가장 좋다** — 같은 틀·같은 slug | 우리 안에서만 맞음 |
| 끊길 때 | 해당 없음 | SP 가 내려가면 과제를 못 읽는다 → **캐시 정책 필요** | 해당 없음 |

**A 를 권하지 않는 근거(실측)** — 의존 폐쇄가 플랫폼 전체이고, DynaForge 에는 온톨로지가
전제하는 **부서(`workspaces`)가 없다.** `objects` 는 부서 소유를 전제로 짜여 있다
(`visible_owner_clause`·`require_owner_edit`·`resolve_owner_workspace`). 부서를 같이 들이면
DynaForge 의 인증·권한을 다시 설계하는 일이 된다. 그것은 "심는다" 가 아니라 **두 플랫폼의
합병**이다.

---

## 3. 권하는 것 — **C 를 먼저, B 를 그 뒤에** (한 길의 두 단계)

지금 당장 쓰이는 것은 "이 리포트가 어느 과제의 어느 revision 인가" 다. 그것은 DynaForge
안에서 끝나야 빠르고, 끊기지 않고, `eng_meta` 필터와 맞물린다 → **C.**

그 다음 필요한 것은 "과제 정본을 어디서 받나" 다. 그 답은 이미 정해져 있다(허브/쌍둥이)
→ **B 를 받는 쪽으로만.** C 의 표에 `source`·`external_key` 칸을 처음부터 두면, B 가 붙을 때
표를 안 고치고 **채우기만** 하면 된다.

즉 **C 의 설계를 B 가 올 것을 알고 한다.** 이것이 요점이다.

---

## 4. revision 설계 — 실제로 새로 만드는 것

### 4.1 SP 의 시간 축은 **연도**다. revision 축이 아니다

`temporal_kind` 는 `evergreen`\|`lifecycle`\|`yearly`\|`derived` 이고 걸리는 필터가 `year=Y` 다
(`valid_from_year`·`valid_to_year`·`object_years`). **revision 은 거기 없다.** 새 축이다.

### 4.2 세 가지 길

| | (a) 과제 객체를 revision 마다 | (b) 과제 하나 + revision 을 **관계 속성**으로 | (c) 과제 하나 + **개발리비전 타입**을 따로 ← |
|---|---|---|---|
| 모양 | `key = PRJ-123@dv1` | 관계 `리포트 —(측정)→ 과제` 에 `dev_rev` 속성 | `개발리비전`(key `PRJ-123@dv1`) `part_of` `과제` |
| 허브와 | ★**불가능** — 과제 객체를 우리가 못 만든다(`managed.py`) | 가능 | 가능 — 과제는 허브 것, 리비전은 **우리 것** |
| revision 을 목록으로 보나 | 봄 | **못 봄**(선의 속성이라 1급이 아니다) | 봄 |
| revision 에 속성을 더하나 | 더함 | 선마다 중복 | 더함(기준일·담당·비고) |
| revision 끼리 비교 | 됨 | 어려움 | 됨 |
| 비용 | — | 가장 적음 | 타입 1 + 관계 1 |

→ **(c) 를 권한다.** 근거는 "허브와" 줄이다. (a) 는 허브가 과제를 관리하는 순간 **길이 막힌다** —
실측으로 확인했다: `backend/app/modules/objects/routes.py:2268` 이
`managed.require_objects_editable(object_type, what="만들지")` 로 **객체 만들기 자체를 거절**한다
(고치기 `:1531`·`:2327` · 지우기 `:1645` · 별칭 `:2397` · 되돌리기 `:2700` 도 같다).
열린 길은 묶음 가져오기에 `source` 를 적는 것 하나뿐이고, 그때 `owner == source` 라야 통과한다. (b) 는 SP 의 `property_defs.owner_kind='relation'` 이
실제로 지원하므로 가능하지만, revision 을 **셀 수도 비교할 수도 없다** — 우리가 하려는 것이
"같은 과제의 revision 간 비교" 라면 그것이 1급이어야 한다.

### 4.3 (c) 의 구체안

```
과제 (project)                     kind_class=record  key_policy=required  key_scope=global
  managed_by = "<허브 slug>"        ← B 가 붙으면 채운다. C 단계에서는 "" (우리가 만든다)
  source / external_key             ← 받은 출처와 원천 식별자. 처음부터 둔다

개발리비전 (dev_revision)           kind_class=record  key_policy=required  key_scope=global
  key      = "<과제코드>@<code>"     예: PRJ-123@dv1
  속성      phase(enum pre|dv|pv|pra|mp) · round(enum 1|2|3|r) · seq(number) ·
            baseline(bool) · note(text_long)
  temporal  lifecycle — valid_from_year/to_year 가 자연히 맞는다(dv1 은 2026 에 돌았다)
  managed_by = ""                    ← **우리 것이다.** 이것이 "자체 온톨로지 정보" 다

관계
  dev_revision --part_of--> project        directed · transitive · acyclic
  impact_report --measured_at--> dev_revision
  (session/job 도 같은 관계로 이을 수 있다 — §6 질문 3)
```

★**`seq` 를 데이터로 둔다.** 지금 순서는 코드의 정규식 순서(`pre|dv|pv|pra|mp`)에 **암묵**이다.
SP 가 이 자리에서 배운 교훈이 문서에 적혀 있다 —

> 메타가 데이터에 있어야 하는 이유: 코드에 암묵이면 화면도 MCP 도 그 의미를 알 방법이 없다.
> ReportArchive 가 `p55` 에서 뒤늦게 깨달은 자리다. (`온톨로지-메타모델-설계.md` §3.4)

### 4.4 지금 있는 `eng_meta` 를 어떻게 하나 — **지우지 않는다**

`eng_meta` 는 DataHub 등재 양식과 **같은 모양**이고 필터·패싯이 이미 물려 있다. 그것을 걷어내면
DataHub 쪽까지 같이 손대야 한다. 그래서 —

1. `eng_meta` 는 **그대로 둔다**(등재·검색이 계속 쓴다)
2. `impact_report` → `개발리비전` 관계를 **더한다**
3. 인제스트·PATCH 때 `eng_meta.project`+`dev_revision.code` 로 리비전을 **찾거나 만들고** 잇는다
4. 둘이 어긋나면 **관계가 정본**이고, 어긋났다는 사실을 화면에 띄운다(조용히 맞추지 않는다)

★ 과거 리포트의 자유 문자열 `project` 를 정본 과제에 붙이는 일이 남는다. SP 에 그 장치가 이미
있다 — `ObjectAlias`(별칭)와 ADR 0025 「채울 곳과 별칭 후보」·「못 찾은 말(별칭 후보)」. 같은
방식으로 **별칭 표**를 두고, 못 붙인 것은 **못 붙었다고 목록으로 보여 준다**(추측해서 붙이지
않는다 — 틀려도 그럴듯하다).

---

## 5. 단계 (각 단계 끝에 검증을 붙인다)

| 단계 | 하는 일 | 검증 |
|---|---|---|
| **G-0** | 이 계획에 합의 · §6 답 | — |
| **G-1** | 표 넷(`ont_types` 없이 **고정 스키마**로: `projects`·`dev_revisions`·별칭·관계) + 마이그레이션 | 회귀: 같은 key 중복 거절 · `part_of` 순환 거절 · `seq` 정렬 |
| **G-2** | `source`·`external_key` 칸과 **받기만 하는 경로**(`managed_by` 와 같은 규약) | 회귀: managed 과제를 고치려 하면 거절 |
| **G-3** | 인제스트·PATCH 에서 `eng_meta` → 리비전 **찾기/만들기/잇기** | 회귀: 어긋남을 **띄운다**(조용히 안 맞춘다) |
| **G-4** | 과거 리포트 붙이기 — 별칭 + **못 붙인 목록** | 실측: 붙은 수 / 못 붙은 수를 보고한다(추정 금지) |
| **G-5** | API·MCP 도구 — 과제·리비전 목록, 리비전 간 리포트 비교 | `reports_smoke` 에 항 추가 |
| **G-6** | 화면 — 리포트 목록의 과제·리비전 필터, 리비전 비교 | Playwright 로 실동작 |
| **G-7** (B) | 허브가 정해지면 받기 경로를 켜고 `managed_by` 를 채운다 | 받은 뒤 우리 화면에서 **못 고치는지** 확인 |

**G-1 을 "고정 스키마" 로 하는 이유** — SP 처럼 `object_types` 를 데이터로 두면 거기서 화면
자동생성·권한·`list_view`·인터페이스가 줄줄이 따라온다(그것이 34,180줄의 정체다). 우리가 지금
필요한 축은 **둘**(과제·리비전)이다. 둘을 위해 메타모델을 들이는 것은 역전이다. 축이 넷을
넘어가면 그때 B 로 간다 — 그 판단 기준을 지금 적어 둔다.

---

## 6. 모르는 것 — 가정으로 메우지 않는다

1. **허브가 어느 인스턴스입니까?** `managed.py` 는 허브가 있다고 전제하는데, 다섯 중 어느
   것인지(MatNexus? TestScope? 아직 없음?) 저는 모릅니다. 이 호스트에는 SP 계열 **백엔드가
   안 떠 있습니다** — 8010~8072 중 열린 것은 `8013` 하나인데, 그것은 컨테이너 안의 MCP 서버
   (`cwd=/mcp-server`)이고 게이트웨이 설정에도 없습니다. SP 의 포트 표(MatNexus 8010/8011/8012
   …)와는 무관합니다. 운영에서는 다를 수 있습니다 — 저는 이 박스만 봤습니다.
2. **과제 코드의 정본 형식은 무엇입니까?** 지금 `project` 는 자유 문자열이고 예시를 못
   봤습니다. `key_scope=global` 로 두려면 형식이 정해져야 합니다.
3. **리비전에 이을 것은 리포트뿐입니까, 세션·잡까지입니까?** 해석을 돌리기 전부터 과제를
   알아야 한다면 `Session` 에 이어야 하고, 그러면 제출 화면이 바뀝니다.
4. **`design_variation`·`doe` 도 축으로 올립니까?** 지금은 `eng_meta` 의 문자열입니다.
   올리면 축이 넷이 되고, §5 의 "넷을 넘으면 B" 기준에 닿습니다.
5. **받은 리포를 `vendor/` 에 계속 둡니까?** 지금은 추적하지 않습니다(18MB · 중첩 `.git`).
   참조가 끝나면 지워도 됩니다 — 계획서에 필요한 `file:line` 은 이 문서에 다 적었습니다.

---

## 부록. 받은 저장소에서 참조한 자리

| 무엇 | 어디 |
|---|---|
| 온톨로지 메타모델 설계(정본) | `docs/온톨로지-메타모델-설계.md` (1,039줄) |
| 그 결정 배경 | `docs/adr/0005-온톨로지-메타모델.md` |
| 허브/쌍둥이 — 받기만 한다 | `backend/app/modules/ontology/managed.py` |
| `managed_by` 칸 | `backend/app/modules/ontology/models.py:258`·`:344`·`:503` |
| 시간 축(연도) | `docs/온톨로지-메타모델-설계.md` §4.3 |
| 식별자 정책 | 같은 문서 §4.1 |
| 속성 일곱 + 검증 | 같은 문서 §4.2 |
| 관계 메타(transitive·acyclic) | 같은 문서 §3.4 |
| 별칭·채울 곳 | `docs/adr/0025-채울-곳과-별칭-후보.md` |
| 바깥 시스템 받기 | `backend/app/modules/datasources/` (`odata`·`rest`·`file`·`sp_core`·`ra_reports`) |
| RA 보고서를 기록으로 | `backend/app/modules/datasources/ra_reports.py` · `docs/adr/0018-…` |
| 포크 절차 | `docs/새-플랫폼-만들기.md` (828줄) · 포트 표 §3.6 |
| MCP(얇은 프록시) | `mcp_server/server.py:44` (`PLATFORM_API_BASE`) |
