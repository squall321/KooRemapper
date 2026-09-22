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


# ── 각도 프리셋 — 목록은 서버가 들고 있다 ──────────────────────────────────
from app.runner.stcx_client import parse_presets  # noqa: E402

# 실제로 도구를 불러 받은 원문의 해당 부분(2026-09-22 실측).
_REAL_CATALOG_TAIL = (
    "■ 사용 가능한 각도 프리셋 (angle_preset, /data/scenario): "
    "26direction, 6face, fibonacci-100, fibonacci-1000, fibonacci-10000\n"
    "  프리셋을 base 로 삼고 scenario_overrides 가 깊은 병합(dict 재귀, 리스트/스칼라 교체)됩니다.\n"
)


def test_presets_come_from_the_server_not_from_our_code():
    got = parse_presets(_REAL_CATALOG_TAIL)
    assert got == ["26direction", "6face", "fibonacci-100", "fibonacci-1000", "fibonacci-10000"]


def test_a_new_preset_on_the_server_shows_up_without_a_code_change():
    """이게 이 함수의 존재 이유다 — 박아 두면 있는 것을 못 쓴다."""
    text = "■ 사용 가능한 각도 프리셋 (angle_preset): 26direction, fibonacci-250, my-new-preset\n"
    assert "fibonacci-250" in parse_presets(text)
    assert "my-new-preset" in parse_presets(text)


def test_prose_around_the_line_is_not_mistaken_for_a_preset():
    got = parse_presets(_REAL_CATALOG_TAIL)
    assert all(" " not in p for p in got)
    assert "프리셋을" not in " ".join(got)


def test_no_preset_line_means_an_empty_list_not_a_crash():
    assert parse_presets("옵션 카탈로그인데 프리셋 줄이 없다") == []
    assert parse_presets("") == []
    assert parse_presets({"result": "각도 프리셋: a, b"}) == ["a", "b"]


# ── 시나리오 옵션 → scenario.json ──────────────────────────────────────────
#
# 여기가 틀리면 **조용히 틀린다.** 도구는 모르는 키를 그냥 병합해 두고 지나가므로,
# 이름이 어긋나면 화면에서 고른 값이 해석에 아무 영향을 안 준다 — 그런데 잡은 성공한다.
from app.runner.stcx_client import build_scenario_overrides, deep_merge  # noqa: E402


def test_physics_options_land_in_simulation_params():
    ov = build_scenario_overrides({"height": 1200, "t_final": 0.01, "dt": 2e-6,
                                   "offset_distance": 0.1, "drop_surface": "RigidWall"})
    sp = ov["simulation_params"]
    assert sp["height"] == 1200
    assert sp["tFinal"] == 0.01, "scenario.json 의 이름은 tFinal 이다(t_final 이 아니다)"
    assert sp["dt"] == 2e-6
    assert sp["offset_distance"] == 0.1
    assert sp["drop_surface"]["type"] == "RigidWall"


def test_nothing_given_means_nothing_overridden():
    """빈 덮어쓰기를 보내면 프리셋 값을 건드린다 — 아무것도 안 주면 아무것도 안 만든다."""
    assert build_scenario_overrides({"model": "m.k", "job_name": "x"}) == {}


def test_the_angle_source_follows_what_you_actually_gave():
    """방향 수만 주고 source_type 을 안 주면 fibonacci 가 아닌 프리셋 원에 num_points 만 얹힌다."""
    ov = build_scenario_overrides({"num_directions": 162})
    a = ov["scenarios"][0]["angle_source"]
    assert a["source_type"] == "fibonacci_lattice" and a["num_points"] == 162

    assert build_scenario_overrides({"pitch_step": 10})["scenarios"][0]["angle_source"] == {
        "source_type": "pitching_sweep", "pitch_step": 10}
    assert build_scenario_overrides({"roll_step": 15})["scenarios"][0]["angle_source"] == {
        "source_type": "rolling_sweep", "roll_step": 15}


def test_a_case_file_decides_the_angle_source_by_itself():
    ov = build_scenario_overrides({"num_directions": 100}, has_case_txt=True)
    assert ov["scenarios"][0]["angle_source"]["source_type"] == "case_txt_file", (
        "각도 파일을 골랐다는 것이 곧 의사표시다")


def test_an_explicit_angle_source_wins_over_the_guess():
    ov = build_scenario_overrides({"angle_source": "cuboid_geometry", "num_directions": 50})
    assert ov["scenarios"][0]["angle_source"]["source_type"] == "cuboid_geometry"


def test_cumulative_and_resources():
    ov = build_scenario_overrides({"cumulative_steps": 3, "ncpu": 64})
    assert ov["scenarios"][0]["cumulative"]["num_steps"] == 3
    assert ov["environment"]["ncpu"] == 64


def test_user_overrides_win_last():
    """**이 규칙이 이 함수의 요점이다** — 서버에 새 옵션이 생겨도 이 표를 안 고치고 쓸 수 있다."""
    ov = build_scenario_overrides({
        "height": 1500,
        "scenario_overrides": {"simulation_params": {"height": 800, "density": 7.85e-9}},
    })
    sp = ov["simulation_params"]
    assert sp["height"] == 800, "사용자가 직접 적은 값이 낱낱 옵션을 이겨야 한다"
    assert sp["density"] == 7.85e-9, "표에 없는 키도 그대로 실려야 한다"


def test_user_overrides_can_reach_places_the_form_has_no_field_for():
    ov = build_scenario_overrides({"scenario_overrides": {
        "preserve_includes": ["*.inc"],
        "simulation_params": {"dynamic_relaxation": {"enabled": True, "nrcyck": 300}}}})
    assert ov["preserve_includes"] == ["*.inc"]
    assert ov["simulation_params"]["dynamic_relaxation"]["nrcyck"] == 300


def test_deep_merge_follows_the_servers_rule():
    """딕트는 재귀, 리스트·스칼라는 교체 — 규칙이 어긋나면 화면과 클러스터가 달라진다."""
    base = {"a": {"x": 1, "y": 2}, "l": [1, 2], "s": "old"}
    over = {"a": {"y": 9, "z": 3}, "l": [7], "s": "new"}
    assert deep_merge(base, over) == {"a": {"x": 1, "y": 9, "z": 3}, "l": [7], "s": "new"}
    assert base == {"a": {"x": 1, "y": 2}, "l": [1, 2], "s": "old"}, "원본을 건드리면 안 된다"
