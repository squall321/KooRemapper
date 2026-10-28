# 낙하 트윈 — 세 포지와 포털의 분담·교환 계획 (2026-10-28)

**출발점** 제안서 「전각도 낙하 해석 결과 활용 고도화」(2026-10-28) — S1 경량화 · S2 구면 위험도 맵 · S3 온디맨드 렌더링 · S4 대리모델.

**사용자 결정(10-28)**
- 브라우저 3D 변형 뷰어와 Omniverse 를 **둘 다** 한다. Omniverse 는 디지털 트윈 보고와 **실물 시험 재현**(시험 사진·고속 카메라와 같은 시점으로 그려 나란히 견주기)에 쓴다.
- DynaForge 와 StepForge 는 각자 강화하고, Omniverse 는 **새 포지**로 지금 세운다. 이름은 이 계획이 정한다(§2).
- 셋은 따로 개발하고 필요한 정보만 주고받는다. 포털은 stcx 정보 때문에 같이 맞물린다.

받는 쪽 문서 —
- 새 포지 창립 계획 `docs/01-plan/features/sceneforge-1028.plan.md`
- StepForge 요청 `docs/requests/stepforge-drop-twin-request-2026-10-28.md`
- 포털 요청 `docs/requests/hwax-portal-drop-twin-request-2026-10-28.md`
- 체크리스트 `drop-twin-1028.checklist.md` · 결정 노트 `drop-twin-1028.context-notes.md`
- P0 실측 `docs/04-report/drop-twin-p0-1028.report.md`
- 공유본 — Claude Docs 「낙하 트윈 계획」 https://claude.ai/artifact/HPP4zThLAtG2TwJu36L32E (원문은 이 파일이다. 바뀌면 이 파일을 먼저 고치고 옮긴다)

## 1. 원칙 다섯
1. **포지마다 정본 하나.** 덱 바이트는 DynaForge, STEP 형상은 StepForge, 합성 장면은 SceneForge 가 갖는다. 같은 사실을 두 곳에서 갖지 않는다.
2. **서로를 부르지 않는다 — 파일과 id 로만 주고받는다.** DynaForge·StepForge 경계 합의(10-15, `docs/requests/stepforge-boundary-reply-2026-10-15.md`)를 셋으로 넓힌다. 각 포지는 MCP·REST 를 열어 둘 뿐 남의 포지를 호출하지 않는다.
3. **잇는 일은 포털 절차가 한다.** 해석 → 후처리 → 추출 → 장면 → 렌더 사슬은 포털 절차(procedures)가 각 포지 도구를 차례로 부르며 id 를 넘긴다. 포털의 R2 낙하 절차를 넓히는 꼴이다.
4. **정본을 다시 계산하지 않는다.** 파트별 최대 응력의 정본은 DynaForge 가 반입한 리포트(원본 기준)다. 경량 추출본·장면·영상은 보기와 학습 전용이다.
5. **기존 잡 무변경.** 지금 후처리 산출(리포트 HTML)과 판정은 그대로 두고 뒤에 붙인다. 붙인 단계가 실패해도 기존 결과는 영향이 없다.

## 2. 새 포지 이름 — SceneForge (권장안으로 착수 · 확정 전)
- 이 포지가 갖는 정본은 **장면**이다. StepForge 형상과 DynaForge 결과에 자기 외관·카메라·조명·템플릿을 얹은 USD 장면(stage)이다.
- 렌더러(Omniverse)는 그 장면을 그리는 도구일 뿐이라, 이름을 렌더러가 아니라 장면에 붙였다. 나중에 렌더러를 바꿔도 이름이 맞는다.
- 기존 포지(DynaForge · StepForge · SignalForge · DocForge)와 같은 꼴이고, 포털 문서와 HEAXHub integrations 에서 충돌이 없다(10-28 확인).
- 대안 — TwinForge(디지털 트윈을 드러내지만 SmartTwin 계열과 헷갈린다) · RenderForge(렌더만 하는 것처럼 좁게 읽힌다).
- ⚠ 리포 생성과 HEAX 등록은 이름이 확정된 뒤에 한다(이름은 적용 전 확인 — 기록된 규칙).

