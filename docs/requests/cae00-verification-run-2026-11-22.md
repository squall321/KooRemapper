# cae00 검증런 안내 — 미룬 결함 3차(1 ~ 7판) · DF 2차(① ~ ⑥) · 2026-11-22

**누가 · 어디서** 사용자가 cae00(실사용 서버)에서 돌린다. 이 박스(dev)에서는 합성 사례 · 표본으로만 쟀고, 요청서의 대조 파일과 LS-DYNA(라이선스
만료)로는 재지 못했다 — 그 대조가 이 검증런의 몫이다. 받는 절차 · 확인 표는 `hwax-portal-cae00-checks-2026-10-30.md` §1-7 ~ §1-14.
요청서 원문의 과제 이름 · 경로는 이 문서에 옮기지 않는다 — 각 줄의 「요청서 DF-xx 검증 방법」 이 가리키는 파일로 대조한다.

## 0. 받기
1. `git pull && update-all` — Drive 판 `dist-20261123-094507Z`(바이너리 `139036f2`)와 코드 `6ac0f7e` 이거나 그 뒤(3차 7판 — §1 의 6 · 7판 줄은 이 판이어야 잰다).
2. `bash platform/infra/scripts/migrate.sh` — 0021 ~ 0026 가운데 빠진 것이 오른다.
3. API · MCP 재기동(도는 잡 0 확인 뒤) → `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` 가 도구 120 · PASS.

## 1. 덱 연산(미룬 결함 3차) — LS-DYNA 로 돌려 볼 것
| 무엇 | 어떻게 | 볼 것 |
|---|---|---|
| battery 덱(5판) | 적층 · 권취 × dent · side · bare · swell 기본 설정을 `battery` 로 짓고 `info --strict` | rc 0 · 그 덱을 LS-DYNA 로 — 키워드 단계를 넘는가(전엔 없는 MID 8 · 세트 3 에서 멈췄다) · SBOPT `3`(정수)를 받는가 |
| 적층 side · no_impactor | 같은 꼴 | side 덱에 바닥판이 있고 바닥판 접촉이 없는 것이 맞는지(목록 밖 — 바닥판 접촉은 짓지 않는다) · no_impactor 덱은 경계가 없다(쓰는 쪽 몫) |
| LONG=Y · I10 덱(2 · 3판) | 운영의 실물 long 덱을 map · squeeze · tetremesh · unfold 에 | rc · 산출을 LS-DYNA 로 읽히는가(리포에 실물 long 덱이 없어 합성으로만 쟀다) |
| `*MAT_T1` 철자 · 열 해석의 없는 TMID(3판) | 열 해석 덱 하나 | `info` 의 의심 줄 · LS-DYNA 가 없는 TMID 에서 멈추는지(구조 해석은 받는다 — 열 해석은 못 쟀다) |
| 인클루드 크기 관문(4판) | 큰 인클루드 닫힘 덱 | 남은 메모리 안이면 그대로 돌고, 넘치면 열기 전에 rc 1 과 까닭 |
| battery phase_modes 사슬(6판) | `use_dynain: true` 에 `batch:` 아래 `phases: [1, 2]` · `phase_modes: [swell, dent]`(블록 꼴)로 적층 · 권취를 짓고 phase 1 을 LS-DYNA 로 돌려 dynain 을 낸 뒤 phase 2 | phase 1 덱에 압입자 · 바닥판이 없고 탭 · PCM 은 있다 · phase 2 가 phase 1 dynain 을 읽어 셀 · 탭 · PCM 이 제자리에서 시작하는가(이 박스는 번호 · 좌표 대조만 했다) |
| contact.depth(6판) | `contact:` 아래 `depth: 2`(블록 꼴)로 battery 덱 | 자동 접촉 Card A 의 DEPTH 2 · 솔버가 받는가 · 기본 5 와 접촉력 차이 |
| 권취 나선 판(6판) | `wound:` 아래 `flat: false`(블록 꼴)로 battery 덱 · `info --strict` | rc 0 · LS-DYNA 가 키워드 단계를 넘는가(전엔 전해질 PART 의 섹션 33 이 없어 멈췄다) |
| 들여 쓴 `*` 제목(6판) | 제목이 `*` 로 시작하는 실물 덱이 있으면 contact · cclip · matswap · merge · optimize · modelmeta(7판부터 matdb · elform · update · stabilize · ale · rebind · carryover 등)에 | 산출이 제목만 바꾼 대조 덱의 산출과 같다(합성 사례로만 쟀다) |
| 권취 강체 방향(7판) | 권취 dent · side 기본 설정 battery 덱을 LS-DYNA 로 | 초기화에서 음의 부피 · 음의 질량 없이 넘어가는가(전 판 덱과 바닥판 · PCM 요소 줄 25 개만 다르다 — 바로 선 차례) |
| ale EOS 제목(7판) | `*EOS_…_TITLE` 인 사용자 재질 파일로 ale | 산출 EOS 의 Card 1 EOSID 가 PART 의 EOSID 와 같고 제목 줄이 그대로 · 솔버가 받는가 |

