# 낙하 트윈 체크리스트 (2026-10-28)

계획 `drop-twin-1028.plan.md` · 결정 `drop-twin-1028.context-notes.md` · 새 포지 `/home/koopark/claude/SceneForge/docs/PLAN.md` · P0 실측 `docs/04-report/drop-twin-p0-1028.report.md`
요청서 `docs/requests/stepforge-drop-twin-request-2026-10-28.md` · `docs/requests/hwax-portal-drop-twin-request-2026-10-28.md`

## 계획 (이번에 한 것)
- [x] 총괄 계획 — 원칙 · 네 자리 역할 · 교환 계약 C-1~C-13 · 단계 P0~P5 · 결정 D-1~D-8
- [x] SceneForge 창립 계획
- [x] StepForge 요청서 · 포털 요청서 작성
- [x] StepForge 요청 발송(10-28) — 받아서 P0 까지 해 왔다
- [x] 포털 요청 발송(10-28 저녁 — 사용자 확인 뒤) · §7 P0 덧붙임 · ⑦ viz 노드 tbot 접근 → 포털 답(10-28 밤)으로 viz 노드는 stcx 노드(사용자 확인), ⑦ 은 필요 없다
- [x] SmartTwinMCP 에 C-1(각도별 run 폴더 · d3plot 경로) 요청 보냄(10-28 밤 — 포털이 SmartTwinMCP 몫이라 함, 사용자 승인)
- [x] 공유 문서 — Claude Docs 「낙하 트윈 계획」(총괄 · SceneForge 두 탭) https://claude.ai/artifact/HPP4zThLAtG2TwJu36L32E
- [x] 사용자 확인(10-28 저녁) — D-1 SceneForge · D-4 사용자 본인 · D-6 전용 Claude 세션 + 검토 · D-7 CAD 색 + 라이브러리 · D-9 SceneForge 가 USD (D-2 · 3 · 5 · 8 은 권장안으로 착수, 확정 아님)

## P0 확인·실측
### DynaForge (우리)
- [x] 1,000각도 리포트 반입·상세 질의 시간·메모리 실측 — 합성 484 MB · 반입 24초 · 4.0 GB · 상세 1회 22초 · 4.0 GB(raw_decode 면 4.5초 · 3.1 GB)
- [x] 각도별 덱 절점·요소 번호 = 템플릿(100각도 · 요소 43,657 전수) — 가중치는 템플릿에서 한 번
- [x] 대표 11각도 S1 압축률·검증 게이트 — 원형(전 상태 4,952) 각도당 204–670 MB(d3plot 의 1.1–3.7%) · 2–4분 · 2.6 GiB · 게이트 11 × 22 통과(의미 있는 것은 사면체 파트 1 — 2각도 내부 최대, 겉면 −0.65% · −4.84%) · deep report 와 44/44 일치
- [ ] (P1 앞) 실제 HDF5Writer 꼴 · 상태 솎기 · 파트별 스케일 · 값 단위 예외 · libver latest · 두 번 읽기 스트리밍으로 다시 재기
- [x] 단면 영상 시간 쪼개기(이 박스 · CPU 경로) — 4,952 상태 덱은 영상 하나 NVMe 약 100초 · HDD 157–312초(34초는 재현 안 됨) · 프레임당 20 ms 중 래스터 절반 · 한 세션 여러 단면은 7–10% · 운영 기본은 각도마다 세션 144개
- [x] 결함 보고(KooD3plotReader) 보냄(10-28 저녁) — `docs/requests/kood3plotreader-section-video-defects-2026-10-28.md`(K-1~K-4 · P-1~P-4)
- [x] KooD3plotReader 회신(10-28 밤) — K-1 원인 확정(LS-PrePost 메모리 예산) · K-1~K-4 · P-1 고침(로컬 커밋, 배포 대기)
- [ ] 고친 운영 이미지가 배포되면(VERSION 통지) 단면 영상을 그 이미지로 다시 재 0 프레임이 사라졌는지 확인
- [ ] (stcx viz 노드) GPU GL 로 movie 단계만 다시 재기 — 고쳐질 몫은 프레임당 약 10 ms(최대 2배)
### StepForge (요청)
- [x] 낙하 모델 하나로 대응표(C-5) 범위 · 가중치(C-6) 품질 — 20/22(PID 20 · 21 누운 쐐기) · 거리 최대 5.5e-6 mm(패싯) · 곡면 짝 0.19 mm(StepForge P0, 10-28)
### SceneForge (담당 미정)
- [x] 공개 문서 조사 — 라이선스(2026-05 무료 · 서면 확인 남음) · MIG(`+gfx` 있음) · Kit-CAE(HDF5 못 읽음) · 헤드리스 · NVENC — `docs/04-report/sceneforge-p0-research-1028.report.md`
- [ ] viz 노드 확인 — `+gfx` MIG 위 Kit RTX · 헤드리스 mp4 · Apptainer Vulkan/NVENC · 노드 자원 · 렌더 한 개 시간. 접근은 `ssh stcx` + `srun`(viz 노드 = stcx 노드, 10-28 사용자 확인). GPU 는 챗 LLM 과 공유 — 읽기만 먼저, MIG · 렌더 시험은 시간을 잡고
- [ ] NVIDIA 라이선스 서면 확인 — SceneForge 몫(사용자 결정 10-28)
- [ ] 렌더용 삼각화(파트 대각선 비율 편차) — StepForge 가 물음 · SceneForge 담당이 정한다
### 포털 (요청)
- [x] 포털 답(10-28 밤) — viz 노드는 stcx 노드 · C-13 은 실행기 칸이 아니라 stcx Slurm 제출 · ⑥ 은 같은 클러스터 마운트일 가능성 · ⑦ 불필요 · ① 은 SmartTwinMCP 몫 · ③ 등록 순서는 P3 · ④ 절차 YAML 은 P1 · ⑤ 시험 자료는 P4(사용자)
- [ ] ⑥ 마운트 확인 — cae00 에서 사람이 `ssh stcx srun -p <viz 파티션> -w <viz 노드> ls <output_dir>`(읽기만)

