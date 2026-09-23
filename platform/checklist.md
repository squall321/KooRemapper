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
- [x] nginx read-only-fs 수정 + nginx.sif 재빌드 (/tmp 경로 + gzip_proxied/text/javascript)

## 표면화 (구현 보류, 사용자 결정)
- [ ] JWT 재설정 무효화 (#3) — token_version 마이그레이션 필요

## 2026-09-23 인클루드·설정 파일 저장 정합성 (include-integrity)

### ③ 하위 경로 보존 (정합성의 본체)
- [x] `storage.safe_relpath()` 추가 — 상대 경로만, `..`·절대·드라이브 제거, 구성요소별 문자 규칙
      → 검증: 트래버설 단위 시험(`..`, `/etc/passwd`, `C:\`, 빈 구성요소, 깊이·길이 상한)
- [x] 업로드가 `safe_relpath` 를 쓰고, 쓰기 직전 목적지가 세션 디렉터리 안인지 재확인
      → 검증: `sub/part.k` 업로드 후 디스크·DB 경로가 `sub/part.k` 인지
- [x] 이름 충돌 de-dup 이 하위 폴더 안에서 동작
      → 검증: 같은 `sub/part.k` 두 번 올리면 `sub/part_1.k`
- [x] 프론트 업로드가 `webkitRelativePath` 를 실어 보내고 폴더 업로드 버튼 추가 + 인클루드 경고 배너
      → 검증: tsc 통과 + 폴더 올려 하위 경로가 보존되는지

### ② 인클루드 정합성 검사
- [x] `meta.includes` 대 세션 파일 대조 함수 + 업로드 응답 경고
      → 검증: 하위 폴더 인클루드 덱만 올리면 missing 목록이 응답에 나오는지
- [x] 잡 생성 시 422 + 명시적 우회 플래그
      → 검증: 빠뜨린 채 실행하면 422, 플래그를 주면 통과

### ① 설정 파일 등록
- [x] `build_command` 산출 파일을 `kind="generated"` 로 명시 등록(origin_job_id 포함)
      → 검증: 잡 실행 후 파일 목록에 `config.yaml` 이 generated 로 뜨고 다운로드되는지
- [x] 산출물 스냅샷에 중복 등록되지 않는지
      → 검증: 같은 파일이 output 으로 다시 안 잡히는지

### 마무리
- [x] 전체 시험 통과 + 무력화 확인
- [x] MCP `upload_kfile` 문서에 하위 경로 사용법 반영 + help/카탈로그 정합
- [x] 커밋(백엔드/프론트 분리) + 푸시

### 실제 결과 (2026-09-23)
- 백엔드 시험 **222 passed, 3 skipped** / C++ 회귀 **37/37** / MCP 문서 패리티 **ALL PASS**
- 무력화 확인 4종: 업로드 평탄화 복귀 · 트래버설 방어 둘 다 제거 · 실행 관문 제거 · 설정 중복 등록
- **dev 라이브 확인(2026-09-23)** — 업로드 경고 문구, `sub/part.k` 경로 보존, 인클루드 해소 후 ok=true,
  실제 indent 잡 성공 후 파일 목록:
  `input master.k / input sub/part.k / input block.k / generated config.yaml / output indent_live.{k,dynain}`
- ⚠ 트래버설은 방어가 **두 겹**이다(`..` 구성요소 버리기 + `lstrip(".")`) — 하나만 빼면 시험이
  안 잡힌다. 둘 다 빼야 빨개진다는 것을 확인했다(시험이 헛돌지 않음을 증명).
- ⚠ `test_a_second_supervisor_does_nothing` 이 간헐적으로 빨개지던 것을 함께 고쳤다 —
  진짜 supervisor.sh 를 holder 로 띄워 잠금을 두고 경쟁했다. 가만있는 더미로 바꿨다.
