# Plan — K파일 메타 강화 파이프라인 (k-enrichment)

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | DataHub에 K파일을 올려도 지금은 "파일 덩어리"일 뿐이다. 어떤 파트가 어떤 파트와 연결되는지(connectivity), 각 파트의 크기·부피·재질이 무엇인지 메타데이터가 없어 AI 분석·검색·재료 연계가 불가능하다. |
| **Solution** | KooRemapper에 구조화 추출 op(`modelmeta`)를 신설해 K파일에서 파트별 기하 메트릭(외부 표면적·부피·xyz 정사영 면적)·재료(ID·이름·대표 물성)·접촉 기반 connectivity를 JSON으로 뽑고, 이를 DataHub SIM 레코드로 올려 MaterialTwin 재료 카드(이미 70건 sync됨)와 이름 매칭으로 연결한다. 진입은 HEAX Hub 포탈 등록으로 연다. |
| **Function/UX Effect** | HEAX Hub에서 KooRemapper 실행 → K파일 업로드 → 파트 연결도·파트별 특성·재료 물성이 자동으로 DataHub에 등록 → "이 모델에서 NBR 러버가 쓰인 파트와 그에 붙은 파트" 같은 질의가 성립. |
| **Core Value** | K파일이 검색·연계 가능한 지식 자산이 된다 — 모델→파트→재료→물성으로 이어지는 조회 체인의 완성. |

작성일 2026-07-20. 정찰 근거: scout-k-enrichment 워크플로(4 에이전트, 파일:라인 실측).

---

## 0. 현재 준비물 평가 — "제대로 된 흐름인가?"

**결론: 방향은 맞고, 이미 깐 것들이 전부 재사용된다. 다만 연결 고리 3개가 미완.**

| 준비물 | 이 흐름에서의 역할 | 판정 |
|---|---|---|
| AIDataHub `cae` kind + SIM 레코드 + eng_meta (d58ddf1) | K파일 첨부·해석 job 레코드·과제/단계 축 — 수신측 그릇 | ✅ 그대로 사용 |
| normalizer 보존 로직 (B4 패턴) | 신규 필드 인제스트 생존 — 이번에 2개 필드만 더 등록 | ✅ 패턴 확립됨 |
| MaterialTwin → AIDataHub sync (dfc93d6, 70건 실측) | 재료 카드가 이미 DataHub에 있음 (DOC-MX-MAT-*, doc_type=material_card) | ✅ 연계 대상 존재 |
| MaterialTwin이 HEAXHub 앱으로 등록된 사례 | KooRemapper 등록의 실물 본보기 (manifest 1파일) | ✅ 본보기 |
| KooRemapper contact 파서/탐지기 (ct_parseContacts/ct_analyze/ct_detectAllPairs) | connectivity의 엔진 — 이미 완전 구현 | ⚠️ 출력이 콘솔 텍스트뿐 |
| KooRemapper 면적·법선·정사영 코드 (ld_extractSurface 등) | 파트 메트릭의 엔진 | ⚠️ load/contact 내부 static — 공용화 필요, HEX8 부피 함수 부재 |
| material_db.json 525종 + matdb op | 재료 이름·카테고리·대표 물성 소스 | ✅ (MaterialTwin 데이터의 원천이 KooRemapper라 이름 정합성 높음 — attributes.source='KooRemapper' 실측) |

**미완의 연결 고리 3개**
1. KooRemapper에 **구조화(JSON) 추출 op가 없다** — info는 전체 집계, contact analyze는 콘솔 텍스트.
2. DataHub SIM content에 **파트 목록·connectivity 표준 자리가 없다** + content 내부는 검색 API가 못 본다(파트명·재료명을 tags/subject_keywords로 끌어올려야 검색됨).
3. materialtwin sync가 **수치 물성(attributes)을 안 가져온다** — "대표 물성 조회"가 지금은 MaterialTwin 웹까지 hop해야 가능.

---

## Phase A — HEAX Hub 등록 (P0, 최우선 · 반나절)

