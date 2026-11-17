# Checklist — DynaForge 개발 요청서 v1.0(11-17) 1차

설계 `df-request-1117.plan.md` · 맥락 `df-request-1117.context-notes.md` · 요청서는 사용자가 붙여 넣은 요청서(리포에 두지 않는다 — 미출시 과제 이름 · PC 경로가 들어 있다, 포털이 전한 부탁 11-17)

## A. 확인
- [x] A-1 SP 판 점검(리포 CLAUDE.md) — 13e6b02 → 068fd32 고정 올림 `accc540` · 시험 64 통과 · StepForge 에 알림
- [x] A-2 요청서 주장 대조(DF-01 · 06 · 08 · 10 · 14 · 15) — 계획서 표
- [x] A-3 사용자 결정 넷(범위 · DF-14 · D1 · 이름)

## B. DF-14 감지 · 경고 · 쓰기 거절
- [x] B-1 이름 확인(modelmeta 새 칸 둘) — `element_id_collisions` · `parts_missing`
- [x] B-2 리더 — 요소 추가 넷에서 덮인 정의를 PID 별로 센다 · 곁표 지움
- [x] B-3 쓰기 관문 — writeFile · writeFileWithSource · 새로 짓는 메시에 표 옮김
- [x] B-4 modelmeta 칸 · 콘솔 경고
- [x] B-5 회귀 시험 — 겹친 덱으로 modelmeta 칸 · 덱 쓰는 op 마다 거절 · 겹침 없는 덱은 그대로
- [x] B-6 플랫폼 — kfile_modelmeta 통과 · 콘솔 파일 패널 경고 · 백엔드 시험
- [ ] B-7 빌드 · 회귀 전부 · compat 빌드 · 플랫폼 bin

## C. DF-01 의 틈
- [x] C-1 `.env.example` 에 `KOORM_PUBLIC_BASE`
- [x] C-2 `upload_instructions` 에 401 세 갈래

- [x] C-3 D4 `capabilities.intake` · D5 `environment` · inspect `sha256`(사용자 결정 11-17 — 셋 다)

## D. 올리기
- [ ] D-1 커밋 · main · 살아 있는 잡 확인 뒤 dev 재기동 · 스모크 · pytest
- [ ] D-2 Drive 게시 · cae00 점검 문서 · 포털 알림
- [ ] D-3 요청 쪽 답신(사용자가 전한다)

## E. 2차 설계서
- [ ] E-1 나머지 13건 설계서와 이름표 — 확인받기
