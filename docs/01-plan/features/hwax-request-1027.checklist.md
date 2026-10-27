# HWAX 요청 체크리스트 (2026-10-27)

## KR-03 — 주응력 솔버 (C++)
- [x] principalStresses 변형률 매개화(한 실근 가지 제거)
- [x] test_StressTensor.cpp(5항) + test_main include
- [x] 단위 145/0 · prestress probe ALL PASS · 옛 솔버는 재현으로 FAIL 확인

## KR-01 — 과제코드 매칭 (ontology)
- [x] resolve_task task_code exact 경로
- [x] task_candidates task_code 후보
- [x] list_tasks matched_by · resolved_how
- [x] why 문구·MCP·TOOLS 수정

## KR-02 — '/' 든 key 경로
- [x] tasks/{task_key:path} compare·revisions
- [x] MCP quote(safe='')

## KR-17 — sync 상태 읽기 열기
- [x] GET /ontology/sync → router(로그인), 쓰기는 admin

## KR-04 — 감시 배포 표지
- [x] check_once 배포 표지 건너뜀 — pid 첫 칸 · flock 은 /proc/locks 로 엿봄(피어 지적 반영)

## KR-05 — 크론 세션 버스
- [x] _common.sh 세션 버스 자동 채움

## KR-09 — crontab 실패 안전
- [x] install-autostart crontab 실패 안전

## 마무리
- [x] 백엔드 662 · C++ 145 · 스크립트/ASGI 시험
- [x] 커밋 7(b8eb309·ca47363·c2a124b·f1ab307 등) 푸시
- [x] compat 빌드(GLIBC_2.35) · dev 재기동·스모크(80·62/62) · 피어 회신 · [x] prod Drive 게시 완료(dist-20261027-220420Z) — prod 는 dist-from-drive(ops)
