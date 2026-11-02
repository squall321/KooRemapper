# 메시 그림 래스터 블록 — 체크리스트 (2026-11-02)

계획: `mcp-figure-png-1102.plan.md` · 결정: `mcp-figure-png-1102.context-notes.md`

## 조사 (끝)
- [x] 그림 도구 흐름 — API 잡이 C++ op 으로 SVG 를 남기고 MCP 는 `svg_file_id` 만 준다
- [x] SVG 에 한글 `<text>` 가 있다(section·surfview·stackdiagram 셋 다, 글꼴 목록에 NanumGothic)
- [x] `mcp.sif` 에 렌더러 없음(PIL·cairosvg·rsvg 없음, numpy 만) · Debian trixie
- [x] FastMCP 1.27 — `-> list` 로 `[dict, Image]` 를 내면 텍스트 블록 바이트 동일 · 출력 스키마 없음
- [x] 시험 SIF(rsvg+나눔+pillow) 30초 빌드 · 크기·시간 실측(결정 노트)

## 구현
- [ ] `platform/mcp_server/figure_png.py` — SVG → (bytes, fmt, w, h), 실패는 짧은 까닭
- [ ] 메시 그림 도구 셋 — `[dict, Image]` + `figure_png` / `figure_png_error`, 낡은 "PNG 경로 없음" 문구 고치기
- [ ] `report_image` · `report_compare` — 이미지마다 출처 한 줄
- [ ] `mcp.def` — librsvg2-bin · fonts-nanum · pillow, `requirements.txt` 에 pillow
- [ ] TOOLS.md · SKILL.md 의 "픽셀은 없다" 문구

## 시험
- [ ] 단위 — 렌더러 없음 · 시간 초과 · 크기 줄이기 순서(호스트)
- [ ] SIF 안 실렌더 — 한글 글꼴 있음, 큰 그림이 256KB 안으로
- [ ] backend 전체 · figures_smoke(이미지 블록 확인)

## 배포
- [ ] dev `mcp.sif` 교체(옛 것 백업) · MCP 재기동
- [ ] 게이트웨이로 그림 한 번 — 이미지 블록 + `fig_…` 줄 · `figure_to_report` → RA
- [ ] 포털에 SHA · (승인 뒤) dist 번호
- [ ] 운영 Drive 게시 — **사용자 승인**