## 3. 네 자리의 역할
| 자리 | 정본(스스로 갖는 것) | 하는 일 | 참조만 하는 것 |
|---|---|---|---|
| **DynaForge 후처리 모듈** | 반입 리포트와 각도별 파트 최대(정본) · S1 추출본 manifest · 검증 게이트 결과 | 후처리 연산 이관(`postprocess`) · S1 추출 단계 · 검증 게이트 · S2 구면 위험도 맵 · 브라우저 변형 뷰어 · 렌더 결과를 리포트 미디어로 묶기 | StepForge 대응표·가중치·CAD 장면 · SceneForge 렌더 결과 · stcx 실행 기록 |
| **StepForge** | STEP 형상 · 재질 이름 · 파트 신원 · FE↔CAD 대응표 · 매핑 가중치 · CAD 장면(glb·USD) | 덱→STEP · 파트 대응 · 가중치 계산 · USD 내보내기 | DynaForge 덱(파일) · S1 표면 메시(파일) |
| **SceneForge (신규)** | USD 장면 합성 · 외관 라이브러리 · 렌더 템플릿 · 시험 카메라 교정 · 렌더 결과물 · GPU 작업 순서 | 보고용 mp4 · 시험 재현 렌더 · (선택) 스트리밍 | StepForge 장면·가중치 · DynaForge S1 추출본·manifest · 시험 영상 |
| **포털(HWAXPortal)** | 절차(사슬) · stcx 연결 · 실행기(노드 분배) · 앱 등록·SSO·배포 | 사슬 잇기 · stcx 실행 기록 넘기기 · viz 노드 GPU 분배 · SceneForge 등록 | 각 포지 도구 |

## 4. 교환 계약
모든 교환은 **파일 + id + 해시**다. 받는 쪽은 해시가 맞을 때만 쓴다.

| # | 무엇 | 만드는 쪽 → 받는 쪽 | 꼴 | 신원 | 판(버전) |
|---|---|---|---|---|---|
| **C-1** | stcx 실행 기록 | 포털·stcx → DynaForge | JSON(`Job.external_ref`) — `registry_id` · `slurm_job_ids` · `work_dir` · `output_dir` + **(신규) 각도별 run 폴더·d3plot 경로** | job_id | 잡마다 |
| **C-2** | 리포트 | stcx 후처리 → DynaForge | `sphere_report.html`(각도당 약 0.49 MB — 1,000각도면 484 MB, 10-28 합성 실측) | report_id(반입 때) | 반입마다 |
| **C-3** | S1 경량 추출본 | 클러스터 후처리 잡(KooD3plotReader) → manifest 는 DynaForge, 파일은 SceneForge·브라우저 뷰어 | 각도마다 HDF5 — 공통 메시 1회(`/mesh`) · 타임스텝마다(`/states/timestep_N`) 표면 변위·응력·요소 삭제 · **기준 단면 조각** | run_id = report_id + case_key | 변환기 판 · 설정(시간 창·정밀도·파트) · sha256 · 표면 규칙(10-28 StepForge 와 맞춤 — 겹친 절점 지운 육면체 면 · 사면체는 세 점 조합 넷). 10-28 원형(전 상태)은 각도당 204–670 MB(d3plot 의 1.1–3.7%) |
| **C-4** | 덱 | DynaForge → StepForge | `.k` 파일 | 덱 sha256 | 덱 판 |
| **C-5** | 파트 대응표 | StepForge → DynaForge·SceneForge | JSON — 머리(deck_sha256 · STEP 판) · pairs[pid · 파트 키(인스턴스 경로) · 정의 key · 근거 · 신뢰도] · unmatched[pid · 까닭] (10-28 StepForge 와 맞춘 초안) | (STEP 판, 덱 sha) | 대응 판 |
| **C-6** | 매핑 가중치 | StepForge → SceneForge·브라우저 뷰어 | JSON 머리 + 리틀엔디언 바이너리 — 파트(인스턴스)마다 row_ptr uint32 · col uint32(FE 절점 id) · w float32 · dist float32(mm). 행 = glb 정점(mesh·primitive·정점 수를 머리에 적는다), 값 = 무게중심 좌표 3개(사각면은 삼각 둘로 나눠 행마다 nnz 3), 템플릿 덱 기준(각도별 자세는 받는 쪽이 건다), 배열 오프셋은 8의 배수. 받는 쪽 검사 — 열이 S1 node_ids 안에 드는가 (10-28 맞춘 초안) | 파트 키 | (STEP 내용 지문, 덱 sha256, 삼각화 설정, 빌드) |
| **C-7** | CAD 장면 | StepForge → SceneForge·브라우저 뷰어 | glb(이미 있음 — 정점 `_PARTID`, 단위 m) · USD(누가 만들지는 D-9) | 파트 키 | STEP 판 |
| **C-8** | 재질 이름·밀도 | StepForge → SceneForge | 파트 표(C-5 · C-6 · glb extras)에 이름 · 밀도 · 값의 출처를 싣는다(StepForge 가 STEP 에서 직접 읽는다) | 파트 키 | STEP 판 |
| **C-9** | 외관 라이브러리 | SceneForge 소유 | 재질 이름 → 외관(MDL·PBR · 색 · 마감) | 재질 이름 | 라이브러리 판 |
| **C-10** | 렌더 요청 | 포털 절차(또는 DynaForge 화면) → SceneForge | JSON — `{report_id, case_key, mode: report|test_repro, scale: 1|N, template, camera: template|calibration_id, outputs}` | request_id | 요청마다 |
| **C-11** | 렌더 결과 | SceneForge → DynaForge | mp4·정지 화면 + 메타(배율·템플릿·판·원 run_id) | render_id | 렌더마다 |
| **C-12** | 시험 영상·카메라 교정 | 시험실(포털 경유) → SceneForge | 영상 + 교정(내부·외부 매개변수 · fps · 충돌 시각 t0) | test_id ↔ (report_id, case_key) | 교정 판 |
| **C-13** | viz 노드 분배 | 포털 실행기 → SceneForge 작업자 | 실행기 계약 확장 — 노드 종류(gpu/viz) 지정 | job_id | 실행기 판 |

