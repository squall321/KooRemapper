# 메시 그림을 리포트로 — MCP 응답에 래스터 이미지 블록 (2026-11-02)

**요청**: 포털(hwaxportal-a5), 사용자 지시 · 급함. 게이트웨이(844f91af)가 MCP 이미지 블록을 7일 저장하고
`figure_to_report` 로 Report Archive(RA)에 넣는데, RA 는 png/jpeg/gif/webp 만 받고 SVG 는 415 로 거절한다.
DynaForge 의 메시 그림 도구 셋은 SVG(`svg_file_id`)만 내서 리포트까지 못 간다.

## 무엇을

1. `mesh_section_figure` · `mesh_surface_figure` · `mesh_stack_diagram` 이 지금 응답(dict)에 더해
   **이미지 블록**(PNG, 크면 JPEG)을 하나 돌려준다. 폭 1500px 안팎, 256KB 이하가 목표. SVG 는 그대로 남긴다.
2. `report_image` · `report_compare` — 이미지마다 출처 한 줄(`file_id`·sha256·리포트·케이스).
3. 큰 출력은 텍스트에 싣지 않는다(게이트웨이 상한 이미지 한 장 8MiB).

## 어떻게 — 결정과 근거

- **래스터화는 MCP 서버(Python)에서** 한다. C++ op 이 아니다. SVG 에 한글(축 눈금 `가로 눈금`·파트 제목)이
  있어 글꼴을 가진 진짜 SVG 렌더러가 필요하다 — C++ 에 넣으면 큰 일이다.
- `mcp.sif` 에 `librsvg2-bin`(rsvg-convert) · `fonts-nanum`(apt) · `pillow`(pip). KooRemapper 바이너리 변경 없음.
- 응답은 `[같은 dict, Image]`. FastMCP 1.27 이 dict 텍스트 블록을 **바이트까지 같게** 내고 출력 스키마도
  없음을 SIF 안에서 확인했다 — 이미지를 무시하는 호출자에게는 키 하나(`figure_png` 또는 `figure_png_error`)만 늘어난다.
- 크기 줄이기: 원본 PNG → 256색 PNG → JPEG q85 → 폭 ×0.8(최소 800px). 실측은 결정 노트.

## 배포

server.py · 새 모듈은 바인드 마운트(재기동). `mcp.sif` 는 새로 굽는다 → dev 교체(옛 SIF 백업) → 게이트웨이 확인 →
운영은 `dist-to-drive.sh`(사용자 승인) → cae00 은 `dist-from-drive.sh` + MCP 인스턴스 재기동.

## 받아들이는 기준(포털)

- 게이트웨이로 메시 그림 하나를 부르면 이미지 블록과 `그림 저장 — fig_…` 줄이 보인다.
- `figure_to_report` 가 그 그림을 RA 리포트에 넣는다.
- 이미지를 무시하는 호출자의 응답은 깨지지 않는다.
