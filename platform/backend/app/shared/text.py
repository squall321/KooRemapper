# 남이 지은 글을 응답 · 원장에 낼 때 찍히는 글자 한 줄 · 상한으로 접는 도우미
"""system 상태의 후처리 판(꾸러미 producer)과 7-1 반입의 이미지 출처가 같이 쓴다 — 둘 다 남이 지은 글을 로그인한
모두에게 낸다(낙하 파이프라인 (c) · ⑥)."""
from __future__ import annotations


def one_line(v, cap: int) -> str | None:
    """찍히는 글자 한 줄 · 상한 — 줄바꿈 · 제어 문자는 빈칸으로 접는다. 비면 None."""
    if v is None:
        return None
    # 훑기 전에 먼저 자른다 — 긴 글 전체를 글자마다 훑지 않게(11-15 검토). 빈칸 접기로 줄어들 몫을 넉넉히 둔다.
    raw = str(v)[: cap * 4]
    s = " ".join("".join(ch if ch.isprintable() else " " for ch in raw).split())
    return s[:cap] or None
