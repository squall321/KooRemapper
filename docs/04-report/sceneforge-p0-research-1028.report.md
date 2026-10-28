# SceneForge P0 공개 문서 조사 (2026-10-28)

> 위임한 웹 조사(10-28)의 보고서 전문이다. 계획을 바꾸는 두 주장은 원문을 다시 열어 확인했다 — NVIDIA Omniverse FAQ(「As of May 2026, Omniverse is freely available for both development and production use with no NVIDIA AI Enterprise subscription required」) · Kit-CAE 3.0 Importing Data(형식 목록에 HDF5 · VTKHDF · Zarr · d3plot 없음).
> 계획 `docs/01-plan/features/sceneforge-1028.plan.md` · 총괄 `drop-twin-1028.plan.md` · P0 실측 `drop-twin-p0-1028.report.md`

## 요약
- 라이선스 — NVIDIA 공식 FAQ·문서상 2026-05-01부터 Omniverse는 개발·프로덕션·재배포 모두 무료이고, 유료 NVIDIA AI Enterprise(구 Omniverse Enterprise 흡수, 정가 $4,500/GPU/년)는 지원용이다. 단 약관 본문에 Kit가 아직 유료 품목으로 남아 있어 NVIDIA 서면 확인이 필요하다.
- MIG — RTX PRO 6000 Blackwell 3종 모두 최대 4개 MIG를 지원하고 `+gfx` 프로파일에서 그래픽 API를 쓸 수 있다. 다만 Kit RTX가 1g.24gb+gfx에서 돈다는 공개 기록은 없다.
- CAE — Kit-CAE 3.0에는 범용 HDF5 리더가 없다. 공식 충돌 해석 예제는 결과를 EnSight Gold로 변환해서 쓴다.
- 헤드리스 — `--no-window` + 뷰포트 캡처/Replicator. Ubuntu 22.04/24.04, 드라이버 R580/R595, Kit PB26h1(110.1.5).
- 인코딩 — GPU당 NVENC 4기, Kit `omni.videoencoding`이 NVENC로 MP4를 만든다. 헤드리스·MIG·Apptainer에서 실제로 되는지는 노드 시험으로만 판정된다.

## 1. 라이선스
**Confirmed**
- "As of May 2026, Omniverse is freely available for both development and production use with no NVIDIA AI Enterprise subscription required."[1] "As of 2026-05-01, Omniverse is now free for development, production, and redistribution use."[2] 구독이 없으면 지원은 포럼·Discord뿐이다[1].
- 지배 문서는 "NVIDIA Software License Agreement"(Last Modified 2026-05-07)[4]와 "Product Specific Terms for NVIDIA AI Products"(Last Modified 2026-04-15)[3]다. "NVIDIA has consolidated the Product Specific Terms for NVIDIA Omniverse into these AI Products Terms."[3] 예전 "Omniverse Enterprise" 정의는 "NVIDIA AI Enterprise"로 합쳐졌다[3]. NGC 표기는 "NVIDIA Agreements | Enterprise Software | NVIDIA Software License Agreement"다[7]. 옛 "NVIDIA Omniverse License Agreement"는 Kit-CAE LICENSE에 아직 남아 있다[15].
- kit-app-template은 "The software and materials are governed by the NVIDIA Software License Agreement"이고 LICENSE는 그 참고본(v. 2025-01-30)이다[5]. USD Composer · USD Viewer · Kit Base Editor · Kit Service는 모두 이 저장소의 템플릿이라 같은 약관을 따른다[5].
- NVAIE 비용은 1년 $4,500/GPU · 3년 $13,500 · 5년 $18,000 · 영구 $22,500이다[6]. 번들은 "Included with NVIDIA H100, H200 NVL and A800 PCIe GPUs"뿐이다[6]. 온프레미스는 "the number of physical GPUs in the computing environment"로 센다[4]. 특정 플랫폼 전용 구독 예로 "IGX, DGX Spark, or RTX PRO Server"가 적혀 있다[3].
- "licensed solely to run on systems with NVIDIA Platforms … (c) NVIDIA Omniverse"[3]. 개발자 프로그램으로 받은 소프트웨어는 "not for use, distribution or deployment in production."[3]

