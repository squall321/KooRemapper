# 덱이 왕복에서 개행을 잃었나 — 잡 기록에 남길 경고 문장을 만드는 순수 함수
"""왜 이 모듈이 있나 (2026-09-25, 덱 계약 2차 P1-8).

바이너리 쪽 개행 소실 12곳을 고쳤지만(afbc154·e841e5a), **플랫폼은 여전히 못 본다.** 실사용은
덱을 올려 op 을 돌리고 내려받는다 — 그 왕복에서 바이트가 달라졌는지 화면에 아무 표시가 없었다.
캠페인이 CRLF 소실을 먼저 찾아 돌려준 것이 그 증거다.

⚠ **`newline` 판정 하나만 대조하면 최악의 경우를 놓친다.** `kfile_inspect` 의 규약은
`count(CRLF)*2 > count(LF)` 라(요청서 DF-01), **섞인 덱**은 지배적인 쪽으로 보고된다.
실제로 고친 `implicit`(CRLF 86 / LF단독 15)과 `squeeze`(CRLF 73 / LF단독 2)는 그 규약 아래서
전부 "crlf" 로 나온다 — 입력도 crlf 였으니 대조만으로는 **경고가 안 뜬다.** 한 파일 안에서
개행이 갈리는 것이 리뷰가 최악이라 짚은 모양인데, 그것부터 못 보는 것이다.

그래서 규칙 네 개를 본다.
  A 산출 덱이 **섞였다** — `0 < n_crlf < n_lines`. 판정과 무관하게 언제나 결함이다
  B **왕복에서 개행 종류가 바뀌었다** — 같은 이름의 파일이 crlf → lf 또는 반대로
  C **입력 대비 산출이 다르다** — 새로 생긴 덱. 입력 덱들이 한 종류로 일치할 때만 본다
  D **말미 개행이 사라졌다** — 왕복 전 있었는데 없어졌다. LS-DYNA 가 마지막 카드를 흘린다
"""
from __future__ import annotations

_NL_KO = {"crlf": "CRLF", "lf": "LF"}


def _is_deck(meta) -> bool:
    """개행을 판정할 수 있는 덱인가 — `kfile_inspect` 가 덱에만 `newline` 을 싣는다."""
    return isinstance(meta, dict) and meta.get("newline") in _NL_KO


def audit_newlines(before: dict, after: dict) -> list[str]:
    """왕복 전/후 메타를 받아 경고 문장 목록을 돌려준다(없으면 빈 목록).

    before — 잡 실행 **전** 세션 파일의 메타 {파일이름: meta}
    after  — 이 잡이 낸/덮어쓴 산출 덱의 메타 {파일이름: meta}
    """
    warns: list[str] = []

    # 입력 덱들이 한 종류로 일치하나 — 규칙 C 는 일치할 때만 쓴다. 섞여 있으면 무엇을
    # 기준으로 삼아야 할지 알 수 없고, 억지로 고르면 실사용 잡에 오탐이 쏟아진다.
    #
    # ⚠ 덮어쓴 파일도 **집계에 넣는다.** 처음에는 빼 뒀는데 변이 시험이 그것이 거꾸로임을
    # 보여 줬다 — 덮어쓴 파일의 **왕복 전** 개행도 엄연히 이 잡의 입력이다. 빼면 입력이
    # 실제로는 갈려 있는데 남은 하나로 "일치" 라고 단정해 새 덱에 오탐을 낸다. 넣으면
    # 갈린 사실이 드러나 규칙 C 가 잠자코 있는다. 모를 때는 말하지 않는 쪽이다.
    in_kinds = {m["newline"] for m in before.values() if _is_deck(m)}
    unanimous = next(iter(in_kinds)) if len(in_kinds) == 1 else None

    for name in sorted(after):
        new = after[name]
        if not _is_deck(new):
            continue
        n_crlf = new.get("n_crlf")
        n_lines = new.get("n_lines")
        head_only = bool(new.get("truncated_scan"))
        tail = " (앞부분만 검사했다)" if head_only else ""

        # A — 섞였다. 이것이 가장 나쁘고, 판정 대조로는 안 잡힌다.
        if isinstance(n_crlf, int) and isinstance(n_lines, int) and 0 < n_crlf < n_lines:
            warns.append(
                f"{name}: 한 파일 안에서 개행이 갈린다 — CRLF {n_crlf}줄 · LF단독 "
                f"{n_lines - n_crlf}줄{tail}. LS-DYNA 가 카드를 잘못 읽을 수 있다."
            )

        old = before.get(name)
        if _is_deck(old):
            # B — 같은 이름의 덱을 덮어썼는데 개행 종류가 바뀌었다
            if old["newline"] != new["newline"]:
                warns.append(
                    f"{name}: 왕복에서 개행이 {_NL_KO[old['newline']]} → "
                    f"{_NL_KO[new['newline']]} 로 바뀌었다{tail}."
                )
            # D — 말미 개행이 사라졌다
            if old.get("final_newline") and not new.get("final_newline"):
                warns.append(f"{name}: 파일 끝 개행이 사라졌다 — 마지막 카드가 흘릴 수 있다.")
        elif unanimous and new["newline"] != unanimous:
            # C — 새로 생긴 덱이 입력과 다르다
            warns.append(
                f"{name}: 입력 덱은 {_NL_KO[unanimous]} 인데 산출 덱은 "
                f"{_NL_KO[new['newline']]} 다{tail}."
            )

    return warns
