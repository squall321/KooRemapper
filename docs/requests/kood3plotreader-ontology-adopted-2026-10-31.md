# 알림 — 해석 어휘(cae_*) 채택 · 적재 · 질의를 지었습니다 + 7-1 길에서는 꾸러미가 안 생깁니다(정하실 것 하나) (2026-10-31)

**보내는 곳** KooD3plotReader · **보내는 쪽** DynaForge(KooRemapper) · 앞선 문서 — 우리 검토 답신 `kood3plotreader-ontology-review-2026-10-31.md`(`7e8252d`),
그쪽 계약 초안 2(`docs/ontology_2026-10/package-contract.md`).

## 1. 지은 것 (사용자 결정 10-31 — (가) 캠페인 수준만 행으로)
| 커밋 | 무엇 |
|---|---|
| `0e9c9da` | 정본 `platform/core/ontology/dynaforge-cae.json` = 그쪽 `e6cce7f` 의 0.3 **바이트 그대로**(sha256 `72ff9b49…4d64`) · 받아들인 판 목록 · 꾸러미 검사(순수 함수) |
| `220df28` | 마이그레이션 0020(행 · 선에 `report_id` FK CASCADE) · 리포트에 싣기 `POST /reports/{id}/cae` · 보기 `GET /reports/{id}/cae` · 리포트를 건너는 질의 `GET /cae/parts` · `/cae/load-paths`(읽을 수 있는 리포트만) · 번들 반입이 같은 줄기 꾸러미를 저절로 |
| `4ada7ba` | MCP 넷 — `attach_cae_package` · `report_cae` · `find_cae_parts` · `find_cae_load_paths` |
| `57a41bf` | 화면 — 리포트 상세 「해석 온톨로지」(파트 판정 · 하중 경로 상위 · 경고 · 꾸러미 붙이기) |

- **받아들인 판** — 지금 0.3 하나(`72ff9b49…`). 꾸러미의 `vocabulary.sha256` 이 목록 안이면 **그 판의 어휘로** 검사합니다. 정본을 올릴 때는
  옛 바이트를 `platform/core/ontology/history/` 로 옮겨 목록에 남깁니다 — 늦게 바뀌는 노드 SIF 의 꾸러미가 막히지 않게(그쪽 권고 그대로).
- **실물로 잰 것** — 표본 셋(v14 · impA · deep)이 검사를 지납니다. v14 는 dev 화면에서 실물 `report.html` 을 반입하고 꾸러미를 붙였습니다 —
  행 94(캠페인 1 · 파트 23 · 접촉 27 · 경로 21 · 소견 22) · 선 115(다대다 114 + 우리가 긋는 `campaign_report`) · 런 20/20 맞음.
  같은 바이트는 멱등, 남의 HTML 지문 · 다른 종류(부분충격 꾸러미를 전각도 리포트에)는 거절하고 아무것도 안 바뀝니다.
- **0.4 `flow_scalars_only`** — 넣는 데 동의합니다(그쪽 표식이 배포될 때 함께). 정본이 이쪽이므로 칸 정의(키 · 꼴 · 뜻)를 보내 주시면
  우리가 정본을 0.4 로 올리고(0.3 은 history 로 · 받아들인 판에 남김) 커밋을 알려 드립니다 — 그 바이트를 그대로 옮겨 주십시오.

## 2. 정하실 것 — 후처리 예약(7-1) 길에서는 꾸러미가 생기지 않습니다 (소스로 본 것)
- 7-1 길의 리포트 셸(pyKooCAE `Runner/PostprocessShellGenerator.py`)은 `koo_sphere_report -o "$OUTPUT_DIR/sphere_report.html" --json
  "$OUTPUT_DIR/sphere_report.json"` 를 바로 부릅니다(부분충격은 `impact_report.html`). 꾸러미 단계가 없습니다.
- 그쪽 꾸러미 단계는 `scripts/post_analyze.sh` 의 `run_step_ontology`(Step O) 하나이고 `<TEST_DIR>/report*.json` · `impact_report.json` 만 봅니다.
  `koo_sphere_report` · `koo_impact_report` 소스에는 꾸러미를 쓰는 곳이 없습니다(grep — 돌려 보지는 않았습니다. 틀렸으면 알려 주십시오).
- 선택지 둘(그쪽이 정하실 일입니다).
  - **(A) 도구가 스스로** — `koo_sphere_report` · `koo_impact_report` 가 `-o` HTML 곁에 `<줄기>.ontology.json` 을 씁니다(deep 이 이미 그렇게 합니다).
    두 길(post_analyze · 7-1)이 같은 코드로 같은 파일을 냅니다. Step O 는 그때 겹칩니다.
  - **(B) 7-1 셸이 부른다** — pyKooCAE 셸이 도구 뒤에 SIF 의 `koo_ontology sphere "$REPORT_JSON" --test-dir "$TEST_DIR" --yield-stress … [--yield-map …]`
    를 부릅니다(옛 SIF 면 건너뜀). 항복값을 리포트와 같게 넘겨야 안전율이 리포트 소견과 같습니다. pyKooCAE 에 우리가 청합니다.
  - 우리 의견은 (A) 입니다 — 꾸러미를 만드는 규칙(짝 HTML 지문 · 항복값)이 생산 쪽 한 곳에 남고, 길이 늘어도 따로 손댈 셸이 없습니다.
    다만 도구가 꾸러미 실패로 죽지 않아야 합니다(리포트가 정본).
- 어느 쪽이든 결과 파일은 `<출력>/<kind>_report.ontology.json` 이고, 머리 `source.html` 은 `<kind>_report.html` 의 지문이어야 합니다 —
  DynaForge 는 그 HTML 을 반입하고 지문으로 짝을 짓습니다.
- KooSlurm 에는 귀환 매니페스트에 그 파일(경로 · 크기 · sha256)을 적어 달라고 따로 청했습니다(`kooslurm-ontology-manifest-request-2026-10-31.md`).
  그리고 `koo_ontology` 가 든 후처리 이미지가 stcx 에 깔려야 이 길이 섭니다.

## 3. 묻는 것
1. (A) · (B) 어느 쪽으로 하실지 — (B) 면 알려 주십시오, pyKooCAE 에 청하겠습니다.
2. `koo_ontology` 가 든 후처리 이미지의 판 이름(stcx 설치 요청에 함께 적겠습니다).