HEAXHub 등록 단위는 `integrations/<slug>/.portal/manifest.yaml` 1파일. 스캐너가 기동 시+5분 주기로 자동 반영. `scripts/register-url.sh kooremapper <upstream> <mode>`가 파일을 생성해준다.

| # | 작업 | 검증 |
|---|---|---|
| A1 | KooRemapper 프론트(Vite)의 base path 확인 — `/apps/kooremapper/` 서브패스에서 자산 로드 가능한지 | vite.config base 확인 |
| A2 | 모드 결정 후 등록. **1차 권장: external_link(새 탭, 기존 주소 그대로)** — 가장 안전. proxy는 (a) self-signed :8443에 TLS 검증 실패 예상(insecure_skip_verify 미설정 실측) (b) SPA base 이슈 (c) forward_auth 없음(무인증 노출) 3가지 리스크가 있어, http 업스트림(:8089)+base 대응 확인 후 2차에 전환 | `curl http://localhost:4180/apps/kooremapper/` + 포탈 카드 노출 |
| A3 | 즉시 반영: backend에서 scan_integrations_periodic 1회 수동 실행 | by_action에 created 확인 |
| A4 | (v2) `mcp: {expose: true}` — KooRemapper MCP를 HWAX MCP Gateway에 편입. published+기동이력 조건이 external 앱에 성립하는지 확인 후 | /api/v1/mcp/servers에 노출 |

## Phase B — KooRemapper `modelmeta` op 신설 (P1·P2·P3 엔진 · 2~3일)

기준 코드 무손상 원칙 유지(additive, cclip 전례). 신규 op 1개 + 공용 헬퍼 추출.

| # | 작업 | 근거/재사용 |
|---|---|---|
| B1 | 기하 헬퍼 공용화 — ld_extractSurface(파트별 자유면)·faceinfo(면적/법선)·정사영 합산을 load 내부 static에서 공용 유틸로 추출(원 코드는 위임 호출로 무회귀) | ModelAssembler.cpp:9873/9897/10427 |
| B2 | HEX8/PENTA6 부피 함수 신설 — 면 중심 tet 분해(기존 TET4 함수 재사용). 정사영 면적은 sum(area·abs(n·d))/2 (닫힌 표면 왕복 상쇄; 개방 쉘은 근사임을 리포트에 명시) | ElementQualityChecker.cpp:76 |
| B3 | 재료 메타 — PID→MID(파서 확보) + 구조 파싱 5종 물성 + material_db.json mid/이름 lookup(name·category·E·rho·대표물성) + *MAT_*_TITLE 범용 제목 추출 보강 | KFileReader.cpp:755, matdb.cpp:100 |
| B4 | connectivity — ct_parseContacts+ct_analyze(기존 *CONTACT의 SSID/MSID→파트 해석) 결과를 edges로 구조화. 옵션 `detect: true`면 ct_detectAllPairs(기하 탐지)도 병기(edge에 source: contact/geometric 구분) | contact_helpers.cpp:1284/609 |
| B5 | op 조립 — `modelmeta` (yaml: model, output, detect, gap_tol, projection 등) → `<output>_modelmeta.json` 출력: `{model:{...}, parts:[{pid,title,elem_type,n_elems,bbox,area_ext,volume,proj:{x,y,z},material:{mid,name,category,props}}], connectivity:{edges:[{a,b,a_title,b_title,source,type,fs}]}}` | cclip op 골격 전례 |
| B6 | 카탈로그 47번째 op 등록 → CLI/웹/MCP 자동 전파. 규정 빌드(build_linux_compat.sh) + 배포(cli.sif/appt313/api) | catalog_data.json |
| B7 | 검증 — 해석 대조(단위 박스: 면적 6·부피 1·정사영 1 등 닫힌형 값), cclip 예제 모델(접촉 포함), 기존 46 op 골든 회귀, 적대적 리뷰 워크플로 | tools/ 자기검증 전례 |