## 5. 단계
| 단계 | DynaForge | StepForge | SceneForge | 포털 |
|---|---|---|---|---|
| **P0 확인·실측** | 1,000각도 리포트 반입·질의 실측 · 대표 10각도 S1 압축률·게이트 오차(클러스터) · 단면 영상 34초(10-28 — 이 덱은 약 100초)를 열기·그리기·인코딩으로 쪼개 재기(viz 노드) | 낙하 모델 하나로 대응표·가중치 가능성 | Omniverse 라이선스 본문 · MIG 그래픽 · Kit-CAE 의 HDF5 꼴 · viz 노드 헤드리스 렌더 | viz 노드 GPU 분배 가능성 · cae00↔stcx 저장소 경로 |
| **P1 공통 바탕** | `postprocess` 연산 이관 · S1 추출 단계 · manifest · 검증 게이트 · 반입 블록 분리(1,000각도 484 MB — 상세 질의 1회 22초 · 4 GB 실측) | C-5 대응표 · C-6 가중치 · 덱 리더 축퇴 꼴 보강 · C-7 USD(D-9) | 리포 세우기(이름 확정 뒤) · 제어면 골격 | C-1 · C-13 · 절차 사슬에 S1 |
| **P2 브라우저 뷰어 + S2** | 구면 위험도 맵 보강(3D·보간·허용비·임계·상위 N) · 브라우저 변형 뷰어 | (C-6·C-7 을 그대로 씀) | — | — |
| **P3 보고 mp4** | 렌더 결과 반입(C-11 → 리포트 미디어) | — | USD 장면 합성 · 외관 라이브러리 · 템플릿 · 위험 상위 N mp4 | SceneForge 등록·SSO·배포 · 절차에 렌더 |
| **P4 시험 재현** | — | — | 카메라 교정 · ×1 · 시간 동기 · 시험-해석 나란히 · 파손 표현 | C-12 시험 자료 길 |
| **P5 (선택)** | — | — | 스트리밍 · S4 대리모델(viz 노드 학습) | — |

기간은 P0 결과를 보고 정한다. **P0 가 끝나기 전에는 어느 쪽도 큰 구현에 들어가지 않는다** — 라이선스·MIG·저장소 경로 하나가 틀리면 설계가 바뀐다.

## 6. 결정 필요 (사용자)
| # | 정할 것 | 권장 |
|---|---|---|
| D-1 | 새 포지 이름 | **SceneForge** |
| D-2 | S1 꼴 | **HDF5** — KooD3plotReader 에 이미 있다. ⚠ Kit-CAE 3.0 은 HDF5 를 못 읽는다(10-28 조사 — CGNS · EnSight Gold · VTK · NumPy 등만). SceneForge 는 C-6 로 CAD 정점에 옮긴 변형을 USD 시간 샘플로 직접 쓰고, Kit-CAE 가 필요할 때만 EnSight Gold · VTK 로 바꾼다. Zarr 는 PhysicsNeMo 학습에 맞추려면 그때 변환 |
| D-3 | S1 추출본 자리 | 클러스터 저장소(원본 옆)에 두고 **요청한 각도만 cae00 로 복사**(S3). 일괄 이동은 S4 때 정한다 |
| D-4 | 원본 d3plot 정리 승인자 | 사람 승인 필수 — 누구인지 정해 주십시오 |
| D-5 | 브라우저 뷰어 자리 | **DynaForge 화면** — S2 맵을 누르면 바로 그 각도가 열린다. 데이터 계약(C-3·C-6·C-7)은 같으므로 StepForge 뷰어로 옮겨도 된다 |
| D-6 | SceneForge 담당 | 새 스택이라 전담이 필요 |
| D-7 | 외관 데이터 출처 | CAD 색 정보 · 디자인팀 자산 · 직접 만드는 라이브러리 중에서 |
| D-8 | 단면 영상 유지 | 유지하면 S1 에 기준 단면 조각을 담는다(표면만으로는 자른 면을 못 그린다) |
| D-9 | USD 를 누가 만드나(10-28 StepForge P0 에서 생김) | **SceneForge 가 glb + 파트 표에서** — 장면 정본이 SceneForge 이고, StepForge 에 pxr 의존을 넣지 않는다. StepForge 도 이 결정을 기다린다 |

