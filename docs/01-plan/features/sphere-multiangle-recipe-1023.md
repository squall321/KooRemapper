# 다각도 새 판 sphere 리포트 만들기 — 조리법 (2026-10-23, 메모리 때문에 보류)

**왜** 새 판 sphere 고정본(`/data/koopark/report_fixtures/sphere_hotspot_v1018`)은 각도가 하나라, 포락 · 각도 축 히트맵 · 상위 60각도 하중경로 상세를
실물로 재지 못했다(결정 5B). 아래는 하위 에이전트가 코드 · 로그로 찾은 길이다 — 실제 데이터로는 아직 안 돌렸다.

## ⚠ 먼저 메모리
- 원본 `Test_005_Fibonacci_100` — 100각도 · 런마다 d3plot 250개 18.2 GB · **4,952 상태**(ENDTIM 5e-3). 분석기는 상태를 전부 메모리에 올린다
  (`KooD3plotReader/src/analysis/SinglePassAnalyzer.cpp:96`). 같은 모델 실측 — 핫스팟 없이 2:56~3:43 · **34.4 GB** · 런마다 170 MB.
  고정본의 원본 런(497 상태)은 58.6 초 · 2.25 GB 였다.
- 10-23 확인 때 이 박스는 쓸 수 있는 메모리 12 GB · 스왑 39/39 GB 라 돌리지 않았다. 계산노드는 2 CPU · 4 GB 이고 꺼져 있다 — 헤드에서 돈다.
- `koo_deep_report` 에 상태를 솎는 옵션은 없다.
- **하나 먼저 `/usr/bin/time -v` 로** 돌려 시간 · 최대 RSS 를 본다.

## 명령 (원본에는 쓰지 않는다 — 원본은 `:ro` 로 묶는다)
```bash
export LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
SIF=/opt/apptainers/SmartTwinPostprocessor.sif           # unified_analyzer ec35274 (10-18)
SRC=/data/koopark/Test_005_Fibonacci_100
TD=/data/koopark/scratch_fib10_hotspot                   # 새 폴더(있으면 멈춘다)
BIND="/data:/data,$SRC:$SRC:ro"
RUNS="Run_20260602_093108_fd1418 Run_20260602_114721_c2559d Run_20260602_141952_eab3bf Run_20260602_164245_22ea56 Run_20260602_191154_ef443e Run_20260602_212320_0d586f Run_20260602_235724_e4ba08 Run_20260603_021031_2b326a Run_20260603_043355_fc75eb Run_20260603_064944_bb6571"
mkdir "$TD" "$TD/output" "$TD/analysis_results"
cp -a "$SRC/runner_config.json" "$SRC/scenario.json" "$SRC"/MinimumModel*.k "$TD/"
for R in $RUNS; do cp -as "$SRC/output/$R" "$TD/output/"; done          # 파일은 전부 심링크(binout0000%001 포함)
for R in $RUNS; do                                                       # 하나씩(메모리)
  RUN_DIR=$TD/output/$R/Output; REPORT_DIR=$RUN_DIR/report; mkdir -p "$REPORT_DIR"
  /usr/bin/time -v apptainer exec --env PYTHONNOUSERSITE=1 --bind "$BIND" "$SIF" python3 -m koo_deep_report "$RUN_DIR" -o "$REPORT_DIR" \
    --ua-threads 8 --hotspot-clusters --hotspot-criterion max_shear,x_tension --hotspot-time-aggregate both --no-render \
    > "$TD/deep_$R.log" 2>&1
  ln -sfn "$REPORT_DIR" "$TD/analysis_results/$R"
done
apptainer exec --env PYTHONNOUSERSITE=1 --bind "$BIND" "$SIF" python3 -m koo_sphere_report --test-dir "$TD" \
  --format html json -o "$TD/sphere_report.html" --json "$TD/sphere_report.json" --yield-stress 350
```
10각도는 DOE P0001 · P0012 · … · P0100(고르게 · 양극 포함). 기준 `max_shear,x_tension` + `both` 는 고정본과 같다.

## 함정 — 조용히 옛 판이 되거나 비는 것
1. 핫스팟은 모든 층에서 기본이 꺼짐이다 — `--hotspot-clusters` 를 빼면 per-run `hotspot` 이 없다. YAML 의 `hotspot_clusters: true`(스칼라)는 조용히 무시된다(블록이어야 한다).
2. `--no-render` 를 빼면 LSPrePost 그림 잡이 붙는다. 파이프라인의 단면 플래그(`--section-view …`)는 쓰지 않는다 — 1214 잡이 그것으로 시간 초과됐다.
3. 이미지 밖(시스템 python)에서 돌리면 lasso 가 없어 `contact_profile` · `contact_trust` · `energy_flows` 가 **키는 있는데 비어** 나온다 — 내용을 본다.
4. 이미지 안에서도 `~/.local` 의 numpy 가 먼저 잡힌다 — `--env PYTHONNOUSERSITE=1`.
5. `--json` 은 `--format json` 없이는 아무것도 안 한다(파이프라인 `sphere_report.sh` 에 그 결함이 있다).
6. `total_runs` 는 `TD/output/Run_*` 를 센다 — 10개만 둔다. `analysis_result.json` 이 없는 런은 말없이 빠진다.
7. 캐시(`.sphere_flow_cache` · `device_preview.json`)를 test dir 에 쓴다 — 원본을 `--test-dir` 로 주지 않는다.
8. `hotspot_cap_note`(2만 군집 초과) · `energy_flows_note`(60각도 초과) · `hotspot_mesh`(이 배치에선 안 생김)는 없는 것이 맞다.

## 확인 — 기대값
| 무엇 | 기대 |
|---|---|
| 런마다 `analysis_result.json` | `metadata.tool_commit == "ec35274"` · `hotspot_clusters` 비지 않음 · 기준 {max_shear, x_tension} |
| results · 성공/실패 | 10 · 10/0 |
| `tool_builds` | `{"ec35274": 10}` |
| `hotspot` 이 있는 런 | 10/10(기대) |
| `contact_profile` | 쌍 > 0 · `pf` 폭 10 |
| `contact_trust` | n_runs 10 · n_available 10 |
| `energy_flows` | 10 |
| 최상위 키 | 고정본 23개에서 `hotspot_cap_note` 빼고 |

리포트 HTML 안의 자료는 플랫폼 파서 `app.reports.parser.extract_embedded_data` 로 꺼낼 수 있다. 다 되면 플랫폼에 반입해 핫스팟 포락 · 접촉 전개 히트맵(각도 10) ·
각도별 하중경로를 보고, 새 고정본(폴더를 하나 더)으로 남긴다.
