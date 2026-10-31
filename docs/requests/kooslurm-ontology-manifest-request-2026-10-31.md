# 요청 — 귀환 매니페스트의 리포트 항목에 **온톨로지 꾸러미**(경로 · 크기 · sha256)를 더해 주십시오 (2026-10-31)

**보내는 곳** KooSlurm(`dashboard/backend_5010/return_manifest.py`) · **보내는 쪽** DynaForge(KooRemapper)
**한 줄** 후처리(KooD3plotReader)가 리포트 곁에 내는 해석 온톨로지 꾸러미를 DynaForge 가 리포트에 싣기 시작했습니다(사용자 결정 10-31).
후처리 예약(7-1) 길은 귀환 매니페스트만 읽으므로, 꾸러미도 저절로 받으려면 매니페스트가 그 파일을 적어야 합니다.
**성격** 작은 덧붙임입니다(새 칸 하나 · `version` 그대로). 모양은 아래가 제안이고, 다르게 하실 까닭이 있으면 그쪽 모양으로 맞추겠습니다.

## 1. 바라는 모양

`_report_entry` 가 만드는 `reports[]` 항목마다 `ontology` 칸 하나:

```json
{"kind": "sphere", "path": "output/sphere_report.html", "present": true, "size": 6217408, "sha256": "999d…",
 "reason": null, "log_tail": null,
 "ontology": {"path": "output/sphere_report.ontology.json", "present": true, "size": 509753, "sha256": "17b7…"}}
```

- **자리** — HTML 과 같은 폴더 · 같은 이름 줄기 `<출력>/<kind>_report.ontology.json`. 생산 쪽 짝짓기 규칙이 「꾸러미는 짝 HTML 과
  같은 폴더 · 같은 줄기」입니다(KooD3plotReader `docs/ontology_2026-10/package-contract.md` §1).
- **없으면** `{"path": …, "present": false, "size": null, "sha256": null}` — 까닭은 필요 없습니다. 꾸러미는 덧붙이는 산출물이라
  옛 후처리 이미지에서는 원래 안 생깁니다. 칸이 아예 없으면(옛 작성기) DynaForge 는 「작성기가 옛판」으로, `present: false` 면
  「이번 잡에 꾸러미가 없다」로 구별해 보입니다.
- **`ok` · 종료 코드는 바꾸지 마십시오** — 꾸러미가 없어도 리포트가 있으면 지금처럼 `ok: true` · 0 입니다. 리포트가 정본이고
  꾸러미는 리포트에서 다시 만들 수 있습니다.
- **`version` 은 1 그대로** — 칸을 더하기만 합니다. DynaForge 의 매니페스트 판정(`platform/backend/app/worker/postprocess_return.py`
  `judge`)은 `kind · present · path · size · sha256 · reason · log_tail` 만 읽고 모르는 칸은 건너뜁니다(소스로 확인).
- 시험 제안(`tests/test_return_manifest.py`) — 꾸러미 있음 → 네 칸이 채워짐 · 없음 → `present: false` · 두 경우 모두 `ok` 가 리포트만으로
  정해짐.

## 2. 지금 이 길에서는 꾸러미가 생기지 않습니다(소스로 본 것 — 먼저 넣으셔도 해가 없습니다)

- 7-1 길의 리포트 셸은 pyKooCAE `Runner/PostprocessShellGenerator.py` 가 만들고 `koo_sphere_report -o "$OUTPUT_DIR/sphere_report.html"
  --json "$OUTPUT_DIR/sphere_report.json"` 를 바로 부릅니다(부분충격은 `impact_report.html`). 꾸러미 단계가 없습니다.
- 생산 쪽의 꾸러미 단계는 KooD3plotReader `scripts/post_analyze.sh` 의 `run_step_ontology`(Step O) 하나이고, 그것은
  `<TEST_DIR>/report*.json` · `impact_report.json` 만 봅니다 — 7-1 길의 `<출력>/sphere_report.json` 은 다루지 않습니다.
- 그래서 이 길로 꾸러미가 생기려면 생산 쪽이 정할 것이 하나 있습니다 — (A) `koo_sphere_report` · `koo_impact_report` 가 `-o` HTML 곁에
  스스로 쓰거나(deep 리포트가 이미 그렇게 합니다) (B) pyKooCAE 셸이 도구 뒤에 `koo_ontology` 를 부르거나. KooD3plotReader 에 따로
  물었습니다. 그리고 `koo_ontology` 가 든 후처리 이미지가 stcx 에 깔려야 합니다(아직).
- 이 요청은 그 결정과 무관한 모양이라 먼저 넣으셔도 됩니다 — 그때까지는 `present: false` 로 보일 뿐입니다.

## 3. DynaForge 쪽(모양이 정해지면)

`postprocess_return` 이 리포트를 반입한 뒤 `ontology.present` 면 같은 파일 REST 로 받아 크기 · sha256 을 맞춰 보고 그 리포트에 싣습니다
(`attach_ontology` — 어휘 판 · 짝 HTML 지문 · 종류 · 런 키를 검사, 맞지 않으면 아무것도 안 싣는다). 꾸러미 실패는 잡을 실패로 만들지 않고
경고로 남깁니다. 리포트를 사람이 올리는 길(화면 · MCP · 번들)은 이미 됩니다(커밋 `0e9c9da` · `220df28` · `4ada7ba` · `57a41bf`).

## 4. 묻는 것
1. 위 모양(리포트 항목 안 `ontology`)으로 좋습니까 — 최상위 목록이 낫다고 보시면 그쪽으로 맞춥니다.
2. 넣으시면 커밋을 알려 주십시오. DynaForge 는 그 판을 기준으로 받는 쪽을 짓습니다.

## 5. 답 (10-31)
KooSlurm `b6a3d75c`(origin/main) — 제안 모양 그대로(리포트 항목 안 `ontology`, 키 순서 `log_tail` 뒤, 리포트가 없어도 칸은 늘 있음, ok · 종료 코드는
리포트만으로, version 1). icn401 반영 뒤 제출한 잡부터 칸이 생긴다. DynaForge 받는 쪽은 이 판을 기준으로 지었다(`postprocess_return`).
