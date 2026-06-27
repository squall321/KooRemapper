# Claude Desktop 연결 가이드

KooRemapper MCP 서버는 **streamable-http + `Authorization: Bearer <PAT>`** 방식이다.
Claude **Code** 는 HTTP 트랜스포트를 직접 지원하지만, Claude **Desktop** 의
`claude_desktop_config.json` 은 기본이 **stdio(로컬 명령)** 이라 원격 HTTP 서버에는
**`mcp-remote` 브리지**로 붙는다(원격 HTTP ↔ stdio 중계 + 헤더 주입).

## 1) 토큰 발급
웹 대시보드(MCP 토큰) 또는:
```bash
curl -s -X POST http://<host>:8700/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"<id>","password":"<pw>"}'                 # → access_token
curl -s -X POST http://<host>:8700/api/v1/me/tokens -H "Authorization: Bearer <access_token>" \
  -H 'Content-Type: application/json' -d '{"name":"desktop"}'   # → kr_... (한 번만 표시)
```

## 2) claude_desktop_config.json
경로: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows `%APPDATA%\Claude\claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "kooremapper": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "http://<host>:8701/mcp",
        "--header", "Authorization: Bearer kr_..."
      ]
    }
  }
}
```
- `npx`(Node 18+) 필요. 저장 후 Claude Desktop 재시작 → 도구 20개가 보인다.
- 비-localhost(외부)면 서버에 `MCP_ALLOWED_HOSTS` 를 지정하고 가급적 nginx/TLS 뒤에 둔다.

## 3) 파일 보내기 — 두 가지 경로

**A. 대화 첨부 (어디서나, 텍스트 K파일에 적합)**
파일을 대화에 첨부/붙여넣기 → "이 K파일 새 세션에 올려줘" → Claude 가 내용을 읽어
`create_session` → `upload_kfile(content=...)` 호출. K파일은 텍스트라 잘 된다.
한계: 대화 채널로 내용을 실어나르므로 **수 MB 이상 대형 메쉬는 비효율/잘림**.

**B. 로컬 경로 (서버를 같은 머신에서 돌릴 때, 대형 파일에 적합)**
MCP 서버가 Desktop 과 같은 PC 에서 돌면 디스크에서 직접 읽고 쓴다:
- `upload_local_path(session_id, "/path/to/big_model.k")`
- `save_result_to_path(session_id, file_id, "/path/to/out.k")`
대화로 내용을 옮기지 않아 수십 MB도 OK.

> 대형/바이너리 파일 + 원격 서버 조합이면, 웹 프론트엔드(직접 업로드/다운로드)가 가장 매끄럽다.

## 표준 워크플로 (Desktop)
1. (A) 파일 첨부 후 "올려줘" 또는 (B) `upload_local_path` 로 업로드
2. `list_session_files` 로 내부(노드/요소/*INCLUDE) 확인
3. `describe_operation(op)` 로 옵션 확인 → `run_operation(session_id, op, args)`
4. `get_job` 폴링 → `download_result` (또는 `save_result_to_path`) 로 회수
