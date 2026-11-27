# 자동 파이프라인 MCP 꼴 — auto_* 표지(readOnlyHint)와 실패는 isError + {error, detail} JSON · 성공에 error 칸 없음(계약 §0.3 · §3 · §4-3)
"""MCP 서버를 그쪽 venv 로 import 해 잰다(`mcp_probe.py auto`) — 백엔드 venv 에는 mcp 가 없다. 계획
docs/01-plan/features/auto-pipeline-1127.plan.md."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

PLATFORM = Path(__file__).resolve().parents[2]
MCP_PY = PLATFORM / "mcp_server" / "venv" / "bin" / "python"
PROBE = Path(__file__).with_name("mcp_probe.py")
needs_mcp = pytest.mark.skipif(not MCP_PY.exists(), reason="MCP venv 없음(platform/mcp_server/venv)")
READ_ONLY = {"auto_changes", "auto_profiles", "auto_check", "auto_status", "auto_result"}
WRITES = {"auto_submit", "auto_cancel"}


@pytest.fixture(scope="module")
def probe() -> dict:
    got = subprocess.run([str(MCP_PY), "-I", str(PROBE), "auto"], capture_output=True, text=True, timeout=180,
                         env={"PATH": "/usr/bin:/bin"})
    assert got.returncode == 0, got.stderr[-2000:]
    return json.loads(got.stdout.strip().splitlines()[-1])


@needs_mcp
def test_read_tools_say_read_only_and_writing_tools_do_not(probe):
    ann = probe["annotations"]
    assert ann, "auto_* 도구가 없다"
    for name, a in ann.items():
        if name in WRITES:
            assert not a.get("readOnlyHint") and a.get("destructiveHint") is False, (name, a)
        else:
            assert name in READ_ONLY and a.get("readOnlyHint") is True, (name, a)


@needs_mcp
def test_failures_are_is_error_with_an_error_word_and_successes_carry_no_error(probe):
    c = probe["calls"]
    assert c["ok"]["isError"] is False and "error" not in c["ok"]["body"], "성공에 error 칸이 실렸다(계약 §4-3)"
    assert c["refused"] == {"isError": True, "body": {"error": "not_ready", "detail": "갖춰지지 않았다",
                                                      "missing": [{"kind": "infra", "why": "공유 폴더 전"}]}}
    assert c["auth"]["isError"] and c["auth"]["body"]["error"] == "http_401" and c["auth"]["body"]["detail"]
    assert c["html"]["isError"] and c["html"]["body"]["error"] == "unreachable"
    assert c["timeout"]["isError"] and c["timeout"]["body"]["error"] == "timeout"