**Likely**
- 사내 엔지니어링 영상 렌더용 자체 Kit 앱은 구독 없이 프로덕션에 쓸 수 있다. 지원 계약은 20 GPU 기준 정가 연 $90,000이다(산술). MIG로 나눠도 과금은 물리 GPU 단위다.
- 검토한 SLA·PST에서 헤드리스 · 서버 · 배치 · 컨테이너 사용을 따로 막는 조항은 찾지 못했다.

**Unknown — NVIDIA 서면 확인 필요**
- 문서끼리 충돌한다. PST A.5는 아직 "NVIDIA Omniverse (including Kit)"를 NVAIE 품목에 둔다[3]. NGC의 PB26h1 Kit SDK 다운로드 페이지는 "Subscription required to access this content"(NVAIE 또는 Developer Program)다[7]. 포럼 답도 "You almost certainly do need NVIDIA Enterprise"(06-22)에서 "Confirmed, yes, they can be redistributed for free."(06-29)로 뒤집혔다[8].
- 사내 서비스 운영이 "offer as a service" 조항(공지 파일 · 사용 보고 의무)에 해당하는지, RTX PRO Server 전용 SKU 가격과 OEM 번들 여부.

## 2. MIG와 그래픽
**Confirmed**
- 에디션은 Server(400–600 W, passive) · Workstation(600 W) · Max-Q(300 W), 모두 96 GB GDDR7 ECC[9]. 3종 모두 1g.24gb(+gfx)×4 · 2g.48gb(+gfx)×2 · 4g.96gb(+gfx)×1을 지원한다[10]. "+gfx: Adds support for graphics APIs (new in GB20X)."[10]
- 원칙은 "No graphics APIs are supported (for example, OpenGL, Vulkan and so on)." 예외로 "The exception to this is RTX Pro 6000 Blackwell GPUs where certain MIG profiles support graphics."[10] 지원 구성에 "Bare-metal, including containers", 드라이버 "R575 (>= 575.51.03) or later"[10].
- Workstation · Max-Q는 vBIOS 98.02.55.00.00 · 98.02.6A.00.00 이상과 DisplayModeSelector로 compute 모드 전환이 필요하다 — "setting display mode to compute will disable physical display output"[10].
- Server Edition은 MIG-backed vGPU를 지원하는 "first data center GPU capable of supporting both compute and graphics workloads within MIG instances"[11].
- Kit 107.3.3(Isaac Sim 5.1)은 Azure MIG-backed vGPU(4g.96gb)에서 GPU 생성에 실패했다(물리 ID와 MIG UUID 불일치). "later Kit versions on which IsaacSim 6.0.1 depends"에서 고쳐졌고 6.0.1은 Kit 110.1.2[13].
- Slurm 26.05는 MIG 인스턴스를 개별 GPU로 다루지만 "does not support dynamic MIG partitioning"[14].

**Likely**
- 베어메탈 컨테이너의 +gfx에는 vGPU 소프트웨어가 필요 없어 보이나 +gfx에 대해 명시한 문장은 없다. 포럼에는 "MIG with all 3 'flavors' of the RTX PRO 6000, but vGPU only with the server edition"[12].
- 프로파일 표의 열을 맞춰 읽으면 1g.24gb+gfx는 NVENC · NVDEC · JPEG 각 1, 2g는 각 2다(정렬이 깨진 표에서 추론)[10].
- 판단 — 1g는 SM 1/4(RT 코어도 1/4로 추정) · 24 GB라 노드당 8세션이 되지만 한 작업은 대략 1/4 속도다. 기본은 GPU당 Kit 프로세스 하나 · 컨테이너별 GPU 고정(2×RTX PRO 6000 운용 사례[12])으로 두고, 실측 VRAM이 24 GB 미만이고 GPU가 놀 때만 MIG를 쓴다.

**Unknown**
- 1g/2g +gfx 인스턴스에서 Kit RTX(실시간 · 패스트레이싱)와 NVENC가 도는지, Vulkan이 할당된 MIG 인스턴스를 제대로 고르는지, Server Edition도 디스플레이 모드 전환이 필요한지.