## P1 공통 바탕
### DynaForge
- [ ] 후처리 연산 이관 — `operation="postprocess"` + `args_schema`(09-16 요청서 ①) · unified_analyzer 의 rc 3(분석 성공 · 렌더 실패)은 실패가 아니라 경고로 다룬다(10-28 KooD3plotReader K-4)
  - 막힌 자리(10-28 밤 확인) — `platform/docs/REQUEST-postprocess-operation.md` §7-1 은 클러스터 선행이 서야 착수: KooSlurm `docs/REQUEST-result-return.md` A(파일 REST 인증 — `/files/download` 가 아직 `@optional_jwt`) · B(귀환 매니페스트 — 코드에 없음) · C · D, pyKooCAE `docs/REQUEST-drop-impact-result-return.md` A(부분충격 리포트) · C — ★B(초속 이중 합산)는 9-17 `5baae8d` 에서 이미 고쳐져 SIF v97+ 에 있다(나는 커밋 메시지 키워드로만 찾아 놓쳤다 — pyKooCAE 회신으로 바로잡음). 두 세션에 진행 요청함(사용자 지시) — pyKooCAE 는 A + E(output_dir) → C → E(deep 건너뛰기) → D 순으로 착수
- [ ] S1 manifest · 검증 게이트 — KooD3plotReader S1 추출기 꼴(요청 §6-1)이 정해진 뒤
- [ ] S1 추출 단계 — 후처리 잡에 KooD3plotReader 표면 HDF5 + 시간 창 + 기준 단면 조각(D-8)
- [ ] manifest 표 — run_id · 방향 · θ/φ · 높이 · 첫 접촉 시각 · 원본 경로 · 변환기 판 · 크기 · 검증 · 보존 상태 · sha256
- [ ] 검증 게이트 — 최대 요소가 표면일 때만 일치 요구 · 내부면 「표면 ≤ 정본」
- [x] 반입 블록 분리 — sphere 곁파일(slim + 각도별 시계열). 1,000각도 상세 질의 1회 0.34초 · 174 MB(처음 22.4초 · 4.0 GB). 계획 · 결과 `report-block-split-1028.plan.md`
- [x] (빠른 길) 임베드 JSON 을 raw_decode 로 — 상세 1회 22.4초 → 6.7초 · 4.0 → 3.1 GB(`288afb7`, dev 반영 · 리포트 스모크 35/35 · 백엔드 672 통과)
### StepForge
- [ ] C-5 대응표 내보내기 · C-6 가중치 잡(꼴은 10-28 초안) · 덱 리더 축퇴 꼴 보강 · 파트 표에 재질 · 밀도 · 색(C-8) — USD 는 SceneForge(D-9)
  - [x] 첫 산출(10-28 밤, 개발판) `/data/koopark/drop_twin_p1/stepforge_fe_cad_a32a9a574143/` — 대응 22/22 · 가중치 22파트(행 1,232 · nnz 3,696) · 겉면 22/22 S1 과 같음. 받는 쪽 검사 통과(sha · 오프셋 8 배수 · Σw=1 · col ⊂ S1 node_ids). 운영 반영 뒤 경로 · 열쇠가 바뀐다
### SceneForge
- [x] 리포 — `/home/koopark/claude/SceneForge`(10-28, 로컬 첫 커밋 ebbf77f). GitHub 비공개 저장소는 이 박스의 gh(snap)가 서비스 cgroup 에서 안 떠 대기
- [ ] 제어면 골격 · glb → USD · 빈 장면 렌더 1장
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
