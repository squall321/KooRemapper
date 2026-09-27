# 덱이 정의되지 않은 것을 가리키면 잡 제출을 막는다 — 업로드 메타 → 게이트 (P1-5)
"""왜 이 시험이 있나 (2026-09-26).

P1-6 이 검사를 넓혀 `info` 의 보고는 정확해졌는데 **막는 자리가 없었다.** 실측 — 추적 덱
489장 중 **40장에 실제 결함**이 들어 있고 그 40장이 전부 `rc=0` 으로 나갔다. 하류
(pyKooCAE REMAP 체인·플랫폼 워커)는 rc 로만 판정하므로 LS-DYNA 에 가서야 터진다.
`info` 의 rc=0 은 **계약**이라 바꿀 수 없으므로(플랫폼이 업로드마다 돈다) 막는 자리는
잡 제출이다.

이 시험의 절반은 **등급을 지우지 않았는지**다. `*INCLUDE` 를 못 읽었으면 그 안에 정의됐을
수 있어 단정할 수 없다. 그것까지 막으면 오탐이고, 오탐 한 번에 사람은 게이트를 통째로 끈다.
그래서 바이너리가 두 문구로 나눠 말하고(`[ERROR] 정의되지 않은 …` / `[WARN] … 못 찾은 …`)
파서가 그 구분을 `grade` 로 보존하고 게이트는 `certain` 만 본다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.runner.kfile_inspect import _parse_ref_dangling

# 실제 `info` 출력에서 그대로 떠 온 조각들 (2026-09-26, HEAD 바이너리).
CERTAIN = """[INFO] Running validation...
[ERROR] 정의되지 않은 것을 가리키는 카드 2건 — LS-DYNA 가 키워드 단계에서 멈춥니다
  line 258 *PART: 섹션 1 이 정의되지 않았습니다
  line 262 *PART: 섹션 1 이 정의되지 않았습니다
  칸 뜻을 확신하지 못해 검사하지 않은 자리 2곳(오탐을 내지 않으려고 건너뜁니다)
[OK] Mesh is valid
"""
UNCERTAIN = """[WARN] 이 덱 안에서 정의를 못 찾은 참조 2건 — *INCLUDE 안에 있을 수 있어 단정하지 않습니다
  line 258 *PART: 섹션 1 의 정의를 이 덱에서 못 찾았습니다
  line 262 *PART: 섹션 1 의 정의를 이 덱에서 못 찾았습니다
  *INCLUDE 안은 보지 않았습니다: assembled_result.dynain
"""
DAMAGED = """[OK] 참조 무결성 OK (세트·파트·섹션·재질 미정의 참조 0건)
[ERROR] 망가진 카드 2건 — LS-DYNA 가 이 칸을 우리와 다르게 읽습니다
  line 22 *CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID: SSID 칸에 실수 0.33 가 들어 있습니다(정수 칸입니다)
  line 22 *CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID: MSID 칸에 실수 0.1 가 들어 있습니다(정수 칸입니다)
