"""stcx 도구 응답 해석 — **JSON 이 아니라 사람이 읽는 글**을 돌려주는 도구들이다.

그리고 실패도 `isError` 가 아니라 "error: …" 로 시작하는 **정상 반환값**으로 온다.
그대로 믿으면 제출되지 않은 잡이 제출된 것으로 남고, 사용자는 몇 시간을 기다린 뒤에야 안다.
해석을 한자리에 떼어 두고 여기서 고정한다. 본문의 예시 글은 실제 도구 소스에서 가져왔다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runner.stcx_client import parse_state, parse_submit

_REAL_OK = (
    "✅ 제출 완료 — job_id=12345\n"
    "template: smarttwin-fullangle-drop\n"
    "script: /data/scripts/x.sh\n"
    "결과 폴더: /data/single/<사용자>/drop_12345/ (드라이버 잡 완료 후)\n"
    "추적: slurm_job_results(job_id=12345) / slurm_job_log(job_id=12345)"
)
_REAL_STATE = (
    "잡 12345 결과\n"
    "  이름: drop\n"
    "  상태: {state}  (ExitCode 0:0)\n"
    "  경과: 01:02:03  파티션: alpha\n"
    "  작업 디렉토리: /data/single/u/drop_12345\n"
    "  결과 파일 (3개):"
)


def test_parse_submit_reads_the_real_success_text():
    r = parse_submit(_REAL_OK)
    assert r["ok"] and r["job_id"] == "12345"


def test_parse_submit_treats_an_error_string_as_failure():
    """가장 위험한 모양 — 도구가 실패를 **정상 반환값**으로 돌려준다."""
    for text in ("error: 제출 실패(status=500): boom",
                 "error: 인증/권한 거부(status=401): ...",
                 "오류: 각도 프리셋 로드 실패"):
        r = parse_submit(text)
        assert r["ok"] is False, text
        assert r["error"] == "tool_refused"


def test_parse_submit_catches_a_dry_run_that_slipped_through():
    r = parse_submit("[DRY-RUN] 제출 계획 (실제 제출은 dry_run=False)\n...")
    assert r["ok"] is False and r["error"] == "dry_run"


def test_parse_submit_refuses_what_it_cannot_read():
    """판정 못 하면 실패다 — 성공으로 접으면 없는 잡을 영영 폴링한다."""
    for text in ("", "제출은 했는데 형식이 바뀌었다", {"weird": 1}):
        assert parse_submit(text)["ok"] is False


def test_parse_submit_unwraps_a_wrapped_string():
    assert parse_submit({"result": _REAL_OK})["job_id"] == "12345"


def test_parse_state_maps_the_slurm_states():
    assert parse_state(_REAL_STATE.format(state="RUNNING"))["state"] == "active"
    assert parse_state(_REAL_STATE.format(state="PENDING"))["state"] == "active"
    assert parse_state(_REAL_STATE.format(state="COMPLETED"))["state"] == "succeeded"
    assert parse_state(_REAL_STATE.format(state="FAILED"))["state"] == "failed"
    assert parse_state(_REAL_STATE.format(state="TIMEOUT"))["state"] == "failed"
    # sacct 는 꼬리표를 붙이기도 한다
    assert parse_state(_REAL_STATE.format(state="CANCELLED+"))["state"] == "failed"


def test_parse_state_says_unknown_instead_of_guessing():
    """모르는 것을 성공이나 실패로 접으면, 도구 고장과 잡 종료가 같은 모양이 된다."""
    assert parse_state(_REAL_STATE.format(state="WEIRD_NEW_STATE"))["state"] == "unknown"
    assert parse_state("잡 1 결과\n  이름: x")["state"] == "unknown"       # 상태 줄 없음
    assert parse_state("error: 인증 실패")["state"] == "unknown"           # 도구가 거절
    assert parse_state("")["state"] == "unknown"


def test_unknown_state_is_never_mistaken_for_done():
    """이 단언이 이 파일에서 가장 중요하다 — 모름이 완료로 새면 결과 없이 succeeded 가 뜬다."""
    for bad in ("", "error: x", "상태: NOPE", "아무 말"):
        assert parse_state(bad)["state"] not in ("succeeded", "failed")