## 3. Kit-CAE
**Confirmed**
- https://github.com/NVIDIA-Omniverse/kit-cae — "Omniverse Kit sample for CAE use-cases", 외부 기여 받지 않음. LICENSE는 "a reference copy of the Omniverse License Agreement"(오픈소스 아님). 기본 Kit 110.1.2[15]. 문서 3.0/2.1/1.5는 2026-10-28 갱신[16].
- 3.0 입력 형식 — CGNS · EDEM · EnSight Gold(.case/.encas) · Eclipse · NanoVDB · NumPy(.npz/.npy) · OpenFOAM · VTK(.vtk/.vti/.vtr/.vts/.vtp/.vtu)[16]. HDF5 · Zarr · d3plot은 없다. 2.x 개요에 "native formats (CGNS, HDF5, VTK, EnSight, NumPy)"라는 문장은 있으나 임포터 목록에 HDF5는 없다[16].
- 3.0 "OmniSci" 데이터 모델 — typed prim `OmniSciDataset` + 다중 적용 `OmniSciArrayAPI:<name>` · `OmniSciFieldAPI:<name>`(association "vertex"/"cell"). 원본은 payload로 참조하고 값은 `UsdAttribute.Get()` 때 지연 로드. 예전 `CaeDataSet`/`CaeFieldArray`는 "not the recommended starting point for new formats or applications"[15].
- 시간은 "mapped seconds = source value * Scale + Offset", Operator Temporal로 필드 보간[16].
- 새 형식은 읽기 전용 `SdfFileFormat` 플러그인(C++ 권장, Python 가능). Data Delegate는 "Do not use it for new formats."[15]
- 예제 "Time-Varying Structural Analysis"는 외연적 범퍼 충돌 결과를 "converted to EnSight Gold binary format"한 것(쉘 약 13,500절점 · 51스텝)[16].

**Likely** — 우리 HDF5를 넣는 길은 셋이다. (a) EnSight Gold 변환(공식 예제와 같은 길) (b) 자체 SdfFileFormat 플러그인 (c) Kit-CAE 없이 `UsdGeomMesh` points 시간 샘플 + 응력 primvar 직접 작성. 렌더만이 목적이면 (c)가 가장 단순하다(판단).

**Unknown** — 유지보수 · 지원 약속(문서상 "reference implementation"뿐) · VTKHDF 지원.

## 4. 헤드리스 배치
**Confirmed**
- "A physical display must be connected to your GPU, unless you are running kit headless with `--no-window` for streaming."[17] Kit Service 템플릿은 "useful for creating headless services leveraging Omniverse Kit functionality"[5].
- Movie Capture는 프레임 범위 · FPS · RTX Real-Time 2.0/Path Tracing/Iray 프리셋 UI다[18]. 스크립트용 `omni.kit.capture.viewport`는 "You need to create a viewport, even when working headlessly"[18]. 명령행 렌더는 Replicator 권장("The best way is not to use Movie Capture which is really a GUI extension"). 108에서 Replicator가 없던 사례 · 107.3 헤드리스 스크립트가 프레임을 하나도 내지 않은 사례가 미해결이다[18].
- GitHub 템플릿은 "based on a Feature Branch", 프로덕션은 NGC Production Branch 권장[5]. PB26h1 = 110.1.5(2026-10-14), FB = 110.4.0(2026-10-08)[7].
- 지원 OS "Ubuntu 22.04/24.04". Blackwell 검증 드라이버 580.95.05 · 595.58.03(워크스테이션은 570.169도)[19]. 570.144 이하는 셰이더 컴파일 중 크래시, 595.58.03은 Kit 109.0.5/110.1.0 미만과 비호환[19]. 서버 권장 구성 "8x RTX Pro 6000 Blackwell Server Edition"[19].
- 컨테이너 베이스 — NGC "Omniverse Base Container - Ubuntu 22"(2026.2.3)[20], `repo package_container` 기본 `ov-base-ubuntu22-x86_64:1.0.0`(110.3.0~)[5]. "Kit Kernel" 이미지는 106.5.0(2025-03) 뒤 갱신 없음[20].
- 폐쇄망 — "Air-gapped builds additionally require the Kit Extension Registry package"[7]. 텔레메트리는 "remove the `omni.kit.telemetry` extension"[21].
- Apptainer `--nvccli`의 기본 capability는 "compute,utility"뿐이라 graphics(OpenGL/Vulkan) · video를 호스트 환경변수로 켜야 한다[22]. Docker는 `NVIDIA_DRIVER_CAPABILITIES=all`, Vulkan ICD 이중 마운트 금지, `VK_DRIVER_FILES`로 선택 권장[23]. Isaac Lab HPC 가이드(Apptainer 1.2.5/1.3.4, SLURM · PBS 검증)는 "the compute node has access to the internet at all times"를 요구한다[23].

