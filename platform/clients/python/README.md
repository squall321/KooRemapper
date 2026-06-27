# KooRemapper Python client

A thin Python client (sync **and** async) over the KooRemapper platform REST API
— the same surface the web UI and the MCP server use. Authenticate with a `kr_`
personal access token (issue one from the web dashboard → **MCP 토큰**).

## Install

```bash
pip install -e platform/clients/python
# or just put the package dir on PYTHONPATH; only dependency is httpx
```

## Sync

```python
from kooremapper import KooRemapper

kr = KooRemapper("http://127.0.0.1:8700", token="kr_...")   # or env KOOREMAPPER_TOKEN
s = kr.create_session("warpage study")
kr.upload(s.id, "flat.k")
kr.upload(s.id, "bent.k")

job = kr.run(s.id, "map", {
    "bent_mesh": "bent.k", "flat_mesh": "flat.k",
    "output": "out.k", "single": True,
})
job = kr.wait(job.id)                  # poll until terminal
print(job.status, job.exit_code)

kr.download(s.id, "out.k", "./out.k")  # by filename or file id → saves, returns path
```

Discover what you can run (catalog-driven — every operation the platform exposes):

```python
for op in kr.list_operations():
    print(op.name, "—", op.summary)
spec = kr.describe_operation("map")    # full args JSON Schema + example
print(spec.args_schema)
```

## Async

```python
import asyncio
from kooremapper import AsyncKooRemapper

async def main():
    async with AsyncKooRemapper(token="kr_...") as kr:
        s = await kr.create_session("warpage")
        await kr.upload(s.id, "flat.k")
        job = await kr.run(s.id, "map", {...})
        await kr.wait(job.id)
        await kr.download(s.id, "out.k", "./out.k")

asyncio.run(main())
```

## Notes

- `base_url` / `token` fall back to env `KOOREMAPPER_API_BASE` / `KOOREMAPPER_TOKEN`.
- Responses are attribute-accessible (`s.id`, `job.status`, `op.name`).
- Errors raise `KooRemapperError` (with `.status`).
- `run()` / `describe_operation()` are **generic**: any operation in the platform
  catalog works without a client change — see the smoke test for the pattern.

## Smoke test

```bash
# against a running stack; auto-mints+revokes a temp PAT (admin creds), CI-safe skip
PYTHONPATH=platform/clients/python python platform/clients/python/smoke.py
```
