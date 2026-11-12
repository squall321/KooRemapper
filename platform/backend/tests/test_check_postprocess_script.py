# 후처리 설정 점검 스크립트 — 값을 출력하지 않는다 · 빈 칸 · 닿지 않는 창구 · 비밀 없이 거절하는 창구를 바로 말한다
"""`platform/infra/scripts/check-postprocess.py` (2026-11-12, 포털 낙하 파이프라인 2번).

비밀은 dev 박스 파일에만 둔다(포털) — 이 스크립트가 값을 화면에 옮기면 그 약속이 깨진다. 그래서 가짜 비밀을 심고
출력 어디에도 그 글자가 없는지 본다. 위임 창구는 로컬 가짜 서버로 흉내 낸다(망 없이).
"""
from __future__ import annotations

import http.server
import subprocess
import sys
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "scripts" / "check-postprocess.py"
SECRET = "s3cret-should-never-print-9f2a"
PAT = "kr_ShouldNeverPrint0123456789"


def _run(env_text: str, *extra) -> tuple[int, str]:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / ".env"
        f.write_text(env_text, encoding="utf-8")
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), "--env-file", str(f), *extra],
                           capture_output=True, text=True, timeout=60,
                           env={"PATH": "/usr/bin:/bin"})         # 박스의 KOORM_* 가 섞이지 않게
    return p.returncode, p.stdout + p.stderr


class _Sso(http.server.BaseHTTPRequestHandler):
    def do_POST(self):                                    # noqa: N802
        if self.headers.get("X-Heax-Gateway-Secret") == SECRET:
            body = b'{"access_token": "kst_TokenShouldNeverPrint0123", "username": "alice"}'
            self.send_response(200)
        else:
            body = b'{"error": "forbidden"}'
            self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Sso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_empty_fields_are_named_and_fail():
    rc, out = _run("")
    assert rc == 1
    assert "KOORM_STCX_BACKEND_URL" in out and "비었음" in out


def test_an_unreachable_backend_is_said_and_no_value_is_printed():
    rc, out = _run(f"KOORM_STCX_BACKEND_URL=http://127.0.0.1:9\nKOORM_KOOSLURM_SSO_SECRET={SECRET}\n"
                   f"KOORM_GATEWAY_PAT={PAT}\nKOORM_GATEWAY_MCP=http://127.0.0.1:9/mcp\n")
    assert rc == 1 and "닿지 않는다" in out
    assert SECRET not in out and PAT not in out and "127.0.0.1:9" not in out


def test_a_live_window_that_refuses_without_secret_passes_and_email_mints_without_printing_the_token():
    srv = _server()
    try:
        url = "http://127.0.0.1:%d" % srv.server_address[1]
        env = f'KOORM_STCX_BACKEND_URL="{url}/"\nKOORM_KOOSLURM_SSO_SECRET={SECRET}\n'
        rc, out = _run(env)
        assert rc == 0 and "HTTP 403" in out and "정상" in out
        rc, out = _run(env, "--email", "alice@example.com")
        assert rc == 0 and "username=alice" in out
        assert "kst_TokenShouldNeverPrint" not in out and SECRET not in out
    finally:
        srv.shutdown()
