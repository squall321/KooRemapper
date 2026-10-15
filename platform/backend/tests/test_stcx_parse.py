"""SmartTwinMCP 응답 해석 — **JSON 봉투**다(예전 :5012 의 사람이 읽는 글이 아니다).

본문의 예시는 실제 도구 소스에서 그대로 가져왔다 —
`smarttwin_mcp/src/smarttwin_mcp/runner.py:40-49`(봉투) ·
`server.py:223-225`(인자 검증 실패는 봉투가 **아니다**) ·
`tools/fullangle_drop_simulation/latest/script.sh:106-122`(제출 본문) ·
`tools/job_status/latest/script.sh:16-22` + `_shared/job_helpers.py:188-208`(상태 본문).

여기서 고정하는 것은 하나다 — **못 읽은 응답을 성공으로 접지 않는다.** 접으면 잡은 없는데
화면에는 도는 것으로 남고, 사용자는 몇 시간을 기다린 뒤에야 안다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.runner.stcx_client import (parse_status, parse_submit, registry_id_of,
                                    result_dir_of, slurm_ids_of, upload_name)

# ── 실제 모양 ──────────────────────────────────────────────────────────────

_SUBMIT_BODY = {
    "ok": True,
    "registry_id": 12,
    "job_id": "924",
    "tool": "fullangle_drop_simulation",
    "project_name": "Fullangle_Fib162",
    "num_angles": 162,
    "work_dir": "/data/koopark/df/01JABC",
    "output_dir": "/data/koopark/df/01JABC/output",
    "scenario_path": "/data/koopark/df/01JABC/scenario.json",
    "submitted_via": "backend_5010 (권한/감사) + 드라이버 클러스터 auto-tune",
    "sphere_report_path": "/data/koopark/df/01JABC/output/sphere_report.html",
    "follow_up_hint": "job_status/job_stop/... 에 registry_id 또는 job_id 사용.",
}


def _envelope(body, *, ok=True, exit_code=0, stderr=""):
    """`RunResult.to_dict()` + `tool` — 도구가 실제로 돌았을 때의 모양."""
    return {"tool": "fullangle_drop_simulation@1.1.0", "ok": ok, "exit_code": exit_code,
            "stdout": "", "stderr": stderr, "result": body,
            "transport": "local", "command": "/bin/bash .../script.sh"}


def _status(squeue):
    body = {"ok": True, "job_id": 12, "tool": "fullangle_drop_simulation",
            "work_dir": "/w", "output_dir": "/w/output", "squeue": squeue,
            "koochainrun_status": {"rc": 0, "stdout": "...", "stderr": ""}}
    return {"tool": "job_status@1.0.0", "ok": True, "exit_code": 0, "stdout": "",
            "stderr": "", "result": body, "transport": "local", "command": ""}


def _details(ids, sphere=None):
    job = {"id": 12, "tool_name": "fullangle_drop_simulation", "work_dir": "/w",
           "output_dir": "/w/output", "slurm_job_ids": list(ids)}
    if sphere:
        job["sphere_job_id"] = sphere
    return {"tool": "get_job_details@1.0.0", "ok": True, "exit_code": 0, "stdout": "",
            "stderr": "", "result": {"ok": True, "job": job},
            "transport": "local", "command": ""}


def _queued(**by_id):
    return {k: {"state": v, "name": "drop", "reason": None} for k, v in by_id.items()}


# ── 제출 ───────────────────────────────────────────────────────────────────

def test_parse_submit_reads_the_real_success_envelope():
    r = parse_submit(_envelope(_SUBMIT_BODY))
    assert r["ok"]
    assert r["registry_id"] == 12
    assert r["job_id"] == "924"
    assert r["work_dir"] == "/data/koopark/df/01JABC"
    assert r["sphere_report_path"].endswith("sphere_report.html")


def test_parse_submit_carries_the_result_dir_and_the_model_source():
    """1.1.2 부터 — `result_dir` 은 실제 결과 폴더, `model_source` 는 덱이 어디서 왔나."""
    body = {**_SUBMIT_BODY, "result_dir": "/data/single/admin/Fullangle_Fib162_924",
            "model_source": "copied"}
    r = parse_submit(_envelope(body))
    assert r["result_dir"] == "/data/single/admin/Fullangle_Fib162_924"
    assert r["model_source"] == "copied"
    # 옛 응답(칸 없음)도 성공이다 — 칸은 더해졌을 뿐이다.
    old = parse_submit(_envelope(_SUBMIT_BODY))
    assert old["ok"] and old["result_dir"] == "" and old["model_source"] == ""


def test_a_script_failure_is_not_a_success():
    """`fail()` 은 `{"ok": false, "reason": …}` 를 찍고 rc=1 로 죽는다."""
    env = _envelope({"ok": False, "reason": "Model file missing: /w/MinimumModel.k"},
                    ok=False, exit_code=1)
    r = parse_submit(env)
    assert r["ok"] is False
    assert "Model file missing" in r["detail"]


def test_an_arg_validation_failure_has_no_envelope_at_all():
    """★이 모양이 함정이다 — `exit_code`·`stdout`·`result` 가 **아예 없다**.

    `server.py:223-225` 가 도구를 돌리기 **전에** 막는다.
    """
    r = parse_submit({"ok": False, "error": "work_dir: 'work_dir' is a required property",
                      "tool": "fullangle_drop_simulation@1.1.0"})
    assert r["ok"] is False
    assert "required property" in r["detail"]


def test_a_success_without_a_registry_id_is_refused():
    """★폴링이 지목할 손잡이가 없으면 제출된 것으로 치지 않는다 — 영영 못 찾는 잡이 된다."""
    body = {k: v for k, v in _SUBMIT_BODY.items() if k != "registry_id"}
    r = parse_submit(_envelope(body))
    assert r["ok"] is False and r["error"] == "no_registry_id"


def test_the_outer_ok_alone_is_not_enough():
    """봉투는 참인데 본문이 거짓인 경우 — 둘 다 봐야 한다."""
    r = parse_submit(_envelope({"ok": False, "reason": "backend 제출 실패"}))
    assert r["ok"] is False


def test_a_dry_run_reply_is_refused():
    r = parse_submit(_envelope({"ok": True, "dry_run": True, "scenario_path": "/w/s.json"}))
    assert r["ok"] is False and r["error"] == "dry_run"


@pytest.mark.parametrize("bad", [None, "", 0, [], {}, "그냥 글"])
def test_what_cannot_be_read_is_a_failure(bad):
    assert parse_submit(bad)["ok"] is False


def test_the_reason_beats_the_error_which_beats_stderr():
    """사유 순서 — 가장 구체적인 것부터. 요청서 §3 이 정한 순서다."""
    both = _envelope({"ok": False, "reason": "구체적인 사유"}, ok=False, stderr="시끄러운 꼬리")
    both["error"] = "덜 구체적"
    assert "구체적인 사유" in parse_submit(both)["detail"]

    no_reason = _envelope({"ok": False}, ok=False, stderr="꼬리만 있다")
    no_reason["error"] = "에러 칸"
    assert "에러 칸" in parse_submit(no_reason)["detail"]

    only_tail = _envelope({"ok": False}, ok=False, stderr="꼬리만 있다")
    assert "꼬리만 있다" in parse_submit(only_tail)["detail"]


# ── 상태 ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("slurm,expect", [
    ("RUNNING", "active"), ("PENDING", "active"), ("COMPLETING", "active"),
    ("COMPLETED", "succeeded"),
    ("FAILED", "failed"), ("TIMEOUT", "failed"), ("NODE_FAIL", "failed"),
    ("CANCELLED+", "failed"),          # 꼬리표가 붙어 온다
])
def test_squeue_states_map(slurm, expect):
    assert parse_status(_status(_queued(**{"101": slurm})), _details(["101"]))["state"] == expect


def test_one_bad_direction_fails_the_whole_study():
    """하나라도 죽으면 실패다 — 방향 하나가 날아간 연구를 성공으로 넘기지 않는다."""
    got = parse_status(_status(_queued(**{"101": "RUNNING", "102": "FAILED"})),
                       _details(["101", "102"]))
    assert got["state"] == "failed" and "FAILED" in got["slurm"]


def test_all_gone_from_squeue_is_done():
    """요청서 §4 가 정한 잠정 규칙."""
    got = parse_status(_status({}), _details(["101", "102"]))
    assert got["state"] == "succeeded" and got["reason"] == "all_gone_from_squeue"


def test_an_empty_squeue_right_after_submit_is_not_done():
    """★이것이 `get_job_details` 를 함께 부르는 이유다.

    제출 직후에는 slurm id 가 아직 레지스트리에 없다. 상태 응답만 보면 `squeue` 가 비어
    있어 **"다 끝났다" 와 구분이 안 된다** — 그대로 접으면 잡이 제출 몇 초 만에 성공으로
    끝나고 사용자는 결과가 없는 성공을 본다.
    """
    got = parse_status(_status({}), _details([]))
    assert got["state"] == "active" and got["reason"] == "no_slurm_ids_yet"


def test_the_aggregation_job_counts_too():
    """본 잡이 끝나고 집계(sphere)만 남은 구간을 '끝' 으로 읽지 않는다."""
    got = parse_status(_status(_queued(**{"999": "RUNNING"})), _details(["101"], sphere="999"))
    assert got["state"] == "active"
    assert "999" in slurm_ids_of(_details(["101"], sphere="999"))


@pytest.mark.parametrize("broken", [
    {},
    {"ok": False, "error": "tool not found"},
    None,
])
def test_an_unreadable_status_never_becomes_done(broken):
    assert parse_status(broken, _details(["101"]))["state"] == "unknown"


def test_unreadable_details_never_become_done():
    """id 목록을 못 읽었으면 **모른다** — 빈 목록으로 읽어 'active' 라고 우기지 않는다."""
    assert parse_status(_status({}), {"ok": False, "error": "x"})["state"] == "unknown"


def test_a_new_slurm_state_is_unknown_not_guessed():
    got = parse_status(_status(_queued(**{"101": "WEIRD_NEW_STATE"})), _details(["101"]))
    assert got["state"] == "unknown" and "WEIRD_NEW_STATE" in got["reason"]


def test_the_raw_is_kept_for_fixing_the_rule_later():
    """요청서 §4 — 실제 응답 원문을 받아 종료 판정을 고칠 수 있어야 한다."""
    got = parse_status(_status(_queued(**{"101": "RUNNING"})), _details(["101"]))
    assert "101" in got["raw"]


# ── 지목 ───────────────────────────────────────────────────────────────────

def test_registry_id_comes_from_the_job_id_field_of_the_status_reply():
    """⚠ 상태 응답의 `job_id` 는 **레지스트리 행 id** 다 — 제출 응답의 것(slurm)과 다르다."""
    assert registry_id_of(_status({})) == 12
    assert registry_id_of({"ok": False, "error": "x"}) is None


def test_the_result_dir_comes_from_the_work_dir_of_the_status_reply():
    """상태 응답의 `work_dir` 은 registry 의 것 = 결과 폴더다(우리가 준 스테이징이 아니다)."""
    assert result_dir_of(_status({})) == "/w"
    assert result_dir_of({"ok": False, "error": "x"}) == ""


# ── 반입 이름 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("given,want", [
    ("model.k", "model.k"),
    ("model.key", "model.k"),
    ("model.dyn", "model.k"),
    ("MODEL.K", "MODEL.k"),            # 받는 쪽 패턴 `^/.+\.k$` 는 대소문자를 가린다
    ("a.b.key", "a.b.k"),
    ("noext", "noext.k"),
])
def test_the_upload_name_always_ends_in_lowercase_k(given, want):
    """잡 id 가 앞에 붙는다 — 한 사용자 폴더 안에서 잡끼리 갈린다."""
    assert upload_name(given, "01JOB") == "01JOB_" + want