10-28 지금 — D-1 · D-2 · D-3 · D-5 · D-8 은 권장안으로 착수했다(확정 아님). D-4 · D-6 · D-7 · D-9 는 미정이다.

## 7. 검증 기준
- **P0** — 실측표가 나온다(압축률 · 게이트 오차 · 1,000각도 질의 시간 · 렌더 단계별 시간 · 라이선스·MIG 답).
- **P1** — 대표 10각도 S1 이 게이트를 통과한다. 대응표가 낙하 모델의 전 파트를 덮는다(못 덮은 파트는 이름과 까닭으로 말한다). 포털 사슬이 S1 까지 돈다.
- **P2** — 맵에서 각도를 누르면 뷰어가 그 변형을 재생한다. 1,000각도 리포트의 상세 질의가 정한 시간 안에 온다.
- **P3** — 위험 상위 N 각도의 mp4 가 리포트에서 열리고 배율이 화면에 적혀 있다.
- **P4** — 시험 영상과 같은 시점·같은 시각의 렌더가 나란히 뜬다(×1).

## 8. 리스크
| 리스크 | 영향 | 대응 |
|---|---|---|
| viz 노드가 클러스터 저장소를 못 읽는다 | S3·S4 데이터 길 | 각도 단위 복사(S3) · 일괄 이동은 S4 때 결정(D-3) |
| 1,000각도 리포트 484 MB — 상세 질의 1회 22초 · 4 GB(10-28 실측) | 상세 질의가 막히고 API 메모리가 튄다 | 반입 때 블록 분리 저장(P1). 그 전에 raw_decode 로 약 5초 · 3.1 GB |
| 덱 리더가 못 읽는 요소 꼴(누운 쐐기 — 10-28 PID 20 · 21) | 그 파트가 대응표에서 빠진다 | StepForge P1 보강. 그때까지 unmatched 와 까닭으로 남긴다 |
| SceneForge 담당 미정(D-6) | P1 골격이 늦는다 | 계약 꼴만 맞춘 가짜 입력으로 골격을 먼저 세운다 |
| 운영 단면 영상이 어느 프레임부터 응력 0 으로 그려진다(10-28 — 24개 중 7개, 다시 돌리면 정상) | 리포트 영상이 오류 없이 틀린다 | KooD3plotReader 결함 보고(사용자 확인 뒤) · 영상마다 마지막 프레임 max = 0 검사 |
| koo_deep_report 가 상태 일부만 읽고 rc 0 으로 끝난다(software 백엔드 4,952 중 1,546) · 가족 파일마다 스레드라 상한 아래 죽는다 | 분석 · 영상이 조용히 잘린다 | 같은 결함 보고 · 읽은 상태 수 검사 |
| 표면만 저장해 내부 최대가 빠진다(10-28 — 사면체 파트 1 이 11각도 중 2각도에서 내부 최대, 겉면이 0.65% · 4.84% 낮음) | 판정 오류 | 정본은 리포트 · 게이트는 최대 요소가 표면일 때만 일치 요구 |
| 단면 내부 응력 | 단면 영상 불가 | S1 기준 단면 조각(D-8) |
| 파손(요소 삭제) | CAD 표면에 안 보인다 | S1 삭제 플래그 · CAD 위에 얹는 방법(P4) |
| Omniverse 라이선스·지원 | 비용·막힘 | 2026-05 부터 개발·운영·재배포 무료(NVIDIA FAQ, 10-28 확인). 약관 본문 · NGC 다운로드 페이지와 충돌해 NVIDIA 서면 확인. 지원은 NVAIE 유료($4,500/GPU/년) |
| MIG 에서 Kit RTX 가 안 될 수 있다(`+gfx` 프로파일은 있다 — 실동 기록 없음) | 동시 사용자 수 | 노드 시험. 기본은 GPU 하나에 Kit 하나 |
| 진짜처럼 보여 생기는 오해 | 잘못된 판단 | 배율 표기 의무 · 시험 재현은 ×1 고정 |
| 세 팀 일정이 엇갈린다 | 서로 막힘 | 계약(§4)을 먼저 맞추고, 파일로 주고받아 앞 단계가 늦어도 뒤가 시제품으로 진행 |
