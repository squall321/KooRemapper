# 기여 가이드 — 새 기능을 웹·MCP·Python에 한 번에 반영하기

세 표면(웹 React, MCP, Python 클라이언트)은 전부 **같은 REST API + `kr_` 토큰** 위의
얇은 클라이언트다. 그래서 기능을 더할 때 한 곳만 잘 건드리면 셋이 같이 따라온다.

## 케이스 1 — 새 오퍼레이션 추가 (대부분의 확장)

**단일 진실원은 카탈로그다** (`backend/app/runner/catalog_data.json` → `catalog.py`).
op마다 별도 코드가 없고, 세 표면이 카탈로그를 범용으로 소비한다.

- 웹: [SchemaForm.tsx](frontend/src/modules/sessions/SchemaForm.tsx) 가 `args_schema`로 폼 생성
- MCP: `list_operations` / `describe_operation` / `run_operation` 3개 도구만
- Python: `kr.list_operations()` / `describe_operation()` / `run(sid, op, args)`
- API: `POST /sessions/{id}/jobs` 가 `{operation, args}`를 카탈로그 스키마로 검증

### 절차
1. C++ 바이너리가 새 op를 지원한다(상위 도구).
2. `catalog_data.json`에 항목을 추가한다 — `name`, `category`, `summary`,
   `invocation`(positional|yaml), 옵션(`params`/`keys`), `example.args`.
   - 파일 인자는 세션 내 파일명으로 받도록 `type: file`(또는 `x-kind: session_file`).
3. 끝. 웹 폼이 자동 생성되고, MCP·Python이 바로 실행하며, 서버가 args를 검증한다.

### 검증
- `cd backend && .venv/bin/python -m pytest tests/test_parity.py` —
  모든 op가 `args_json_schema`로 표현 가능한지(= 세 표면에서 노출 가능한지) 강제.
- 스모크: `mcp_server/smoke.py`, `clients/python/smoke.py` 가 op 수 ≥ 45를 확인.

> 유일한 수작업은 카탈로그가 바이너리의 실제 옵션을 정확히 반영하는 것이다. 바이너리에서
> 옵션을 자동 추출하지는 않으니 새 op의 옵션은 카탈로그에 적어줘야 한다. 한 번 적으면 끝.

## 케이스 2 — 오퍼레이션이 아닌 새 기능 (새 리소스/엔드포인트)

자동이 아니다. 표면마다 얇게 한 줄씩 더한다. 모두 같은 응답 봉투
(`{success, data, message, errors}`)를 쓰므로 추가가 일관적이다.

1. **백엔드** — `app/modules/<feature>/routes.py`에 라우트 추가, `app/modules/__init__.py`에 등록.
2. **웹** — [endpoints.ts](frontend/src/shared/api/endpoints.ts)에 함수 + UI.
3. **MCP** — `mcp_server/server.py`에 `@mcp.tool` 한 개.
   도구를 더하면 `app/modules/system/routes.py`의 `mcp_tools` 숫자도 올린다
   (안 올리면 `test_parity.py`가 실패한다).
4. **Python** — `clients/python/kooremapper/__init__.py`의 `KooRemapper`와
   `AsyncKooRemapper` 양쪽에 메서드 추가.

## 전체 검증 (PR 전)
```bash
cd backend && .venv/bin/python -m pytest tests/ -q          # 38+ tests
cd ../frontend && pnpm build                                 # tsc + vite
# 러닝 스택 대상 스모크 (선택, 스택 없으면 자동 skip)
mcp_server/venv/bin/python mcp_server/smoke.py
PYTHONPATH=clients/python python clients/python/smoke.py
```
