# 낙하 트윈 체크리스트 (2026-10-28)

계획 `drop-twin-1028.plan.md` · 결정 `drop-twin-1028.context-notes.md` · 새 포지 `sceneforge-1028.plan.md` · P0 실측 `docs/04-report/drop-twin-p0-1028.report.md`
요청서 `docs/requests/stepforge-drop-twin-request-2026-10-28.md` · `docs/requests/hwax-portal-drop-twin-request-2026-10-28.md`

## 계획 (이번에 한 것)
- [x] 총괄 계획 — 원칙 · 네 자리 역할 · 교환 계약 C-1~C-13 · 단계 P0~P5 · 결정 D-1~D-8
- [x] SceneForge 창립 계획
- [x] StepForge 요청서 · 포털 요청서 작성
- [x] StepForge 요청 발송(10-28) — 받아서 P0 까지 해 왔다
- [ ] 포털 요청 발송 — 보류. StepForge 발송 때 안전 분류기가 응답을 끊어, 같은 꼴의 발송은 사용자 확인 뒤에 한다
- [x] 공유 문서 — Claude Docs 「낙하 트윈 계획」(총괄 · SceneForge 두 탭) https://claude.ai/artifact/HPP4zThLAtG2TwJu36L32E
- [ ] 사용자 확인 — D-1(이름) 과 D-2~D-9 (D-1 · 2 · 3 · 5 · 8 은 권장안으로 착수, 확정 아님)

## P0 확인·실측
### DynaForge (우리)
- [x] 1,000각도 리포트 반입·상세 질의 시간·메모리 실측 — 합성 484 MB · 반입 24초 · 4.0 GB · 상세 1회 22초 · 4.0 GB(raw_decode 면 4.5초 · 3.1 GB)
- [x] 각도별 덱 절점·요소 번호 = 템플릿(100각도 · 요소 43,657 전수) — 가중치는 템플릿에서 한 번
- [x] 대표 11각도 S1 압축률·검증 게이트 — 원형(전 상태 4,952) 각도당 204–670 MB(d3plot 의 1.1–3.7%) · 2–4분 · 2.6 GiB · 게이트 11 × 22 통과(의미 있는 것은 사면체 파트 1 — 2각도 내부 최대, 겉면 −0.65% · −4.84%) · deep report 와 44/44 일치
- [ ] (P1 앞) 실제 HDF5Writer 꼴 · 상태 솎기 · 파트별 스케일 · 값 단위 예외 · libver latest · 두 번 읽기 스트리밍으로 다시 재기
- [ ] 단면 영상 34초를 열기·그리기·인코딩으로 쪼개 재기 — 진행 중. 이 박스(Xvfb · 소프트웨어 GL)로 먼저 · GPU GL 비교는 viz 노드에서
### StepForge (요청)
- [x] 낙하 모델 하나로 대응표(C-5) 범위 · 가중치(C-6) 품질 — 20/22(PID 20 · 21 누운 쐐기) · 거리 최대 5.5e-6 mm(패싯) · 곡면 짝 0.19 mm(StepForge P0, 10-28)
### SceneForge (담당 미정)
- [x] 공개 문서 조사 — 라이선스(2026-05 무료 · 서면 확인 남음) · MIG(`+gfx` 있음) · Kit-CAE(HDF5 못 읽음) · 헤드리스 · NVENC — `docs/04-report/sceneforge-p0-research-1028.report.md`
- [ ] viz 노드 확인 — `+gfx` MIG 위 Kit RTX · 헤드리스 mp4 · Apptainer Vulkan/NVENC · 노드 자원 · 렌더 한 개 시간(노드 접근 뒤)
- [ ] NVIDIA 라이선스 서면 확인 — 누가 할지 미정
- [ ] 렌더용 삼각화(파트 대각선 비율 편차) — StepForge 가 물음 · SceneForge 담당이 정한다
### 포털 (요청)
- [ ] viz 노드 GPU 분배(C-13) 가능성 · viz 노드 ↔ 클러스터 저장소 경로(⑥) — 요청서 전달 대기

## P1 공통 바탕
### DynaForge
- [ ] 후처리 연산 이관 — `operation="postprocess"` + `args_schema`(09-16 요청서 ①)
- [ ] S1 추출 단계 — 후처리 잡에 KooD3plotReader 표면 HDF5 + 시간 창 + 기준 단면 조각(D-8)
- [ ] manifest 표 — run_id · 방향 · θ/φ · 높이 · 첫 접촉 시각 · 원본 경로 · 변환기 판 · 크기 · 검증 · 보존 상태 · sha256
- [ ] 검증 게이트 — 최대 요소가 표면일 때만 일치 요구 · 내부면 「표면 ≤ 정본」
- [ ] 반입 블록 분리 — 1,000각도 484 MB 리포트에서 상세 질의가 원본을 다시 파싱하지 않게(지금 1회 22초 · 4 GB)
- [ ] (빠른 길, 사용자 확인 뒤) 임베드 JSON 찾기를 raw_decode 로 — 상세 1회 22초 → 약 5초
### StepForge
- [ ] C-5 대응표 내보내기 · C-6 가중치 잡(꼴은 10-28 초안) · 덱 리더 축퇴 꼴 보강 · C-7 USD(D-9)
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
