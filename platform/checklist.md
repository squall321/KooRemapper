# Checklist — Phase 10 리뷰 후속 조치

## 백엔드 (수정)
- [x] services.py — 더미 해시 상수시간 인증 (타이밍 사이드채널 #1)
- [x] schemas.py — 공통 이메일/비밀번호 검증 헬퍼 + SignupRequest 적용 (#5)
- [x] admin/routes.py — UserCreate/PasswordReset 검증 적용 + 마지막 관리자 가드 (#2, #5)
- [x] auth/routes.py — change_password 죽은 is_active 가드 제거 (#4)
- [x] tests — 회원가입 공백 비밀번호/잘못된 이메일 422 테스트 추가

## 프론트엔드 (수정)
- [x] Pagination.tsx — `count===0` 무조건 null (#8)
- [x] Pagination.tsx — 꽉 찬 마지막 페이지 한계 주석 (#7, 보류 명시)
- [x] SystemPage.tsx — CopyBtn clearTimeout (#9)
- [x] AccountPage.tsx — nonce 기반 자동소멸 (#6)
- [x] ComparePanel.tsx — 포맷값 기준 동등 판정 (#10)

## 검증
- [x] pytest 전체 통과 (36 passed)
- [x] tsc + vite 빌드 통과
- [x] api 재시작 + 라이브 회원가입 검증 확인 (blank/bad-email 422, valid 201, ghost 401)
- [x] 커밋(백엔드/프론트 분리) + 푸시
- [ ] nginx read-only-fs 수정 + nginx.sif 재빌드 (재부팅으로 드러난 별개 이슈)

## 표면화 (구현 보류, 사용자 결정)
- [ ] JWT 재설정 무효화 (#3) — token_version 마이그레이션 필요