**Likely** — 공식 「헤드리스 렌더러」 이미지는 없고 앱을 베이스 이미지 위에 패키징한다. 셰이더 캐시를 잡 사이에 유지해야 기동이 짧다. 문서엔 최소 드라이버가 아니라 검증 버전만 있다(Blackwell 최저 검증 570.169 WS · 580.95.05 데이터센터)[5][19].

**Unknown** — Kit 110에서 시간 샘플 USD를 `--no-window` 배치로 프레임 시퀀스 · MP4까지 내는 공식 예제 · Apptainer `--nv`만으로 Vulkan ICD가 잡히는지 · 비 Ubuntu 호스트.

## 5. 영상 인코딩
**Confirmed** — 3종 모두 NVENC 4기(9세대) · NVDEC 4기(6세대), 동시 세션 "Unrestricted"[24]. 서버 페이지 "four video encode and four video decode engines"[9]. `omni.videoencoding`은 "programmable interface to encode image frames into MP4 video files", 설정에 "Tuning Info of NVENC encoding", 캡처 확장의 MP4 설정은 `/exts/omni.videoencoding/*`[25].
**Likely** — 헤드리스에서도 같은 경로로 NVENC를 쓸 것이다. 막히면 PNG/EXR 시퀀스를 ffmpeg `h264_nvenc`로 묶는다.
**Unknown** — MIG 인스턴스 · Apptainer 안에서 NVENC.

## 6. Kit App Streaming
kit-app-template 문서는 "Helm charts on any Kubernetes cluster"로 자체 운영 가능(2026-04-06). Streaming 26.10.0(2026-10)이 "support customer-managed, upstream Kubernetes clusters in your own data center"와 On-Premises Deployment Guide를 추가[26]. 스트리밍 별도 라이선스 문구는 없고 2026-05 변경으로 무료로 보인다(Likely). Kit 밖 RTX 라이브러리 `ovrtx`는 "currently pre-release software"[27].

## 노드에서 직접 확인할 것
- [ ] `nvidia-smi -q` — Product Name(에디션) · VBIOS · Driver(580.95.05 이상, MIG는 575.51.03 이상) · MIG Mode · Display · GPU Virtualization Mode.
- [ ] `nvidia-smi -i 0 -mig 1` → `nvidia-smi mig -lgip` — `+gfx` 프로파일, 프로파일별 NVENC/NVDEC/JPG/OFA 수 · 인스턴스 수.
- [ ] WS/Max-Q면 DisplayModeSelector 상태, Server면 모드 전환 없이 MIG가 켜지는지.
- [ ] `nvidia-smi mig -cgi <+gfx ID> -C` → 컨테이너 안 `nvidia-smi -L` · `vulkaninfo --summary`로 MIG UUID와 Vulkan 장치 대응.
- [ ] Kit 110.1.5 `--no-window`로 시간 샘플 USD를 PNG · MP4로 — RTX 초기화 로그 · 최대 VRAM · 프레임당 시간을 전체 GPU / 2g / 1g에서 비교.
- [ ] 인코딩 중 `nvidia-smi encodersessions`로 NVENC 사용 확인.
- [ ] Apptainer `--nv`와 `--nvccli`(호스트 `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video`)에서 각각 Vulkan · NVENC.
- [ ] Slurm `AutoDetect=nvml`의 MIG 인식 · 잡의 `CUDA_VISIBLE_DEVICES`와 Kit이 고른 GPU 일치.
- [ ] 외부망을 끊고 기동(Air Gap 패키지 · 로컬 레지스트리 · telemetry 제거).
- [ ] 첫 실행과 캐시 재사용 실행의 기동 시간 · `/etc/os-release`.

