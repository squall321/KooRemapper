# 체크리스트 — 결정 목록 권장안 (10-23 저녁)

## 3B 카탈로그
- [x] `contact` 키 112개 Vol_I 대조표 — 틀린 것 54 · 맞는 것 58(하위 에이전트 대조 + Card 1–G · THERMAL · TIEBREAK 원문 · PDF 1210쪽 직접 확인)
- [x] 틀린 설명 고침 — contact 50 새로 · 3 덧붙임 · type 끝 문장 · op 설명 CHLM · stabilize 2 · stcx 3 → `841065c`
- [x] 설명으로 못 고치는 코드 결함 11개 기록(사용자 결정 대기) → `74aa501`
- [x] 도움말(ops_help · HelpCatalogData)에 같은 오류 없음 — 재빌드 없음
- [x] 카탈로그 시험 15 · 카탈로그↔바이너리 대조 ALL PASS · 재기동 뒤 MCP describe 에 새 문장(Birth time · FTOSA · Known issue 5)

## 4 CPU
- [x] map 확장성 측정표(1·2·4·8·16·32 스레드) — 모두 6.1~6.4 초 · CPU 110% · 직렬 전처리(gdb 표본 6) · prestress 0.97→0.74 초 · 결과 동일
- [x] 워커 — 실행기가 없을 때 잡 환경에 `OMP_NUM_THREADS`(이미 있으면 존중) · 시험 5 → `6c20e57`
- [x] 살아 있는 잡에서 값 확인 — MCP → API → 워커 database 잡 `omp_num_threads: 8` · `host.job_node: null`

## 8 HWAX
- [x] `host.job_node` ← `.job_<id>.node`(길이 · 글자 검사) · 시험 3 → `ae8e94f`
- [x] `.nfs*` 출력 제외 · 시험 1 → `ae8e94f`
- [x] 답신 6장 덧붙임(③ A · `.nfs*` · ⚠ V1 예외 · 측정) · ENVIRONMENT · 실행기 계획 · 체크리스트

## 6B 요청서 초안
- [x] SmartTwinMCP 결과 내려받기 요청서 초안(보내지 않는다) → `47a10e6`

## 5B 다각도 sphere
- [x] 재생성 방법 확인(분석기 · 핫스팟 설정 · 시간) — 하위 에이전트 조리법(koo_deep_report `--hotspot-clusters` · `--no-render` · 10각도 test dir · koo_sphere_report)
- [ ] 10각도 새 판 리포트 → 플랫폼 반입 · 잰다 — **보류**: 런마다 4,952 상태 · 약 35 GB 가 드는데 지금 쓸 수 있는 메모리 12 GB · 스왑 39/39 GB(사용자 결정)
- [ ] (괜찮으면) 100각도

## 관문 · 배포
- [x] 백엔드 pytest 628 · 스모크 넷(op 63 · 도구 73 · 리포트 35/35 · 그림 20/20 · 덱 op 21/21)
- [x] API · MCP 재기동(살아 있는 잡 0 을 본 **결과에** 걸었다) · health ok 252bd444 일치
- [ ] SIF 굽기 · `/opt/apptainers` · sha
- [ ] 커밋 · 푸시 · 메모리 · 보고