## 2. 캠페인(DF ① ~ ③) — 실제 KooChainRun 귀환 목록으로
| 무엇 | 어떻게 | 볼 것 |
|---|---|---|
| 적재(DF-01) | `create_campaign` → `ingest_campaign_manifest`(런 목록) → 런마다 intake | `campaign_ingest_status` 의 받음 + 건너뜀 + 거절 + 아직 = 목록 수 |
| 출처 · 건강(DF-02 · 03) | 런 목록에 `provenance` · `health` 를 실제 꼴로 | 모르는 열쇠 422 가 나면 만드는 쪽 꼴과 다르다 — 받는 쪽을 맞춘다. `campaign_health_table` 머리 줄 「유효 n / 전체 N」 |
| 추출 · 삭제 허가(DF-04) | `extraction` · `set_campaign_required_extractions` | `campaign_deletion_clearance` 가 지워도 되는 런만 allow(조회만) |

## 3. 분석(DF ④ ~ ⑥) — 요청서의 검증 방법 파일과 대조
| 요청서 | 도구 | 대조 |
|---|---|---|
| DF-05 각도 통계 | `set_campaign_part_groups` → `campaign_angle_stats` · `campaign_angle_table`(두께축은 덱에 맞게) | 요청서 DF-05 검증 방법의 각도 표 · 점수 · 요약 파일과 열 · 값(방향 수 · 2 회 이상 충격 비율). 충격 구간은 런 목록 `impacts` 로 넣어야 셈한다 |
| DF-06 피크 표 | `campaign_peak_table` | DF-06 검증 방법의 피크 · 충격 표(시각은 ms) |
| DF-08 여유 | `set_campaign_criteria`(MatNexus 기준값 · 판) → `campaign_part_margin` | DF-08 수용 기준의 가운데값 · 넘은 비율(인터포저 항복 기준) |
| DF-09 구면 지도 | `campaign_sphere_map` | DF-09 검증 방법의 격자 스크립트 출력과 격자값(같은 보간 규칙 — 8 방향 · 1/θ² · 0.5° · 가운데 맞춤은 cos 위도 가중 열 평균) |
| DF-10 자리 | `set_campaign_sites` → `campaign_site_table` · `campaign_site_map` | DF-10 검증 방법의 자리 결과 파일(보드 ÷ 기준 가운데값 · 넘은 자리 수) · 빠진 자리 · footprint 합성 경고 |
| DF-11 리비전 | `import_part_map`(짝 근거 필수) → `compare_campaigns` | DF-11 검증 방법의 짝 후보 파일을 올려 힌지 짝 · 공통 DOE 수 |
| DF-12 설정 쌍 | `set_campaign_pair_rule` → `compare_config_pairs` | DF-12 의 쌍 판정 스크립트와 쌍별 판정 |
| DF-13 묶음 | `build_report_bundle` → `report_bundle(items=true)` | 보고 영상이 읽던 숫자 JSON 과 같은 값 · 다시 지으면 바뀐 숫자만 새 판 |
| DF-07 핫스팟 | `set_campaign_frame_offset` → `campaign_hotspot_sites` | DF-07 의 재집계 결과와 자리 · bbox 포함률 99 % 이상 |
| DF-15 세션 | `PATCH /sessions/{id}` 로 덱 판 · CAD 연결 → `get_session` · `rename_session_part` | 판이 다르면 `revision_warning` · 제목만 바뀐 덱 |

## 4. 결과를 알려 줄 때
- 맞지 않는 줄은 「도구 · 인자 · 기대값 · 받은 값」 을 적어 주면 그 줄부터 고친다. 만드는 쪽(KooChainRun · 생성기)의 실제 꼴이 요청서 표와
  다르면 그 꼴 하나만 보내 주면 받는 쪽을 맞춘다.
- 남은 물음(고르지 않고 남긴 것) — 최종 보고의 「물음」 절.
