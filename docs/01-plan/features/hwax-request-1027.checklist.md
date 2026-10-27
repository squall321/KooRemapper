# HWAX 요청 체크리스트 (2026-10-27)

## KR-03 — 주응력 솔버 (C++)
- [ ] `StressTensor::principalStresses` 를 변형률 매개화로(한 실근 가지 제거 · clamp)
- [ ] `tests/test_StressTensor.cpp` 추가 · `test_main.cpp` 에 include
- [ ] 단위 시험 빌드·통과(host 테스트 타깃) · 옛 솔버 FAIL 확인

## KR-01 — 과제코드 매칭 (ontology)
- [ ] `resolve_task` 가 `properties.task_code` 도 exact 로 본다(과제명·코드·별칭)
- [ ] `task_candidates` 가 task_code 를 후보·근거로
- [ ] 검색/resolve 가 `matched_by` 를 돌려준다
- [ ] 화면·설명·문서의 'key=과제코드' 문구 수정

## KR-02 — '/' 든 key 경로
- [ ] API `{task_key:path}` (또는 질의 인자)
- [ ] MCP 클라이언트 `quote(key, safe='')`

## KR-17 — sync 상태 읽기 열기
- [ ] `ontology_sync_state` 읽기를 일반 사용자에게

## KR-04 — 감시 배포 표지
- [ ] check_once 가 deploy.lock.d PID · `/tmp/hwax-update-all.*.lock` 보면 「배포 중 — 건너뜀」

## KR-05 — 크론 세션 버스
- [ ] `_common.sh` 가 XDG_RUNTIME_DIR · DBUS_SESSION_BUS_ADDRESS 자동 채움(비었고 소켓 있으면)

## KR-09 — crontab 실패 안전
- [ ] `install-autostart.sh` 가 'no crontab for' 만 빈 목록 · 그 밖 실패엔 exit 1

## 마무리
- [ ] 백엔드 pytest · C++ 단위 · 관련 스크립트 시험
- [ ] 의미 단위 커밋·푸시
- [ ] compat 빌드 → Drive(KR-03) · dev 재기동 · 완료 보고 · 저쪽 회신(필요 시)
