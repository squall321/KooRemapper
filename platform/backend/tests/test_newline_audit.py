# 덱 왕복 개행 경고의 규칙 넷 — 특히 **섞인 덱**을 판정 대조가 놓치는 자리를 지킨다
"""왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P1-8).

`kfile_inspect` 의 개행 판정 규약은 `count(CRLF)*2 > count(LF)` 다. 그래서 **섞인 덱**은
지배적인 쪽으로 보고된다 — 실제로 고친 `implicit`(CRLF 86 / LF단독 15)과
`squeeze`(CRLF 73 / LF단독 2)는 그 규약 아래서 전부 "crlf" 다. 입력도 crlf 였으니
**판정 대조만으로는 경고가 안 뜬다.** 한 파일 안에서 개행이 갈리는 것이 리뷰가 최악이라
짚은 모양인데 그것부터 못 보는 것이다. 그래서 섞임을 별도 규칙으로 본다.
"""
from app.runner.newline_audit import audit_newlines


def deck(newline="crlf", n_crlf=100, n_lines=100, final=True, truncated=False):
    return {"newline": newline, "n_crlf": n_crlf, "n_lines": n_lines,
            "final_newline": final, "truncated_scan": truncated}


def test_a_clean_roundtrip_warns_about_nothing():
    before = {"in.k": deck()}
    after = {"out.k": deck()}
    assert audit_newlines(before, after) == []


def test_a_mixed_output_is_caught_even_though_the_verdict_still_says_crlf():
    """⚠ 이 시험이 핵심이다. `implicit` 의 실측(CRLF 86 / LF단독 15)을 그대로 쓴다 —
    86*2 > 101 이라 판정은 "crlf" 이고 입력도 crlf 다. 대조만 하면 조용히 통과한다."""
    before = {"in.k": deck(n_crlf=101, n_lines=101)}
    after = {"out.k": deck(newline="crlf", n_crlf=86, n_lines=101)}
    w = audit_newlines(before, after)
    assert len(w) == 1, w
    assert "개행이 갈린다" in w[0] and "CRLF 86줄" in w[0] and "LF단독 15줄" in w[0]


def test_squeeze_two_stray_lines_are_caught():
    """`squeeze` 의 실측(CRLF 73 / LF단독 2) — 두 줄만 어긋나도 잡아야 한다."""
    after = {"output_s1.k": deck(newline="crlf", n_crlf=73, n_lines=75)}
    w = audit_newlines({"in.k": deck()}, after)
    assert len(w) == 1 and "LF단독 2줄" in w[0], w


def test_an_overwritten_deck_that_flipped_is_caught():
    before = {"model.k": deck(newline="crlf", n_crlf=100, n_lines=100)}
    after = {"model.k": deck(newline="lf", n_crlf=0, n_lines=100)}
    w = audit_newlines(before, after)
    assert len(w) == 1 and "CRLF → LF" in w[0], w


def test_a_new_deck_that_differs_from_a_unanimous_input_is_caught():
    before = {"a.k": deck("crlf"), "b.k": deck("crlf")}
    after = {"out.k": deck("lf", n_crlf=0, n_lines=50)}
    w = audit_newlines(before, after)
    assert len(w) == 1 and "입력 덱은 CRLF" in w[0] and "산출 덱은 LF" in w[0], w


def test_mixed_inputs_do_not_produce_a_guess():
    """입력이 섞여 있으면 무엇을 기준으로 삼을지 알 수 없다 — 억지로 고르면 실사용 잡에
    오탐이 쏟아진다. 새로 생긴 덱에 대해서는 잠자코 있는 것이 맞다.

    ⚠ **두 방향을 다 본다.** 한 방향만 보면 "집합에서 아무거나 고른다" 는 구현이 우연히
    통과한다(변이 시험에서 실제로 살아남았다) — 고른 값이 마침 산출물과 같으면 조용하다."""
    before = {"a.k": deck("crlf"), "b.k": deck("lf", n_crlf=0, n_lines=10)}
    assert audit_newlines(before, {"out.k": deck("lf", n_crlf=0, n_lines=50)}) == []
    assert audit_newlines(before, {"out.k": deck("crlf", n_crlf=50, n_lines=50)}) == []


def test_a_lost_final_newline_is_caught():
    before = {"model.k": deck(final=True)}
    after = {"model.k": deck(final=False)}
    w = audit_newlines(before, after)
    assert len(w) == 1 and "끝 개행이 사라졌다" in w[0], w


def test_non_decks_are_ignored():
    """`kfile_inspect` 는 덱에만 `newline` 을 싣는다 — config.yaml 등은 대조 대상이 아니다."""
    before = {"config.yaml": {"filename": "config.yaml"}}
    after = {"config.yaml": {"filename": "config.yaml"}, "log.txt": {}}
    assert audit_newlines(before, after) == []


def test_an_lf_only_project_stays_quiet():
    """LF 로만 작업하는 팀에 경고가 뜨면 안 된다 — 보존이 곧 정답이다."""
    before = {"in.k": deck("lf", n_crlf=0, n_lines=100)}
    after = {"out.k": deck("lf", n_crlf=0, n_lines=120)}
    assert audit_newlines(before, after) == []


def test_a_truncated_scan_says_so():
    """8MB 넘는 덱은 앞부분만 본다 — 경고에 그 사실을 적어야 사람이 판단할 수 있다."""
    after = {"out.k": deck(newline="crlf", n_crlf=80, n_lines=100, truncated=True)}
    w = audit_newlines({"in.k": deck()}, after)
    assert len(w) == 1 and "앞부분만 검사했다" in w[0], w


def test_an_overwritten_files_prior_newline_still_counts_as_input():
    """덮어쓴 파일의 **왕복 전** 개행도 이 잡의 입력이다. 그것을 집계에서 빼면, 입력이
    실제로는 갈려 있는데 남은 하나로 "일치" 라고 단정해 새 덱에 오탐을 낸다.

    여기서는 입력이 갈려 있다(model.k 는 CRLF, ref.k 는 LF). 그러니 새로 생긴 new.k 에
    대해서는 아무 말도 하지 않아야 하고, 경고는 model.k 가 뒤집힌 것 하나뿐이어야 한다."""
    before = {"model.k": deck("crlf"), "ref.k": deck("lf", n_crlf=0, n_lines=10)}
    after = {"model.k": deck("lf", n_crlf=0, n_lines=100),
             "new.k": deck("crlf", n_crlf=30, n_lines=30)}
    w = audit_newlines(before, after)
    assert len(w) == 1, w
    assert "model.k" in w[0] and "CRLF → LF" in w[0], w


def test_rule_c_still_fires_when_every_input_agrees():
    """반대로 입력이 전부 일치하면(덮어쓴 것까지) 새 덱의 차이는 말해야 한다."""
    before = {"model.k": deck("crlf"), "ref.k": deck("crlf")}
    after = {"model.k": deck("crlf"), "new.k": deck("lf", n_crlf=0, n_lines=30)}
    w = audit_newlines(before, after)
    assert len(w) == 1 and "new.k" in w[0] and "입력 덱은 CRLF" in w[0], w
