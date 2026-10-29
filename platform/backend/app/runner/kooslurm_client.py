# KooSlurm 대시보드 REST 로 귀환 매니페스트·잡 상태를 보고 리포트를 내려받는 클라이언트(예약자 PAT)
"""계약은 KooSlurm `docs/REQUEST-result-return.md` §6-1 이다(10-28, 실 Slurm 검증 §6-3).

- 신원 — 예약한 사용자 본인의 `kst_` PAT 를 `Authorization: Bearer` 로 싣는다. 서비스 계정은 없다.
- 끝남 신호 — `GET /api/jobs/<id>/files/download?path=output/return_manifest.json` 이 404 면 아직, 200 이면 끝.
  ⚠ **없는 잡도 404 다**(결과 폴더를 못 찾으면 같은 꼴). 그래서 404 만으로 실패를 정하지 않고
  `/info` 로 잡 상태를 따로 본다 — 판정은 부르는 쪽(`app.worker.postprocess_return`) 몫이다.
- C(후처리 잡)가 도는 동안 이전 매니페스트는 `output/return_manifest.prev.json` 으로 옮겨져 있다.

주소는 덱 업로드와 같은 대시보드다(`settings.stcx_backend_url`, backend_5010 이 둘 다 싣는다).

어떤 실패도 예외로 올리지 않는다 — `{"ok": False, "error": …, "detail": …}` 로 돌려준다(stcx_client 와 같은
규율). ⚠ `detail` 에 토큰이 들어가지 않게 한다 — 헤더는 어디에도 옮겨 적지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

MANIFEST_PATH = "output/return_manifest.json"
PREV_MANIFEST_PATH = "output/return_manifest.prev.json"
# 매니페스트는 몇 KB 다. 이보다 크면 매니페스트가 아니다.
_SMALL_MAX_BYTES = 1 << 20
_CHUNK = 1 << 20


def _failed(resp: httpx.Response) -> dict:
    """KooSlurm 오류 본문 `{"success": false, "error": …}` 에서 까닭을 뽑는다."""
    try:
        body = resp.json()
    except ValueError:
        body = None
    why = body.get("error") if isinstance(body, dict) else resp.text
    return {"ok": False, "error": f"http_{resp.status_code}", "detail": str(why or "")[:300]}


def _transport(exc: Exception) -> dict:
    kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport"
    return {"ok": False, "error": kind, "detail": f"{type(exc).__name__}: {exc}"[:300]}


class KooSlurmClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 30.0,
                 client: httpx.AsyncClient | None = None) -> None:
        self._base = str(base_url or "").rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout
        self._client = client
        self._own = client is None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _url(self, job_id: str, tail: str) -> str:
        return f"{self._base}/api/jobs/{job_id}/{tail}"

    async def _small(self, job_id: str, path: str) -> dict:
        """작은 파일 하나 — `{"ok": True, "found": False}`(404) · `{"ok": True, "found": True, "body": bytes}`."""
        try:
            r = await self._http().get(self._url(job_id, "files/download"), params={"path": path},
                                       headers=self._headers)
        except httpx.HTTPError as exc:
            return _transport(exc)
        if r.status_code == 404:
            return {"ok": True, "found": False}
        if r.status_code != 200:
            return _failed(r)
        if len(r.content) > _SMALL_MAX_BYTES:
            return {"ok": False, "error": "too_large", "detail": f"{len(r.content)} 바이트 — 매니페스트가 아니다"}
        return {"ok": True, "found": True, "body": r.content}

    async def manifest(self, job_id: str) -> dict:
        """귀환 매니페스트 — 404 면 `found: False`(아직), 200 이면 `manifest` 에 JSON 객체."""
        got = await self._small(job_id, MANIFEST_PATH)
        if not got.get("ok") or not got.get("found"):
            return got
        try:
            data: Any = json.loads(got["body"])
        except ValueError:
            return {"ok": False, "error": "bad_manifest", "detail": got["body"][:200].decode("utf-8", "replace")}
        if not isinstance(data, dict):
            return {"ok": False, "error": "bad_manifest", "detail": "JSON 객체가 아니다"}
        return {"ok": True, "found": True, "manifest": data}

    async def has_prev_manifest(self, job_id: str) -> dict:
        """C 가 돌기 시작하면 생기는 이전 매니페스트가 있나 — `{"ok": True, "found": bool}`."""
        got = await self._small(job_id, PREV_MANIFEST_PATH)
        got.pop("body", None)
        return got

    async def job_info(self, job_id: str) -> dict:
        """sacct 로 본 잡 상태 — `{"ok": True, "found": True, "state": "COMPLETED", "exit_code": "0:0"}`.

        404 는 `found: False` 다. ⚠ 대시보드는 sacct 가 5초 상한에 걸려도 404 를 준다 — 한 번으로 단정하지 말 것.
        `state` 는 첫 낱말만 대문자로 둔다(`CANCELLED by 0` → `CANCELLED`).
        """
        try:
            r = await self._http().get(self._url(job_id, "info"), headers=self._headers)
        except httpx.HTTPError as exc:
            return _transport(exc)
        if r.status_code == 404:
            return {"ok": True, "found": False}
        if r.status_code != 200:
            return _failed(r)
        try:
            job = (r.json() or {}).get("job") or {}
        except (ValueError, AttributeError):
            return {"ok": False, "error": "bad_info", "detail": r.text[:200]}
        words = str(job.get("state") or "").split()
        return {"ok": True, "found": True, "state": words[0].upper() if words else "",
                "exit_code": str(job.get("exitCode") or "")}

    async def download(self, job_id: str, path: str, dest: Path, *, max_bytes: int) -> dict:
        """파일 하나를 `dest` 로 흘려 쓴다 — `{"ok": True, "bytes": n, "sha256": hex}`. 실패면 `dest` 를 지운다."""
        h = hashlib.sha256()
        n = 0
        done = False
        try:
            async with self._http().stream("GET", self._url(job_id, "files/download"),
                                           params={"path": path}, headers=self._headers) as r:
                if r.status_code != 200:
                    await r.aread()
                    return _failed(r)
                with dest.open("wb") as fh:
                    async for chunk in r.aiter_bytes(_CHUNK):
                        n += len(chunk)
                        if n > max_bytes:
                            return {"ok": False, "error": "too_large",
                                    "detail": f"{max_bytes} 바이트를 넘었다"}
                        h.update(chunk)
                        fh.write(chunk)
            done = True
        except httpx.HTTPError as exc:
            return _transport(exc)
        except OSError as exc:
            return {"ok": False, "error": "write_failed", "detail": f"{type(exc).__name__}: {exc}"[:300]}
        finally:
            if not done:
                dest.unlink(missing_ok=True)
        return {"ok": True, "bytes": n, "sha256": h.hexdigest()}

    async def close(self) -> None:
        if self._own and self._client is not None:
            await self._client.aclose()
            self._client = None