## Phase C — DataHub 수용측 보강 (반나절~1일)

| # | 작업 | 근거 |
|---|---|---|
| C1 | SimContent에 `components: list[dict]`·`connectivity: dict` 필드 추가 + normalizer _extract_sim 보존 리스트 등록(eng_meta 패턴 1줄) + 회귀 테스트 | sim.py, normalizer.py:302 |
| C2 | 검색 끌어올림 관례 확정 — 파트명·재료명을 `subject_keywords`/`tags`(`part:`/`mat:` 접두)로 승격(업로더가 기입). content 내부는 검색 API가 못 보므로(실측: content WHERE 사용 0건, SIM은 sections/임베딩도 없음) 이것이 유일한 검색 수단 | search_svc.py 실측 |
| C3 | 재료 연계 — components[].material에 `record_id`(DOC-MX-MAT-*) 기입 + 레코드 `related_record_ids`에 재료 레코드 추가. 매칭은 이름 기반(/api/records?q= 또는 /api/search?mode=fts), 미매칭은 unmatched 목록으로 보고 | 70건 실측, q= ILIKE |
| C4 | materialtwin sync 보강 — mapping_rules에 attributes(수치 물성: E0, Prony, mat_type 등) 매핑 추가 후 재sync → 재료 카드에서 "대표 물성"이 바로 조회되게 | sync_sources.yml (+45줄 커밋 전례) |
| C5 | cad_cae_metadata_rules.md에 components/connectivity/검색 승격 관례 추가 | 문서 단일 진입점 |
| C6 | (v2) related_record_ids 역참조 API + content @> 필터 — GIN 인덱스는 둘 다 이미 있음, 서버 1쿼리씩 | db/models.py 실측 |

## Phase D — 통로 연결 + E2E (1일)

| # | 작업 | 비고 |
|---|---|---|
| D1 | AIDataHub api 재기동 — d58ddf1(+C1)이 라이브에 반영되는 선행 조건 | :8001 구프로세스 |
| D2 | KooRemapper → DataHub 업로더 — KooRemapper 플랫폼 백엔드에 `publish to DataHub` 액션: modelmeta job 실행 → JSON → SIM 레코드 조립(eng_meta 포함, 파트명/재료명 tags 승격, 재료 record_id 매칭) → K파일+JSON 첨부(kind=cae) 번들 POST(:8001) → 레코드 ID 반환 | "KooRemapper쪽에서 해야하는 일" |
| D3 | E2E 파일럿 — cclip 보드 K파일 1건 왕복: 업로드→modelmeta→DataHub 등록→(a) 파트명 검색 (b) 재료 카드 hop (c) connectivity 확인 | 성공 기준 명시 |

## 결정 필요 (착수 전 확인)

1. **HEAXHub 1차 모드** — external_link(안전) vs proxy(:8089, base 확인 후). 권장: link로 시작.
2. **정사영 이중카운트** — /2(닫힌 표면 정확, 개방 쉘 근사) 채택 여부.
3. **modelmeta 이름** — modelmeta / enrich / partinfo 중.
4. **connectivity 크기 상한** — 파트 수백 개 모델의 content 폭주 대비(edges 상한+truncated 플래그 제안).

## 리스크

- SPA 서브패스(base) 미대응 → A2에서 link 모드 폴백으로 흡수.
- 재료명 미스매치 → 원천이 동일(KooRemapper→MaterialTwin)이라 낮음; unmatched 보고로 가시화.
- normalizer 화이트리스트 재발 → C1에서 회귀 테스트 동시 추가(이번에 확립한 패턴).
- 대형 모델 자유면 추출 비용 → modelmeta는 비동기 job이라 UX 영향 없음; 시간만 리포트.

## 범위 밖 (v2)

HWAX MCP Gateway 편입(A4) · content @> 검색/역참조 API(C6) · SIM 레코드 semantic 검색(섹션 생성) · DataHub 웹 UI의 connectivity 시각화 · 소성 곡선 등 상세 물성 구조화.