"""
CLEAN = """[OK] 참조 무결성 OK (세트·파트·섹션·재질 미정의 참조 0건)
[OK] Mesh is valid
[OK] All elements have positive Jacobian
"""


def test_clean_deck_carries_no_ref_dangling():
    """온전한 덱은 메타에 이 키를 아예 싣지 않는다 — 키가 있으면 볼 게 있다는 뜻이어야 한다."""
    assert _parse_ref_dangling(CLEAN) is None


def test_certain_grade_is_preserved():
    ref = _parse_ref_dangling(CERTAIN)
    assert ref is not None
    assert ref["grade"] == "certain", "이 등급만 잡 제출을 막는다"
    assert ref["count"] == 2
    assert ref["top"][0] == {"line": 258, "keyword": "*PART", "what": "섹션 1 이 정의되지 않았습니다"}


def test_uncertain_grade_is_not_promoted():
    """⚠ 이것을 `certain` 으로 올리면 인클루드를 쓰는 정상 덱이 전부 막힌다."""
    ref = _parse_ref_dangling(UNCERTAIN)
    assert ref is not None
    assert ref["grade"] == "uncertain"
    assert ref["count"] == 2
    assert ref["unread_includes"] == ["assembled_result.dynain"]


def test_damaged_cards_are_certain_regardless_of_includes():
    """망가진 카드는 이 덱 안에서 본 것이라 `*INCLUDE` 와 무관하게 단정할 수 있다."""
    ref = _parse_ref_dangling(DAMAGED)
    assert ref is not None
    assert ref["grade"] == "certain"
    assert ref["damaged"] == 2


def test_top_is_capped():
    """수천 건이 와도 메타가 부풀지 않아야 한다 — 상위 N 만 싣는다."""
    many = "[ERROR] 정의되지 않은 것을 가리키는 카드 900건 — LS-DYNA 가 키워드 단계에서 멈춥니다\n"
    many += "".join(f"  line {i} *ELEMENT: 파트 {i} 이 정의되지 않았습니다\n" for i in range(1, 40))
    ref = _parse_ref_dangling(many)
    assert ref["count"] == 900
    assert len(ref["top"]) == 5


def test_gate_only_blocks_certain():
    """`dangling_status` 는 단정 등급만 낸다 — 게이트가 그것만 보고 막는다."""
    from app.modules.sessions.services import dangling_status  # noqa: PLC0415

    class F:
        def __init__(self, name, meta):
            self.filename, self.meta = name, meta

    rows = [
        F("bad.k", {"ref_dangling": {"grade": "certain", "count": 3, "damaged": 1, "top": []}}),
        F("maybe.k", {"ref_dangling": {"grade": "uncertain", "count": 9, "top": []}}),
        F("clean.k", {}),
        F("nometa.k", None),
    ]

    import app.modules.sessions.services as svc

    async def fake_list_files(db, session_id):
        return rows

    orig = svc.list_files
    svc.list_files = fake_list_files
    try:
        import asyncio

        out = asyncio.run(dangling_status(None, "s"))
    finally:
        svc.list_files = orig

    assert set(out) == {"bad.k"}, "불확실 등급과 메타 없는 파일은 막지 않는다"
    assert out["bad.k"]["count"] == 3 and out["bad.k"]["damaged"] == 1


def test_default_is_warn_not_block():
    """⚠ 기본은 **통과**다(2026-09-27 캠페인 결정).

    검사는 정확하지만 실사용 덱에 몇 장이 걸리는지 아직 안 세어 봤다. 첫날부터 막으면 멀쩡한
    운용이 멈추고 사람은 게이트를 통째로 끈다 — 그 뒤엔 진짜를 놓친다. 그래서 경고로 시작한다.
    기본값을 뒤집는 것은 실사용 숫자를 센 뒤의 결정이고, 그때 이 시험도 같이 고쳐야 한다.
    """
    from app.modules.jobs.schemas import JobCreate  # noqa: PLC0415

    assert JobCreate(operation="info", args={}).allow_dangling_refs is True, "기본은 통과다"
    assert JobCreate(operation="info", args={}, allow_dangling_refs=False).allow_dangling_refs is False


def test_warning_path_does_not_pass_silently():
    """막지 않는다는 것이 **조용히 지나간다**는 뜻이어서는 안 된다 — 잡 기록에 남아야 한다."""
    src = (Path(__file__).resolve().parents[1] / "app/modules/jobs/routes.py").read_text(encoding="utf-8")
    assert "dangling_warnings.append" in src, "통과 경로에서 경고를 남겨야 한다"
    assert "warnings=dangling_warnings or None" in src, "그 경고가 Job 에 실려야 한다"
    assert "HTTP_422_UNPROCESSABLE_ENTITY" in src, "막는 쪽도 남아 있어야 한다(allow=false)"


def test_runner_does_not_clobber_submission_warnings():
    """런너가 개행 경고를 **덮어쓰면** 제출 시점 경고가 사라진다 — 이어 붙여야 한다."""
    src = (Path(__file__).resolve().parents[1] / "app/worker/runner_loop.py").read_text(encoding="utf-8")
    assert "job.warnings = (job.warnings or []) + nl_warns" in src


def test_gate_message_tells_how_to_see_all_of_it():
    """422 문구가 `--strict` 를 가리켜야 한다 — 건수만 보여 주면 사람이 다음에 뭘 할지 모른다."""
    src = (Path(__file__).resolve().parents[1] / "app/modules/jobs/routes.py").read_text(encoding="utf-8")
    assert "allow_dangling_refs" in src
    assert "--strict" in src, "전부 보는 방법을 문구가 가리켜야 한다"
    assert "키워드 단계" in src


def _run_dangling(rows):
    """`dangling_status` 를 가짜 파일 목록으로 돌린다."""
    import asyncio

    import app.modules.sessions.services as svc
    from app.modules.sessions.services import dangling_status

    async def fake_list_files(db, session_id):
        return rows

    orig = svc.list_files
    svc.list_files = fake_list_files
    try:
        return asyncio.run(dangling_status(None, "s"))
    finally:
        svc.list_files = orig


class _F:
    def __init__(self, name, meta):
        self.filename, self.meta = name, meta


def _certain(n=2):
    return {"ref_dangling": {"grade": "certain", "count": n, "damaged": 0, "top": []}}


def test_include_target_is_not_judged_standalone():
    """다른 덱이 `*INCLUDE` 하는 파일은 **단독으로 판정하지 않는다.**

    LS-DYNA 는 그 파일을 혼자 읽지 않으므로 "이 덱 안에 정의가 없다" 는 결함이 아니다.
    실사용 1,967장 실측(2026-09-27) — 단정 등급 148장 중 **147장이 오탐**이고 그중 **122장이
    바로 이 부류**다(같은/부모 폴더의 다른 덱이 인클루드하는 파일). 오탐율 99.3%.
    """
    rows = [
        _F("master.k", {"includes": ["parts.k", "sub/mesh.k"]}),
        _F("parts.k", _certain()),                       # 인클루드 대상 → 면제
        _F("sub/mesh.k", _certain()),                    # 경로째로도 면제
        _F("standalone.k", _certain(5)),                 # 아무도 인클루드하지 않는다 → 낸다
    ]
    out = _run_dangling(rows)
    assert set(out) == {"standalone.k"}, out
    assert out["standalone.k"]["count"] == 5


def test_basename_match_also_exempts():
    """옛 세션은 경로가 평탄화돼 올라온다 — 이름만으로도 맞춰야 한다(인클루드 게이트와 같은 규율)."""
    rows = [
        _F("master.k", {"includes": ["./sub/parts.k"]}),
        _F("parts.k", _certain()),
    ]
    assert _run_dangling(rows) == {}


def test_gate_does_not_fall_back_to_whole_session():
    """⚠ 이 잡이 **쓰지도 않는 덱** 때문에 경고가 붙어서는 안 된다.

    인클루드 게이트에는 `or inc` 폴백이 있다(빠진 인클루드는 세션 어디에 있어도 산출물을
    깨뜨리므로 그쪽은 맞다). 이 축은 반대다 — 실사용 실측에서 막힌 덱이 1장이라도 있는 study
    폴더가 51/230 이고 그 폴더의 덱 총수는 **515/938** 이다. 폴더 하나를 세션 하나로 올리는
    정상 운용에서 개별로 걸리는 147장의 **3.5배**가 함께 물든다.
    """
    src = (Path(__file__).resolve().parents[1] / "app/modules/jobs/routes.py").read_text(encoding="utf-8")
    # ⚠ 주석을 걷고 본다. 처음에 이 시험이 **내 주석 안의 문구**("`or dang` 폴백을 쓰지 않는다")를
    # 잡아 빨갰다 — 코드는 맞았는데 시험이 글자만 봤다. 문서와 코드를 같은 잣대로 읽으면 안 된다.
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    dang_hit = [l for l in code.splitlines() if l.strip().startswith("hit = ") and "dang" in l]
    inc_hit = [l for l in code.splitlines() if l.strip().startswith("hit = ") and "inc." in l]
    assert len(dang_hit) == 1 and len(inc_hit) == 1, (dang_hit, inc_hit)
    assert "or dang" not in dang_hit[0], "미정의 참조 축에는 세션 전체 폴백을 쓰지 않는다"
    # 인클루드 축의 폴백은 **그대로 있어야 한다** — 서로 다른 판단이다.
    assert "or inc" in inc_hit[0], "인클루드 축의 폴백은 건드리지 않는다"
