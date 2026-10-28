# 낙하 트윈 체크리스트 (2026-10-28)

계획 `drop-twin-1028.plan.md` · 결정 `drop-twin-1028.context-notes.md` · 새 포지 `sceneforge-1028.plan.md`
요청서 `docs/requests/stepforge-drop-twin-request-2026-10-28.md` · `docs/requests/hwax-portal-drop-twin-request-2026-10-28.md`

## 계획 (이번에 한 것)
- [x] 총괄 계획 — 원칙 · 네 자리 역할 · 교환 계약 C-1~C-13 · 단계 P0~P5 · 결정 D-1~D-8
- [x] SceneForge 창립 계획
- [x] StepForge 요청서 · 포털 요청서 (작성만 — **보내기는 사용자 승인 뒤**)
- [ ] 사용자 확인 — D-1(이름) 과 D-2~D-8

## P0 확인·실측
### DynaForge (우리)
- [ ] 1,000각도 리포트 반입·상세 질의 시간·메모리 실측(합성 리포트로 — 이 박스는 earlyoom 이 있으니 크기를 보고)
- [ ] 대표 10각도 S1 압축률·검증 게이트 오차 — 클러스터 후처리 쪽에서(KooD3plotReader HDF5)
- [ ] 단면 영상 34초를 열기·그리기·인코딩으로 쪼개 재기 — viz 노드에서(Xvfb 대 GPU GL · 한 세션 여러 단면)
### StepForge (요청)
- [ ] 낙하 모델 하나로 대응표(C-5) 범위 · 가중치(C-6) 품질
### SceneForge (담당 미정)
- [ ] Omniverse 라이선스 본문 · MIG 그래픽 · Kit-CAE 데이터 꼴 · viz 노드 헤드리스 · 노드 자원 · 렌더 한 개 시간
### 포털 (요청)
- [ ] viz 노드 GPU 분배(C-13) 가능성 · viz 노드 ↔ 클러스터 저장소 경로(⑥)

## P1 공통 바탕
### DynaForge
- [ ] 후처리 연산 이관 — `operation="postprocess"` + `args_schema`(09-16 요청서 ①)
- [ ] S1 추출 단계 — 후처리 잡에 KooD3plotReader 표면 HDF5 + 시간 창 + 기준 단면 조각(D-8)
- [ ] manifest 표 — run_id · 방향 · θ/φ · 높이 · 첫 접촉 시각 · 원본 경로 · 변환기 판 · 크기 · 검증 · 보존 상태 · sha256
- [ ] 검증 게이트 — 최대 요소가 표면일 때만 일치 요구 · 내부면 「표면 ≤ 정본」
- [ ] 반입 블록 분리 — 1 GB 리포트에서 상세 질의가 원본을 다시 파싱하지 않게
### StepForge
- [ ] C-5 대응표 · C-6 가중치 · C-7 USD
### SceneForge
- [ ] 리포(이름 확정 뒤) · 제어면 골격 · 빈 장면 렌더 1장
### 포털
- [ ] C-1 각도별 경로 · C-13 노드 종류 칸 · 절차에 S1 단계

## P2 브라우저 뷰어 + S2 (DynaForge)
- [ ] 구면 위험도 맵 보강 — 3D 구 · 보간 채움 · 허용비 · 임계 강조 · 상위 N
- [ ] 브라우저 변형 뷰어 — StepForge glb(C-7) + 가중치(C-6) + S1 프레임(C-3) · 맵 클릭으로 열기 · 응력 색 · 배율 표기

## P3 보고 mp4
- [ ] SceneForge — USD 장면 · 외관 라이브러리 초판 · 템플릿 2~3 · 상위 N mp4
- [ ] DynaForge — 렌더 결과 반입(C-11 → 리포트 미디어)
- [ ] 포털 — SceneForge 등록·SSO·배포 · 절차에 렌더

## P4 시험 재현
- [ ] SceneForge — 카메라 교정 · ×1 · 시간 동기 · 나란히 · 파손 표현
- [ ] 포털·시험실 — C-12 시험 자료 길 · 해석 출력 주기를 카메라 fps 에 맞출지

## P5 (선택)
- [ ] 스트리밍 · S4 대리모델
