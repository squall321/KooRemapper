# 메시 그림 래스터 블록 — 결정 노트 (2026-11-02)

### 왜 C++ 이 아니라 MCP 서버인가

세 op 의 SVG 는 한글 `<text>` 를 담는다(`section.cpp:863-878` 축 눈금·제목, 글꼴 목록
`Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, NanumGothic, sans-serif`). 글자를 못 그리는 경량
래스터라이저(nanosvg 류)는 눈금·제목을 빼먹는다 — 숫자가 사라진 그림은 거짓이다. 글꼴까지 다루는 렌더러를
C++ 에 넣는 것보다 SIF 에 rsvg-convert 와 나눔 글꼴을 넣는 편이 훨씬 작다. 바이너리·cae00 설치가 없다.

### 왜 `[dict, Image]` 인가

`-> dict` 도구는 FastMCP 1.27 에서 출력 스키마가 없고 텍스트 블록 하나(JSON)만 낸다. `-> list` 로 바꿔
`[같은 dict, Image]` 를 내면 첫 블록 텍스트가 **바이트까지 같다**(mcp.sif 안에서 비교). `CallToolResult` 를
직접 만들 필요가 없다.

### 실측 — 폭 1500px, rsvg-convert(시험 SIF)

| 그림 | SVG | PNG | 256색 PNG | JPEG q85 | 시간 |
|---|---|---|---|---|---|
| 작은 덱 단면 | 9KB | 39KB | 17KB | 79KB | 0.25s |
| 작은 덱 모식도 | 3KB | 77KB | 31KB | 62KB | 0.23s |
| 작은 덱 표면 | 94KB | 238KB | 97KB | 69KB | 0.25s |
| 37MB 배터리 덱 단면 | 447KB | 279KB | **89KB** | 189KB | 0.27s |
| 37MB 배터리 덱 표면(다각형 101k) | 11.4MB | 705KB | 257KB | **149KB** | 1.04s · RSS 250MB |

평평한 색(단면·모식도)은 256색 PNG 가, 음영(표면)은 JPEG 가 작다 → 순서를 원본 PNG → 256색 PNG → JPEG →
폭 줄이기로 둔다. 256KB 는 포털의 "되면" 목표이고, 게이트웨이 상한(8MiB)과는 거리가 멀다.

### SIF 크기

시험 SIF 101MB(지금 60MB). 나눔 글꼴과 librsvg 의존(cairo·pango)이 대부분이다.

### 패키지를 고정했다 — 고정 없이 다시 구우면 mcp 2.3.0 이 들어왔다

`mcp.def` 는 `mcp>=1.2` 만 적고 있었다. 다시 구우니 **mcp 2.3.0**·anyio 4.16·starlette 1.10 이 들어왔다(지금
SIF 는 1.28.0·4.14·1.3.1). 주 판이 바뀌면 서버가 통째로 깨질 수 있어, 지금 SIF 의 `pip freeze` 를
`mcp.constraints.txt` 로 박고 `-c` 로 묶었다. 새 SIF 는 옛 SIF 와 패키지가 같고 pillow 하나만 늘었다(freeze diff).

### dev 의 MCP 는 SIF 의 mcp 가 아니라 호스트 `~/.local` 의 mcp 를 쓴다 (고치지 않았다)

인스턴스가 `python server.py`(사용자 사이트 켜짐)로 뜨고 홈이 붙어서, `~/.local/lib/python3.12` 의
**mcp 1.27.1**·typing_extensions 가 SIF 의 것을 가린다(실측 `mcp.__file__`). 운영(cae00)은 `~/.local` 이
없으니 SIF 의 1.28.0 을 쓴다 — dev 와 운영의 mcp 판이 다르다. 고정하지 않은 새 SIF(anyio 4.16)는 이
`~/.local` typing_extensions 와 부딪쳐 `cannot import name 'sentinel'` 로 **dev 서버가 못 떴을 것**이다.
`[dict, Image]` 직렬화는 1.27.1·1.28.0 둘 다에서 텍스트 바이트 동일을 확인했다.
고치려면 `mcp.def` 의 `%environment` 에 `PYTHONNOUSERSITE=1` — dev 의 mcp 판이 바뀌는 일이라 이번에는 하지 않았다.