## 출처
1. Omniverse FAQ — https://www.nvidia.com/en-us/omniverse/enterprise/faq/ (「As of May 2026」, 10-28 열람 · 재확인)
2. License Server Overview (Legacy) — https://docs.omniverse.nvidia.com/ov/latest/ov_license_server/license_server_overview.html
3. Product Specific Terms for NVIDIA AI Products — https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/ (Last Modified 2026-04-15)
4. NVIDIA Software License Agreement — https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/ (Last Modified 2026-05-07)
5. kit-app-template — https://github.com/NVIDIA-Omniverse/kit-app-template
6. NVIDIA AI Enterprise Pricing — https://docs.nvidia.com/ai-enterprise/planning-resource/licensing-guide/latest/pricing.html (2026-09-02)
7. NGC Kit SDK PB26h1 — https://catalog.ngc.nvidia.com/orgs/nvidia/teams/omniverse/resources/kit-sdk-linux-pb26h1 · FB https://catalog.ngc.nvidia.com/orgs/nvidia/teams/omniverse/resources/kit-sdk-linux
8. 포럼 — https://forums.developer.nvidia.com/t/nvidia-omniverse-licensing-change/375138 · https://forums.developer.nvidia.com/t/can-we-use-nvidia-omniverse-sdk-kit-and-nucleus-server-as-saas-in-cloud-for-our-commercial-project/374101
9. RTX PRO 6000 — https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/ · https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/
10. MIG User Guide — https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-mig-profiles.html · https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/deployment-considerations.html · https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/getting-started-with-mig.html
11. vWS Sizing Guide — https://docs.nvidia.com/vgpu/sizing/virtual-workstation/latest/gpus-vws.html
12. 포럼 — https://forums.developer.nvidia.com/t/mig-support-on-rtx-pro-6000-blackwell/334906 · https://forums.developer.nvidia.com/t/running-two-isaac-sim-6-0-0-instances-on-a-dual-nvidia-rtx-pro-6000-blackwell-workstation-using-webrtc/374228
13. https://github.com/isaac-sim/IsaacSim/issues/794 · https://docs.isaacsim.omniverse.nvidia.com/6.0.1/overview/release_notes.html
14. https://slurm.schedmd.com/gres.html
15. https://github.com/NVIDIA-Omniverse/kit-cae
16. Kit-CAE User Guide — https://docs.omniverse.nvidia.com/guide-kit-cae/latest/index.html · https://docs.omniverse.nvidia.com/guide-kit-cae/latest/v3/importing-data.html (10-28 재확인) · https://docs.omniverse.nvidia.com/guide-kit-cae/latest/kit-cae-v2.html · https://docs.omniverse.nvidia.com/guide-kit-cae/latest/v2/examples/time-varying-structural.html
17. https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/linux_troubleshooting.html
18. https://docs.omniverse.nvidia.com/extensions/latest/ext_core/ext_movie-capture.html · https://forums.developer.nvidia.com/t/how-to-capture-stage-from-kit-app-in-headless-mode/327895 · https://forums.developer.nvidia.com/t/rendering-out-aov-image-sequences-via-command-line-in-headless-mode/341892
19. https://docs.omniverse.nvidia.com/dev-guide/latest/common/technical-requirements.html
20. https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/containers/ov-base-ubuntu-22 · https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/containers/ov-kit-kernel
21. https://docs.omniverse.nvidia.com/usd/latest/common/data-collection.html
22. https://apptainer.org/docs/user/latest/gpu.html
23. https://isaac-sim.github.io/IsaacLab/main/source/isaaclab/installation.html · https://isaac-sim.github.io/IsaacLab/main/source/features/hpc_clusters.html
24. https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new
25. https://docs.omniverse.nvidia.com/kit/docs/omni.videoencoding/0.2.2/Overview.html · https://docs.omniverse.nvidia.com/kit/docs/omni.videoencoding/0.2.1/SETTINGS.html · https://docs.omniverse.nvidia.com/kit/docs/omni.kit.capture.viewport/2.11.1/SETTINGS.html
26. https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/streaming.html · https://docs.omniverse.nvidia.com/ov/ovs/latest/release-notes/26_10_0.html
27. https://github.com/nvidia-omniverse/ovrtx
